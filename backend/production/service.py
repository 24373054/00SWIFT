"""Production payment orchestration and projection services."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from config import get_settings
from nextgen.standards import finding_dicts, validate_message

from .connectors import SandboxFxQuoteProvider
from .corridors import assert_corridor_admitted
from .limit_reservation import LimitReservationError, LimitReservationService
from .models import (
    ProductionAuthorizationDecision,
    ProductionCancellationRequest,
    ProductionCompletionProfile,
    ProductionComplianceDecision,
    ProductionControlAttestation,
    ProductionCorridorAdmission,
    ProductionDeliveryProfile,
    ProductionExposurePosition,
    ProductionFinalityProfile,
    ProductionFundingReservation,
    ProductionFxQuote,
    ProductionFxTradeIntent,
    ProductionLedgerAccount,
    ProductionLimitCounter,
    ProductionPaymentFact,
    ProductionPaymentOrder,
    ProductionReturnPayment,
    ProductionSettlementLeg,
    utcnow,
)
from .rulebook_service import RulebookError, RulebookService
from .runtime import (
    ProductionAuditService,
    ProductionConflict,
    ProductionEvidenceService,
    ProductionIdempotencyService,
    ProductionOutboxService,
    canonical_json,
    digest,
    minor_amount,
)
from .security import ProductionPrincipal, assert_account_access, assert_entitlement, assert_limit
from .standards import ensure_artifact, validate_and_record

ORCHESTRATION_TERMINAL = {
    "OPERATIONALLY_CLOSED",
    "OPERATIONALLY_CLOSED_UNSUCCESSFUL",
}

ALLOWED_ORDER_TRANSITIONS: dict[str, set[str]] = {
    "CONTROL_CHECKS": {"RESERVATION_PENDING", "FX_ACCEPTANCE_PENDING", "COMPLIANCE_REJECTED", "SUSPENDED", "EXECUTION_CANCELLED"},
    "RESERVATION_PENDING": {"MESSAGE_DELIVERED", "SUSPENDED", "EXECUTION_CANCELLED"},
    "FX_ACCEPTANCE_PENDING": {"FX_ACCEPTED", "SUSPENDED", "EXECUTION_CANCELLED"},
    "FX_ACCEPTED": {"MESSAGE_DELIVERED", "SUSPENDED", "EXECUTION_CANCELLED"},
    "MESSAGE_DELIVERED": {"VALUE_SETTLEMENT", "SUSPENDED", "EXECUTION_CANCELLED"},
    "VALUE_SETTLEMENT": {"CUSTOMER_COMPLETED", "SUSPENDED", "EXECUTION_CANCELLED"},
    "CUSTOMER_COMPLETED": {"OPERATIONALLY_CLOSED"},
    "COMPLIANCE_REJECTED": {"OPERATIONALLY_CLOSED_UNSUCCESSFUL"},
    "EXECUTION_CANCELLED": {"OPERATIONALLY_CLOSED_UNSUCCESSFUL"},
    "SUSPENDED": {"RESERVATION_PENDING", "FX_ACCEPTANCE_PENDING", "MESSAGE_DELIVERED", "VALUE_SETTLEMENT", "OPERATIONALLY_CLOSED_UNSUCCESSFUL", "EXECUTION_CANCELLED"},
    "OPERATIONALLY_CLOSED": set(),
    "OPERATIONALLY_CLOSED_UNSUCCESSFUL": set(),
}


def _uuid4(value: str | None = None) -> str:
    if value is None:
        return str(uuid.uuid4())
    parsed = uuid.UUID(value)
    if parsed.version != 4:
        raise ProductionConflict("UETR must be an RFC4122 UUIDv4")
    return str(parsed)


def _amount_fields(payload: dict[str, Any]) -> tuple[int, str, str]:
    instructed = payload.get("instructed_amount") or payload.get("amount")
    if not isinstance(instructed, dict):
        raise ProductionConflict("instructed_amount must contain currency and value")
    currency = str(instructed.get("currency", "")).upper()
    settlement_currency = str(payload.get("settlement_currency") or currency).upper()
    if len(currency) != 3 or len(settlement_currency) != 3:
        raise ProductionConflict("currency must be an ISO 4217 alphabetic code")
    return minor_amount(instructed.get("value", instructed.get("amount")), currency), currency, settlement_currency


def _party_ref(value: Any, field: str) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise ProductionConflict(f"{field} is required")
    party = str(value.get("party_id") or value.get("name") or "").strip()
    account = str(value.get("account_id") or value.get("account") or "").strip()
    if not party or not account:
        raise ProductionConflict(f"{field} must contain party_id/name and account reference")
    return party[:160], account[:160]


def _json_load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _as_utc(value: dt.datetime) -> dt.datetime:
    return value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value


class ProductionPaymentService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_reference_data(self) -> None:
        ensure_artifact(self.db, profile="iso20022-base:2026", message_type="pacs.008", version="2026.1", simulation_only=True)
        if not self.db.query(ProductionCompletionProfile).filter_by(profile_id="cmp-cn-hk-cny-v1").first():
            self.db.add(
                ProductionCompletionProfile(
                    profile_id="cmp-cn-hk-cny-v1",
                    corridor="CN-HK",
                    required_messages=json.dumps(["payment-message"], separators=(",", ":")),
                    required_funding=json.dumps(["debit"], separators=(",", ":")),
                    required_fx=json.dumps([], separators=(",", ":")),
                    required_settlement=json.dumps(["PAYMENT_VALUE"], separators=(",", ":")),
                    required_credits=json.dumps(["beneficiary"], separators=(",", ":")),
                    projection_rule_version="cmp-cn-hk-cny-v1",
                )
            )
        if not self.db.query(ProductionCompletionProfile).filter_by(profile_id="cmp-cn-hk-fx-v1").first():
            self.db.add(
                ProductionCompletionProfile(
                    profile_id="cmp-cn-hk-fx-v1",
                    corridor="CN-HK",
                    required_messages=json.dumps(["payment-message"], separators=(",", ":")),
                    required_funding=json.dumps(["debit", "credit"], separators=(",", ":")),
                    required_fx=json.dumps(["FX_SELL", "FX_BUY"], separators=(",", ":")),
                    required_settlement=json.dumps(["FX_SELL", "FX_BUY", "PAYMENT_VALUE"], separators=(",", ":")),
                    required_credits=json.dumps(["beneficiary"], separators=(",", ":")),
                    projection_rule_version="cmp-cn-hk-fx-v1",
                )
            )
        if not self.db.query(ProductionFinalityProfile).filter_by(profile_id="sandbox-finality-v1").first():
            self.db.add(
                ProductionFinalityProfile(
                    profile_id="sandbox-finality-v1",
                    connector="sandbox-value-settlement",
                    jurisdiction="CN-HK",
                    accepted_event="ACCEPTED",
                    irrevocable_event="IRREVOCABLE",
                    final_event="FINAL",
                    evidence_schema="simulation-finality-proof-v1",
                    rulebook_reference="sandbox-rulebook-v1",
                )
            )
        if not self.db.query(ProductionDeliveryProfile).filter_by(profile_id="delivery-cn-hk-pacs008-v1").first():
            self.db.add(
                ProductionDeliveryProfile(
                    profile_id="delivery-cn-hk-pacs008-v1",
                    version="1.0",
                    required_network_state="DELIVERED",
                    business_response_required=False,
                    non_blocking=False,
                    message_set=json.dumps(["pacs.008", "pacs.002", "pacs.004"], separators=(",", ":")),
                )
            )
        for currency in ("CNY", "HKD"):
            account_id = f"SANDBOX-ORIGIN:{currency}"
            if not self.db.query(ProductionLedgerAccount).filter_by(account_id=account_id).first():
                self.db.add(
                    ProductionLedgerAccount(
                        account_id=account_id,
                        legal_entity="SANDBOX-ORIGIN",
                        book="cross-border-settlement",
                        currency=currency,
                        account_type="NOSTRO",
                        balance_minor=100_000_000_00,
                    )
                )
        if not self.db.query(ProductionCorridorAdmission).filter_by(admission_id="sandbox-adm-cn-hk-v1").first():
            now = utcnow()
            self.db.add(ProductionCorridorAdmission(
                admission_id="sandbox-adm-cn-hk-v1", environment="sandbox", corridor="CN-HK",
                applicable_subjects='["*"]', scenarios='["TRADE"]', currencies='["CNY","HKD"]',
                min_amount_minor=1, max_amount_minor=100_000_000_00,
                valid_from=now - dt.timedelta(days=1), valid_to=now + dt.timedelta(days=365),
                funding_flow_version="sandbox-funding-v1", finality_definition="sandbox-finality-v1",
                data_flow_version="sandbox-data-v1", rulebook_version="sandbox-rulebook-v1",
                signed_roles='["sandbox-authority"]', status="ACTIVE", simulation_only=True,
                evidence_ref="evidence://sandbox/corridor-admission",
            ))
            self.db.add(ProductionControlAttestation(
                attestation_id="sandbox-control-cn-hk-v1", admission_id="sandbox-adm-cn-hk-v1",
                signer_role="sandbox-authority", signer_subject="sandbox",
                statement_digest=digest({"admission": "sandbox-adm-cn-hk-v1"}),
                valid_from=now - dt.timedelta(days=1), valid_to=now + dt.timedelta(days=365),
                status="ACTIVE", evidence_ref="evidence://sandbox/control-attestation",
            ))
        self.db.flush()

    def create_payment(
        self,
        principal: ProductionPrincipal,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        if get_settings().is_sandbox:
            self.ensure_reference_data()
        amount_minor_value, currency, settlement_currency = _amount_fields(payload)
        if not get_settings().is_sandbox:
            try:
                RulebookService(self.db).assert_current(principal.participant_id)
            except RulebookError as exc:
                raise ProductionConflict(str(exc)) from exc
        corridor = str(payload.get("corridor") or "CN-HK").upper()
        message_type = str(payload.get("message_type") or "pacs.008")
        scenario = str((payload.get("purpose") or {}).get("code") or "UNSPECIFIED").upper()
        assert_corridor_admitted(
            self.db, participant_id=principal.participant_id, corridor=corridor,
            scenario=scenario, currency=currency, amount_minor=amount_minor_value,
        )
        scope = f"{principal.participant_id}:POST:/production/v1/payments"
        record, replay = ProductionIdempotencyService(self.db).begin(scope, idempotency_key, payload)
        if replay and record.status == "COMPLETED":
            return _json_load(record.response_body, {})
        debtor_party, debtor_account = _party_ref(payload.get("debtor"), "debtor")
        creditor_party, creditor_account = _party_ref(payload.get("creditor"), "creditor")
        uetr = _uuid4(payload.get("uetr"))
        instruction_id = str(payload.get("instruction_id") or f"INST-{uuid.uuid4().hex}")[:200]
        entitlement = assert_entitlement(
            self.db,
            principal,
            service="payment.create",
            corridor=corridor,
            currency=currency,
            message_type=message_type,
            counterparty_id=creditor_party,
            amount_minor=amount_minor_value,
        )
        limit_profile = assert_limit(
            self.db,
            principal,
            service="payment.create",
            corridor=corridor,
            currency=currency,
            amount_minor=amount_minor_value,
        )
        assert_account_access(self.db, principal, debtor_account, currency, debtor_party)
        standards_payload = {
            "message_type": message_type,
            "header": {
                "biz_msg_id": instruction_id,
                "message_definition": message_type,
                "sender": debtor_party,
                "receiver": creditor_party,
            },
            "document": {
                "message_id": instruction_id,
                "uetr": uetr,
                "amount": str(payload.get("instructed_amount", {}).get("amount")),
                "currency": currency,
                "debtor": payload.get("debtor"),
                "creditor": payload.get("creditor"),
            },
        }
        findings = finding_dicts(validate_message("iso20022-base:2026", message_type, standards_payload))
        if any(item["severity"].lower() == "error" for item in findings):
            raise ProductionConflict(f"Standards validation failed: {canonical_json(findings)}")
        if currency == settlement_currency and payload.get("quote_id"):
            raise ProductionConflict("Same-currency payment cannot include quote_id")
        if currency != settlement_currency and not payload.get("quote_id"):
            raise ProductionConflict("Cross-currency payment requires an approved quote_id")
        order = ProductionPaymentOrder(
            order_id=f"pay_{uuid.uuid4().hex}",
            uetr=uetr,
            instruction_id=instruction_id,
            tenant_id=principal.tenant_id,
            initiator_participant=principal.participant_id,
            corridor=corridor,
            debtor_party_ref=debtor_party,
            debtor_account_ref=debtor_account,
            creditor_party_ref=creditor_party,
            creditor_account_ref=creditor_account,
            amount_minor=amount_minor_value,
            currency=currency,
            settlement_currency=settlement_currency,
            purpose_code=str((payload.get("purpose") or {}).get("code") or "UNSPECIFIED")[:40],
            payload=canonical_json(payload),
            payload_hash=digest(payload),
            orchestration_state="CONTROL_CHECKS",
            completion_profile_id="cmp-cn-hk-fx-v1" if currency != settlement_currency else "cmp-cn-hk-cny-v1",
            projection_rule_version="cmp-cn-hk-cny-cny-v1",
        )
        self.db.add(order)
        self.db.flush()
        if limit_profile is not None:
            try:
                counter, _position = LimitReservationService(self.db).reserve(
                    tenant_id=principal.tenant_id,
                    participant_id=principal.participant_id,
                    service="payment.create",
                    corridor=corridor,
                    currency=currency,
                    business_date=utcnow().date(),
                    amount_minor=amount_minor_value,
                    daily_limit_minor=limit_profile.daily_amount_minor,
                    exposure_limit_minor=limit_profile.max_exposure_minor,
                )
            except LimitReservationError as exc:
                raise ProductionConflict(str(exc)) from exc
            order.limit_reservation_id = counter.counter_id
            self.db.flush()
        standards_result = validate_and_record(self.db, profile="iso20022-base:2026", message_type=message_type, payload=standards_payload, order_id=order.order_id)
        if not standards_result["valid"]:
            raise ProductionConflict(f"Standards validation failed: {canonical_json(standards_result['findings'])}")
        auth = ProductionAuthorizationDecision(
            decision_id=f"authz_{uuid.uuid4().hex}",
            order_id=order.order_id,
            outcome="PENDING",
            payment_hash=order.payload_hash,
            mandate_ref=(payload.get("authorization") or {}).get("mandate_id"),
            approval_ref=(payload.get("authorization") or {}).get("corporate_approval_ref"),
            input_hash=digest(payload.get("authorization") or {}),
            rule_version="authz-cn-hk-v1",
        )
        compliance = ProductionComplianceDecision(
            decision_id=f"comp_{uuid.uuid4().hex}",
            order_id=order.order_id,
            outcome="PENDING",
            input_hash=digest(payload),
            rule_version="aml-cn-hk-v1",
            list_version="sandbox-lists-v1",
        )
        self.db.add_all([auth, compliance])
        self._fact(order, "MESSAGE", "RECEIVED", "payment-message", {"message_type": message_type})
        self._fact(order, "AUTHORIZATION", "PENDING", auth.decision_id, {"decision_ref": auth.decision_id})
        self._fact(order, "COMPLIANCE", "PENDING", compliance.decision_id, {"decision_ref": compliance.decision_id})
        if entitlement is not None:
            self._fact(order, "ENTITLEMENT", "MATCHED", entitlement.entitlement_id, {"version": entitlement.version, "evidence_ref": entitlement.evidence_ref})
        self._fact(order, "FUNDING", "PENDING", "debit", {})
        self._fact(order, "FX", "NOT_APPLICABLE" if currency == settlement_currency else "PENDING", None, {})
        self._fact(order, "SETTLEMENT", "PENDING", "PAYMENT_VALUE", {})
        self._fact(order, "BENEFICIARY", "UNKNOWN", "beneficiary", {})
        self._fact(order, "RECONCILIATION", "UNMATCHED", "reconciliation", {})
        self.db.add(
            ProductionSettlementLeg(
                leg_id=f"leg_{uuid.uuid4().hex}",
                order_id=order.order_id,
                leg_role="PAYMENT_VALUE",
                connector="sandbox-value-settlement",
                currency=settlement_currency,
                amount_minor=amount_minor_value,
                finality_profile_id="sandbox-finality-v1",
            )
        )
        ProductionOutboxService(self.db).enqueue(
            "payment.created",
            order.order_id,
            {"order_id": order.order_id, "uetr": order.uetr, "currency": currency},
        )
        audit_payload = {"uetr": order.uetr, "payload_hash": order.payload_hash}
        if entitlement is not None:
            audit_payload["entitlement_id"] = entitlement.entitlement_id
            audit_payload["entitlement_version"] = entitlement.version
        ProductionAuditService(self.db).append("payment.created", order.order_id, audit_payload, principal.subject)
        response = self.serialize(order)
        ProductionIdempotencyService(self.db).complete(record, 202, response)
        self.db.flush()
        return response

    def create_fx_quote(
        self,
        principal: ProductionPrincipal,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        base_currency = str(payload.get("base_currency", "")).upper()
        quote_currency = str(payload.get("quote_currency", "")).upper()
        amount_minor_value = minor_amount(payload.get("base_amount"), base_currency)
        minor_amount("1", quote_currency)
        corridor = str(payload.get("corridor") or "CN-HK").upper()
        entitlement = assert_entitlement(
            self.db,
            principal,
            service="fx.quote",
            corridor=corridor,
            currency=base_currency,
            amount_minor=amount_minor_value,
        )
        assert_limit(
            self.db,
            principal,
            service="fx.quote",
            corridor=corridor,
            currency=base_currency,
            amount_minor=amount_minor_value,
        )
        scope = f"{principal.participant_id}:POST:/production/v1/fx-quotes"
        record, replay = ProductionIdempotencyService(self.db).begin(scope, idempotency_key, payload)
        if replay and record.status == "COMPLETED":
            return _json_load(record.response_body, {})
        result = SandboxFxQuoteProvider().request_quote(base_currency, quote_currency, amount_minor_value, corridor)
        evidence = result.evidence
        quote = ProductionFxQuote(
            quote_id=result.external_reference,
            participant_id=principal.participant_id,
            corridor=corridor,
            provider=result.connector,
            base_currency=base_currency,
            quote_currency=quote_currency,
            base_amount_minor=amount_minor_value,
            quote_amount_minor=int(evidence["quote_amount_minor"]),
            rate=str(evidence["rate"]),
            fee_minor=int(evidence["fee_minor"]),
            expires_at=dt.datetime.fromisoformat(evidence["expires_at"]),
            evidence_ref=ProductionEvidenceService(self.db).record(
                "fx.quote", result.external_reference, evidence, actor=principal.subject
            ).evidence_id,
        )
        self.db.add(quote)
        self.db.flush()
        response = {
            "quote_id": quote.quote_id,
            "provider": quote.provider,
            "base_currency": quote.base_currency,
            "quote_currency": quote.quote_currency,
            "base_amount": quote.base_amount_minor,
            "quote_amount": quote.quote_amount_minor,
            "rate": quote.rate,
            "fee_minor": quote.fee_minor,
            "expires_at": quote.expires_at,
            "mode": "simulation",
        }
        ProductionIdempotencyService(self.db).complete(record, 200, response)
        if entitlement is not None:
            ProductionAuditService(self.db).append("fx.quote.entitlement.matched", quote.quote_id, {"entitlement_id": entitlement.entitlement_id, "version": entitlement.version, "evidence_ref": entitlement.evidence_ref}, principal.subject)
        self.db.flush()
        return response

    def create_fx_acceptance(
        self,
        principal: ProductionPrincipal,
        order_id: str,
        quote_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        order = self.get_order(order_id, principal)
        if order.initiator_participant != principal.participant_id and not principal.can("production.admin"):
            raise ProductionConflict("Payment does not belong to the participant")
        quote = self.db.query(ProductionFxQuote).filter_by(quote_id=quote_id).one_or_none()
        if quote is None:
            raise ProductionConflict("Quote not found")
        if order.currency == order.settlement_currency:
            raise ProductionConflict("Same-currency payment cannot accept an FX quote")
        if quote.participant_id != principal.participant_id or quote.corridor != order.corridor:
            raise ProductionConflict("Quote is not owned by the payment participant/corridor")
        if order.currency != quote.base_currency or order.settlement_currency != quote.quote_currency:
            raise ProductionConflict("Quote currencies do not match payment settlement currencies")
        if _as_utc(quote.expires_at) <= utcnow() or quote.status != "QUOTED":
            quote.status = "EXPIRED"
            raise ProductionConflict("Quote is expired or unavailable")
        scope = f"{principal.participant_id}:POST:/production/v1/payments/{order_id}/fx-acceptance"
        request = {"order_id": order_id, "quote_id": quote_id}
        record, replay = ProductionIdempotencyService(self.db).begin(scope, idempotency_key, request)
        if replay and record.status == "COMPLETED":
            return _json_load(record.response_body, {})
        intent = ProductionFxTradeIntent(
            trade_intent_id=f"fxi_{uuid.uuid4().hex}",
            order_id=order.order_id,
            quote_id=quote.quote_id,
            idempotency_context=f"fx-accept-{uuid.uuid4().hex}",
            state="PREPARING",
        )
        self.db.add(intent)
        self.db.flush()
        reservation_ids: list[str] = []
        for currency, amount in (
            (order.currency, order.amount_minor),
            (quote.quote_currency, quote.quote_amount_minor),
        ):
            reservation = ProductionFundingReservation(
                reservation_id=f"res_{uuid.uuid4().hex}",
                reservation_intent_id=intent.trade_intent_id,
                order_id=order.order_id,
                funding_reference=f"{principal.participant_id}:{currency}",
                currency=currency,
                amount_minor=amount,
            )
            self.db.add(reservation)
            reservation_ids.append(reservation.reservation_id)
            ProductionOutboxService(self.db).enqueue(
                "funding.reserve.requested",
                reservation.reservation_id,
                {
                    "reservation_id": reservation.reservation_id,
                    "reservation_intent_id": intent.trade_intent_id,
                    "order_id": order.order_id,
                    "funding_reference": reservation.funding_reference,
                    "currency": currency,
                    "amount_minor": amount,
                },
            )
        intent.reservation_ids = json.dumps(reservation_ids, separators=(",", ":"))
        self._replace_fact(order.order_id, "FX", "ACCEPTANCE_PENDING", intent.trade_intent_id, {})
        response = {
            "trade_intent_id": intent.trade_intent_id,
            "order_id": order.order_id,
            "quote_id": quote.quote_id,
            "state": intent.state,
            "reservation_ids": reservation_ids,
        }
        ProductionIdempotencyService(self.db).complete(record, 202, response)
        self.db.flush()
        return response

    def request_cancellation(
        self,
        principal: ProductionPrincipal,
        order_id: str,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        order = self.get_order(order_id, principal)
        if order.orchestration_state in ORCHESTRATION_TERMINAL:
            raise ProductionConflict("Terminal payment cannot be cancelled")
        if order.initiator_participant != principal.participant_id and not principal.can("production.admin"):
            raise ProductionConflict("Payment does not belong to the participant")
        scope = f"{principal.participant_id}:POST:/production/v1/payments/{order_id}/cancellation"
        record, replay = ProductionIdempotencyService(self.db).begin(scope, idempotency_key, {"reason": reason})
        if replay and record.status == "COMPLETED":
            return _json_load(record.response_body, {})
        request = ProductionCancellationRequest(
            cancellation_request_id=f"can_{uuid.uuid4().hex}",
            order_id=order.order_id,
            reason=reason[:120],
            idempotency_context=f"cancel-{uuid.uuid4().hex}",
        )
        self.db.add(request)
        self._fact(order, "CANCELLATION", "REQUESTED", request.cancellation_request_id, {"reason": reason})
        ProductionOutboxService(self.db).enqueue(
            "payment.cancellation.requested",
            order.order_id,
            {"order_id": order.order_id, "cancellation_request_id": request.cancellation_request_id},
        )
        response = {"cancellation_request_id": request.cancellation_request_id, "state": request.state}
        ProductionIdempotencyService(self.db).complete(record, 202, response)
        self.db.flush()
        return response

    def request_return(
        self,
        principal: ProductionPrincipal,
        order_id: str,
        amount: str | int,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        order = self.get_order(order_id, principal)
        if order.initiator_participant != principal.participant_id and not principal.can("production.admin"):
            raise ProductionConflict("Payment does not belong to the participant")
        amount_minor_value = minor_amount(amount, order.currency)
        if order.customer_outcome != "COMPLETED":
            raise ProductionConflict("Only a completed payment can be returned")
        already_returned = sum(
            item.amount_minor
            for item in self.db.query(ProductionReturnPayment)
            .filter(
                ProductionReturnPayment.original_order_id == order.order_id,
                ProductionReturnPayment.state.in_(["REQUESTED", "ACCEPTED", "FINAL"]),
            )
            .all()
        )
        if already_returned + amount_minor_value > order.amount_minor:
            raise ProductionConflict("Return amount exceeds original payment")
        scope = f"{principal.participant_id}:POST:/production/v1/payments/{order_id}/return"
        request_body = {"amount": str(amount), "reason": reason}
        record, replay = ProductionIdempotencyService(self.db).begin(scope, idempotency_key, request_body)
        if replay and record.status == "COMPLETED":
            return _json_load(record.response_body, {})
        return_payment = ProductionReturnPayment(
            return_payment_id=f"ret_{uuid.uuid4().hex}",
            original_order_id=order.order_id,
            original_uetr=order.uetr,
            return_uetr=_uuid4(),
            amount_minor=amount_minor_value,
            currency=order.currency,
            reason=reason[:120],
            idempotency_context=f"return-{uuid.uuid4().hex}",
        )
        self.db.add(return_payment)
        self.db.flush()
        return_leg = ProductionSettlementLeg(
            leg_id=f"leg_{uuid.uuid4().hex}",
            order_id=order.order_id,
            leg_role=f"RETURN:{return_payment.return_payment_id}",
            connector="sandbox-value-settlement",
            currency=order.currency,
            amount_minor=amount_minor_value,
            finality_profile_id="sandbox-finality-v1",
        )
        self.db.add(return_leg)
        return_payment.return_leg_id = return_leg.leg_id
        self._fact(order, "RETURN", "REQUESTED", return_payment.return_payment_id, {"reason": reason, "return_uetr": return_payment.return_uetr})
        ProductionOutboxService(self.db).enqueue(
            "payment.return.requested",
            order.order_id,
            {"order_id": order.order_id, "return_payment_id": return_payment.return_payment_id},
        )
        response = {
            "return_payment_id": return_payment.return_payment_id,
            "return_leg_id": return_leg.leg_id,
            "state": return_payment.state,
        }
        ProductionIdempotencyService(self.db).complete(record, 202, response)
        self.db.flush()
        return response

    def get_order(self, order_id: str, principal: ProductionPrincipal | None = None) -> ProductionPaymentOrder:
        query = self.db.query(ProductionPaymentOrder).filter_by(order_id=order_id)
        if principal is not None:
            query = query.filter(ProductionPaymentOrder.tenant_id == principal.tenant_id)
        order = query.one_or_none()
        if order is None:
            raise ProductionConflict("Payment order not found")
        return order

    def serialize(self, order: ProductionPaymentOrder) -> dict[str, Any]:
        facts = self.db.query(ProductionPaymentFact).filter_by(order_id=order.order_id).all()
        return {
            "payment_id": order.order_id,
            "uetr": order.uetr,
            "instruction_id": order.instruction_id,
            "orchestration_state": order.orchestration_state,
            "customer_outcome": order.customer_outcome,
            "amount_minor": order.amount_minor,
            "currency": order.currency,
            "settlement_currency": order.settlement_currency,
            "corridor": order.corridor,
            "fact_summary": self.fact_summary(order, facts),
            "_links": {
                "self": f"/production/v1/payments/{order.order_id}",
                "facts": f"/production/v1/payments/{order.order_id}/facts",
                "cancellation": f"/production/v1/payments/{order.order_id}/cancellation-requests",
                "returns": f"/production/v1/payments/{order.order_id}/return-requests",
            },
            "created_at": order.created_at,
        }

    def fact_summary(
        self, order: ProductionPaymentOrder, facts: list[ProductionPaymentFact] | None = None
    ) -> dict[str, Any]:
        facts = facts if facts is not None else self.db.query(ProductionPaymentFact).filter_by(order_id=order.order_id).all()
        summary: dict[str, dict[str, Any]] = {}
        for fact in facts:
            entry = summary.setdefault(fact.fact_type.lower(), {"state_counts": {}, "latest": None})
            entry["state_counts"][fact.state] = entry["state_counts"].get(fact.state, 0) + 1
            entry["latest"] = {"state": fact.state, "reference": fact.reference}
        return {
            "projection_rule_version": order.projection_rule_version,
            "orchestration_state": order.orchestration_state,
            "facts": summary,
        }

    def facts(self, order_id: str) -> list[dict[str, Any]]:
        self.get_order(order_id)
        return [
            {
                "fact_id": fact.fact_id,
                "fact_type": fact.fact_type,
                "state": fact.state,
                "reference": fact.reference,
                "payload": _json_load(fact.payload, {}),
                "evidence_ref": fact.evidence_ref,
                "occurred_at": fact.occurred_at,
            }
            for fact in self.db.query(ProductionPaymentFact)
            .filter_by(order_id=order_id)
            .order_by(ProductionPaymentFact.id)
            .all()
        ]

    def _fact(
        self,
        order: ProductionPaymentOrder,
        fact_type: str,
        state: str,
        reference: str | None,
        payload: dict[str, Any],
    ) -> ProductionPaymentFact:
        fact = ProductionPaymentFact(
            fact_id=f"fact_{uuid.uuid4().hex}",
            order_id=order.order_id,
            fact_type=fact_type,
            state=state,
            reference=reference or f"{fact_type.lower()}-{uuid.uuid4().hex[:12]}",
            payload=canonical_json(payload),
        )
        self.db.add(fact)
        return fact

    def _replace_fact(
        self, order_id: str, fact_type: str, state: str, reference: str | None, payload: dict[str, Any]
    ) -> ProductionPaymentFact:
        existing = (
            self.db.query(ProductionPaymentFact)
            .filter_by(order_id=order_id, fact_type=fact_type, reference=reference)
            .order_by(ProductionPaymentFact.id.desc())
            .first()
        )
        order = self.get_order(order_id)
        if existing is None:
            return self._fact(order, fact_type, state, reference, payload)
        next_reference = f"{reference or fact_type.lower()}:{uuid.uuid4().hex[:12]}"
        next_fact = self._fact(
            order,
            fact_type,
            state,
            next_reference,
            {"supersedes_fact_id": existing.fact_id, **payload},
        )
        next_fact.supersedes_fact_id = existing.fact_id
        next_fact.evidence_ref = payload.get("evidence_id")
        return next_fact


def set_order_state(
    db: Session,
    order_id: str,
    state: str,
    outcome: str | None = None,
    *,
    expected_version: int | None = None,
) -> None:
    order = db.query(ProductionPaymentOrder).filter_by(order_id=order_id).one()
    if order.orchestration_state in ORCHESTRATION_TERMINAL:
        if order.orchestration_state == state:
            return
        raise ProductionConflict("Terminal payment state cannot transition")
    if state != order.orchestration_state and state not in ALLOWED_ORDER_TRANSITIONS.get(order.orchestration_state, set()):
        raise ProductionConflict(f"Invalid payment transition {order.orchestration_state} -> {state}")
    expected = order.version if expected_version is None else expected_version
    if order.version != expected:
        raise ProductionConflict("Payment version conflict")
    values = {"orchestration_state": state, "version": expected + 1, "updated_at": utcnow()}
    if outcome is not None:
        values["customer_outcome"] = outcome
    result = db.execute(update(ProductionPaymentOrder).where(ProductionPaymentOrder.order_id == order_id, ProductionPaymentOrder.version == expected).values(**values))
    if result.rowcount != 1:
        raise ProductionConflict("Payment version conflict")
    db.flush()
    if order.limit_reservation_id and state in ORCHESTRATION_TERMINAL:
        counter = db.query(ProductionLimitCounter).filter_by(counter_id=order.limit_reservation_id).with_for_update().one_or_none()
        if counter is not None:
            position = db.query(ProductionExposurePosition).filter_by(tenant_id=order.tenant_id, participant_id=order.initiator_participant, corridor=order.corridor, currency=order.currency).with_for_update().one_or_none()
            LimitReservationService(db).finalize(counter, position, order.amount_minor, consumed=state == "OPERATIONALLY_CLOSED" and outcome == "COMPLETED")
