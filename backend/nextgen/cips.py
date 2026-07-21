"""CIPS participant routing, RTGS/DNS settlement and two-tier e-CNY services."""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from database import EcnyAccount
from ecny.ledger.engine import burn, get_or_create_account, mint

from .models import (
    CipsAccount,
    CipsParticipant,
    CipsSettlement,
    EcnyOperator,
    PaymentLensEvent,
    utcnow,
)
from .payments import PaymentLifecycleError
from .runtime import LeaseService, OutboxService
from .standards import finding_dicts, validate_message


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class CipsService:
    def __init__(self, db: Session):
        self.db = db

    def register_participant(
        self,
        participant_id: str,
        name: str,
        participant_type: str,
        country: str,
        bic: str | None = None,
        lei: str | None = None,
        capabilities: list[str] | None = None,
        settlement_hours: dict[str, str] | None = None,
    ) -> CipsParticipant:
        if participant_type not in {"direct", "indirect"}:
            raise ValueError("participant_type must be direct or indirect")
        if self.db.query(CipsParticipant).filter_by(participant_id=participant_id).first():
            raise ValueError("participant already exists")
        participant = CipsParticipant(
            participant_id=participant_id,
            name=name,
            participant_type=participant_type,
            bic=bic,
            lei=lei,
            country=country.upper(),
            capabilities=_json(sorted(set(capabilities or ["RTGS"]))),
            settlement_hours=_json(settlement_hours or {}),
        )
        self.db.add(participant)
        self.db.flush()
        return participant

    def route_candidates(
        self,
        destination_country: str,
        required_capability: str = "RTGS",
        destination_bic: str | None = None,
    ) -> list[dict[str, Any]]:
        candidates = []
        for participant in self.db.query(CipsParticipant).filter_by(active=True).all():
            capabilities = set(json.loads(participant.capabilities or "[]"))
            if required_capability not in capabilities:
                continue
            score = 0
            reasons = []
            if participant.participant_type == "direct":
                score += 50
                reasons.append("direct participant")
            if participant.country == destination_country.upper():
                score += 30
                reasons.append("destination jurisdiction")
            if destination_bic and participant.bic == destination_bic:
                score += 100
                reasons.append("exact BIC")
            candidates.append(
                {
                    "participant_id": participant.participant_id,
                    "score": score,
                    "reasons": reasons,
                    "participant_type": participant.participant_type,
                    "bic": participant.bic,
                    "country": participant.country,
                }
            )
        return sorted(candidates, key=lambda item: (-item["score"], item["participant_id"]))

    def open_account(
        self,
        participant_id: str,
        initial_balance: int = 0,
        currency: str = "CNY",
    ) -> CipsAccount:
        if initial_balance < 0:
            raise ValueError("initial balance cannot be negative")
        participant = self.db.query(CipsParticipant).filter_by(participant_id=participant_id).one()
        if participant.participant_type != "direct":
            raise ValueError("Only direct participants may hold settlement accounts")
        account = CipsAccount(
            account_id=f"cips-acct-{uuid.uuid4().hex}",
            participant_id=participant_id,
            balance=initial_balance,
            currency=currency,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def submit_settlement(
        self,
        uetr: str,
        mode: str,
        debtor_participant: str,
        creditor_participant: str,
        amount: int,
        priority: int = 5,
        batch_id: str | None = None,
    ) -> CipsSettlement:
        if mode not in {"RTGS", "DNS"}:
            raise ValueError("mode must be RTGS or DNS")
        if amount <= 0:
            raise ValueError("amount must be positive")
        settlement = CipsSettlement(
            settlement_id=f"cips-set-{uuid.uuid4().hex}",
            uetr=uetr,
            mode=mode,
            debtor_participant=debtor_participant,
            creditor_participant=creditor_participant,
            amount=amount,
            priority=priority,
            batch_id=batch_id,
        )
        self.db.add(settlement)
        self.db.flush()
        self._lens(uetr, "cips.submitted", "QUEUED", {"mode": mode})
        if mode == "RTGS":
            self.settle_rtgs(settlement.settlement_id)
        return settlement

    def settle_rtgs(self, settlement_id: str) -> CipsSettlement:
        settlement = self.db.query(CipsSettlement).filter_by(settlement_id=settlement_id).one()
        if settlement.status == "SETTLED":
            return settlement
        owner = f"rtgs-{uuid.uuid4().hex}"
        lease = LeaseService(self.db)
        token = lease.acquire(f"cips-settlement:{settlement_id}", owner)
        try:
            debtor = self._account(settlement.debtor_participant, settlement.currency)
            creditor = self._account(settlement.creditor_participant, settlement.currency)
            available = debtor.balance - debtor.reserved
            if available < settlement.amount:
                settlement.status = "QUEUED"
                self._lens(
                    settlement.uetr,
                    "cips.liquidity",
                    "QUEUED",
                    {"available": available, "required": settlement.amount},
                )
                return settlement
            debtor.balance -= settlement.amount
            creditor.balance += settlement.amount
            debtor.version += 1
            creditor.version += 1
            settlement.status = "SETTLED"
            settlement.settled_at = utcnow()
            self._lens(
                settlement.uetr,
                "cips.rtgs",
                "SETTLED",
                {"settlement_id": settlement_id},
            )
            OutboxService(self.db).enqueue(
                "cips.settled",
                settlement.uetr,
                {"settlement_id": settlement_id, "mode": "RTGS"},
            )
            self.db.flush()
            return settlement
        finally:
            lease.release(f"cips-settlement:{settlement_id}", token)

    def release_rtgs_queue(self) -> list[str]:
        settled = []
        queue = (
            self.db.query(CipsSettlement)
            .filter_by(mode="RTGS", status="QUEUED")
            .order_by(CipsSettlement.priority.desc(), CipsSettlement.id)
            .all()
        )
        for settlement in queue:
            result = self.settle_rtgs(settlement.settlement_id)
            if result.status == "SETTLED":
                settled.append(result.settlement_id)
        return settled

    def settle_dns_batch(self, batch_id: str) -> dict[str, int]:
        settlements = (
            self.db.query(CipsSettlement)
            .filter_by(mode="DNS", batch_id=batch_id, status="QUEUED")
            .order_by(CipsSettlement.id)
            .all()
        )
        if not settlements:
            raise ValueError("No queued DNS settlements")
        net: dict[str, int] = defaultdict(int)
        for settlement in settlements:
            net[settlement.debtor_participant] -= settlement.amount
            net[settlement.creditor_participant] += settlement.amount
        for participant_id, position in net.items():
            if position < 0:
                account = self._account(participant_id, "CNY")
                if account.balance - account.reserved < -position:
                    raise ValueError(f"Insufficient DNS liquidity for {participant_id}")
        for participant_id, position in net.items():
            account = self._account(participant_id, "CNY")
            account.balance += position
            account.version += 1
        for settlement in settlements:
            settlement.status = "SETTLED"
            settlement.settled_at = utcnow()
            self._lens(
                settlement.uetr,
                "cips.dns",
                "SETTLED",
                {"batch_id": batch_id},
            )
        OutboxService(self.db).enqueue("cips.dns.settled", batch_id, {"net": dict(net)})
        self.db.flush()
        return dict(net)

    def prevalidate(
        self,
        message_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        findings = validate_message("cips:2026", message_type, payload)
        return {
            "valid": not any(finding.severity == "error" for finding in findings),
            "findings": finding_dicts(findings),
        }

    def timeline(self, uetr: str) -> list[PaymentLensEvent]:
        return (
            self.db.query(PaymentLensEvent).filter_by(uetr=uetr).order_by(PaymentLensEvent.id).all()
        )

    def _account(self, participant_id: str, currency: str) -> CipsAccount:
        account = (
            self.db.query(CipsAccount)
            .filter_by(participant_id=participant_id, currency=currency)
            .first()
        )
        if not account:
            raise ValueError(f"Settlement account not found: {participant_id}/{currency}")
        return account

    def _lens(self, uetr: str, event_type: str, status: str, details: dict[str, Any]) -> None:
        self.db.add(
            PaymentLensEvent(
                uetr=uetr,
                system="CIPS",
                event_type=event_type,
                status=status,
                details=_json(details),
            )
        )


class EcnyOperatorService:
    """Central-bank issuance controls for the two-tier operating model."""

    def __init__(self, db: Session):
        self.db = db

    def register(
        self,
        operator_id: str,
        name: str,
        issuance_limit: int,
        reserve_amount: int = 0,
    ) -> EcnyOperator:
        if issuance_limit <= 0 or reserve_amount < 0:
            raise ValueError("Invalid issuance or reserve amount")
        if self.db.query(EcnyOperator).filter_by(operator_id=operator_id).first():
            raise ValueError("operator already exists")
        operator = EcnyOperator(
            operator_id=operator_id,
            name=name,
            issuance_limit=issuance_limit,
            reserve_amount=reserve_amount,
        )
        self.db.add(operator)
        get_or_create_account(
            self.db,
            f"acct-operator-{operator_id}",
            "operator",
            operator_id,
        )
        self.db.flush()
        return operator

    def issue(self, operator_id: str, amount: int):
        operator = self.db.query(EcnyOperator).filter_by(operator_id=operator_id).one()
        if operator.status != "active":
            raise PaymentLifecycleError("operator is not active")
        if amount <= 0 or operator.issued_amount + amount > operator.issuance_limit:
            raise PaymentLifecycleError("issuance limit exceeded")
        transaction = mint(
            self.db,
            f"acct-operator-{operator_id}",
            amount,
            {"operator_id": operator_id, "tier": "central_bank_to_operator"},
        )
        operator.issued_amount += amount
        self.db.flush()
        return transaction

    def redeem(self, operator_id: str, amount: int):
        operator = self.db.query(EcnyOperator).filter_by(operator_id=operator_id).one()
        if amount <= 0 or amount > operator.issued_amount:
            raise PaymentLifecycleError("invalid redemption amount")
        transaction = burn(
            self.db,
            f"acct-operator-{operator_id}",
            amount,
            {"operator_id": operator_id, "tier": "operator_to_central_bank"},
        )
        operator.issued_amount -= amount
        self.db.flush()
        return transaction

    def reconcile(self, operator_id: str) -> dict[str, int | bool]:
        operator = self.db.query(EcnyOperator).filter_by(operator_id=operator_id).one()
        account = (
            self.db.query(EcnyAccount).filter_by(account_id=f"acct-operator-{operator_id}").one()
        )
        return {
            "issued_amount": operator.issued_amount,
            "ledger_balance": account.balance,
            "reserve_amount": operator.reserve_amount,
            "within_limit": operator.issued_amount <= operator.issuance_limit,
            "reconciled": operator.issued_amount == account.balance,
        }
