"""Retail e-CNY, offline value, programmable money, multi-CBDC and PvP services."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import secrets
import uuid
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any

from sqlalchemy.orm import Session

from database import EcnyAccount, EcnyHolder, EcnyWallet
from ecny.ledger.engine import LedgerError, get_or_create_account, transfer

from .cips import EcnyOperatorService
from .models import (
    CbdcJurisdiction,
    CbdcNode,
    FxQuote,
    OfflineVoucher,
    ProgrammableInstrument,
    PvpSettlement,
    utcnow,
)
from .runtime import LeaseService, OutboxService

HK_RETAIL_LIMITS = {
    4: {"balance": 10_000_00, "single": 2_000_00, "daily": 5_000_00},
    3: {"balance": 50_000_00, "single": 10_000_00, "daily": 20_000_00},
    2: {"balance": 500_000_00, "single": 50_000_00, "daily": 100_000_00},
    1: {"balance": 5_000_000_00, "single": 500_000_00, "daily": 1_000_000_00},
}
PROGRAM_TEMPLATES = {
    "directed_subsidy",
    "merchant_category",
    "expiry",
    "staged_payment",
    "escrow_release",
    "conditional_refund",
    "multi_approval",
}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class RetailProfileError(ValueError):
    pass


class HkRetailService:
    """Synthetic Hong Kong cross-border retail profile.

    The service models public design characteristics only. It is not connected
    to FPS, an e-CNY operating institution, or the HKMA.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_wallet(
        self,
        operator_id: str,
        tier: int = 4,
        phone_hash: str | None = None,
        country_code: str = "HK",
    ) -> EcnyWallet:
        if tier not in HK_RETAIL_LIMITS:
            raise RetailProfileError("Unsupported HK retail wallet tier")
        wallet_id = str(uuid.uuid4())
        holder_id = str(uuid.uuid4())
        holder = EcnyHolder(
            holder_id=holder_id,
            wallet_id=wallet_id,
            id_type="phone_hash" if phone_hash else None,
            id_hash=phone_hash,
            kyc_level=max(0, 4 - tier),
            country_code=country_code,
        )
        wallet = EcnyWallet(
            wallet_id=wallet_id,
            holder_id=holder_id,
            tier=tier,
            operator_id=None,
            currency="CNY",
        )
        self.db.add_all([holder, wallet])
        get_or_create_account(self.db, f"acct-wallet-{wallet_id}", "wallet", wallet_id)
        self.db.flush()
        return wallet

    def fps_top_up(
        self,
        operator_id: str,
        wallet_id: str,
        amount: int,
        quote_id: str | None = None,
    ) -> dict[str, Any]:
        wallet = self._wallet(wallet_id)
        self._check_amount(wallet, amount)
        issuance = EcnyOperatorService(self.db).issue(operator_id, amount)
        operator_account = f"acct-operator-{operator_id}"
        wallet_account = f"acct-wallet-{wallet_id}"
        movement = transfer(
            self.db,
            operator_account,
            wallet_account,
            amount,
            {"profile": "ecny-hk-retail", "source": "FPS-simulation", "quote_id": quote_id},
        )
        self._check_balance(wallet)
        OutboxService(self.db).enqueue(
            "ecny.hk.topup",
            wallet_id,
            {"amount": amount, "issuance_tx": issuance.tx_id, "movement_tx": movement.tx_id},
        )
        return {"issuance_tx": issuance.tx_id, "movement_tx": movement.tx_id}

    def merchant_payment(
        self,
        wallet_id: str,
        merchant_wallet_id: str,
        amount: int,
        merchant_category: str,
    ):
        wallet = self._wallet(wallet_id)
        self._check_amount(wallet, amount)
        if not merchant_category:
            raise RetailProfileError("merchant_category is required")
        transaction = transfer(
            self.db,
            f"acct-wallet-{wallet_id}",
            f"acct-wallet-{merchant_wallet_id}",
            amount,
            {"profile": "ecny-hk-retail", "merchant_category": merchant_category},
        )
        OutboxService(self.db).enqueue(
            "ecny.hk.merchant_payment",
            wallet_id,
            {"amount": amount, "merchant_wallet_id": merchant_wallet_id},
        )
        return transaction

    def p2p_transfer(self, *_args, **_kwargs):
        raise RetailProfileError("Cross-border HK retail P2P is disabled by this profile")

    def _wallet(self, wallet_id: str) -> EcnyWallet:
        wallet = self.db.query(EcnyWallet).filter_by(wallet_id=wallet_id).first()
        if not wallet:
            raise RetailProfileError("wallet not found")
        if wallet.status != "active":
            raise RetailProfileError("wallet is not active")
        return wallet

    def _check_amount(self, wallet: EcnyWallet, amount: int) -> None:
        if amount <= 0 or amount > HK_RETAIL_LIMITS[wallet.tier]["single"]:
            raise RetailProfileError("single transaction limit exceeded")

    def _check_balance(self, wallet: EcnyWallet) -> None:
        account = self.db.query(EcnyAccount).filter_by(account_id=f"acct-wallet-{wallet.wallet_id}").one()
        if account.balance > HK_RETAIL_LIMITS[wallet.tier]["balance"]:
            raise RetailProfileError("wallet balance limit exceeded")


class OfflineValueService:
    def __init__(self, db: Session):
        self.db = db

    def issue(
        self,
        wallet_id: str,
        device_id: str,
        amount: int,
        ttl_minutes: int = 60,
    ) -> OfflineVoucher:
        if amount <= 0 or ttl_minutes <= 0:
            raise ValueError("Invalid offline amount or lifetime")
        voucher_id = f"offline-{uuid.uuid4().hex}"
        escrow = get_or_create_account(
            self.db,
            f"acct-offline-{voucher_id}",
            "offline_escrow",
            voucher_id,
        )
        transfer(
            self.db,
            f"acct-wallet-{wallet_id}",
            escrow.account_id,
            amount,
            {"purpose": "offline_reservation", "device_id": device_id},
        )
        voucher = OfflineVoucher(
            voucher_id=voucher_id,
            wallet_id=wallet_id,
            device_id=device_id,
            amount=amount,
            nonce=secrets.token_urlsafe(24),
            expires_at=utcnow() + dt.timedelta(minutes=ttl_minutes),
        )
        self.db.add(voucher)
        self.db.flush()
        return voucher

    def redeem(
        self,
        voucher_id: str,
        nonce: str,
        merchant_wallet_id: str,
    ):
        voucher = self.db.query(OfflineVoucher).filter_by(voucher_id=voucher_id).one()
        if voucher.status != "issued":
            raise ValueError("Voucher has already been consumed or invalidated")
        if voucher.expires_at < utcnow():
            voucher.status = "expired"
            raise ValueError("Voucher expired")
        if not secrets.compare_digest(voucher.nonce, nonce):
            raise ValueError("Invalid offline voucher nonce")
        transaction = transfer(
            self.db,
            f"acct-offline-{voucher_id}",
            f"acct-wallet-{merchant_wallet_id}",
            voucher.amount,
            {"purpose": "offline_redemption", "device_id": voucher.device_id},
        )
        voucher.status = "redeemed"
        voucher.redeemed_by = merchant_wallet_id
        OutboxService(self.db).enqueue(
            "ecny.offline.redeemed",
            voucher_id,
            {"merchant_wallet_id": merchant_wallet_id, "amount": voucher.amount},
        )
        self.db.flush()
        return transaction

    def invalidate(self, voucher_id: str, reason: str) -> None:
        voucher = self.db.query(OfflineVoucher).filter_by(voucher_id=voucher_id).one()
        if voucher.status != "issued":
            raise ValueError("Only issued vouchers may be invalidated")
        voucher.status = "invalidated"
        OutboxService(self.db).enqueue(
            "ecny.offline.invalidated",
            voucher_id,
            {"reason": reason},
        )
        self.db.flush()


class ProgrammableMoneyService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        owner_wallet: str,
        amount: int,
        template: str,
        conditions: dict[str, Any],
    ) -> ProgrammableInstrument:
        if template not in PROGRAM_TEMPLATES:
            raise ValueError("Unsupported programmable-money template")
        if amount <= 0:
            raise ValueError("amount must be positive")
        self._validate_conditions(template, conditions)
        instrument_id = f"program-{uuid.uuid4().hex}"
        escrow = get_or_create_account(
            self.db,
            f"acct-program-{instrument_id}",
            "program_escrow",
            instrument_id,
        )
        transfer(
            self.db,
            f"acct-wallet-{owner_wallet}",
            escrow.account_id,
            amount,
            {"template": template, "instrument_id": instrument_id},
        )
        instrument = ProgrammableInstrument(
            instrument_id=instrument_id,
            template=template,
            owner_wallet=owner_wallet,
            amount=amount,
            conditions=_json(conditions),
        )
        self.db.add(instrument)
        self.db.flush()
        return instrument

    def execute(
        self,
        instrument_id: str,
        destination_wallet: str,
        amount: int,
        context: dict[str, Any],
    ):
        instrument = (
            self.db.query(ProgrammableInstrument)
            .filter_by(instrument_id=instrument_id)
            .one()
        )
        if instrument.status != "active":
            raise ValueError("instrument is not active")
        if amount <= 0 or amount > instrument.amount:
            raise ValueError("invalid execution amount")
        conditions = json.loads(instrument.conditions)
        if not self._allows(instrument.template, conditions, amount, context):
            raise ValueError("programmable-money conditions are not satisfied")
        transaction = transfer(
            self.db,
            f"acct-program-{instrument_id}",
            f"acct-wallet-{destination_wallet}",
            amount,
            {"instrument_id": instrument_id, "template": instrument.template},
        )
        instrument.amount -= amount
        if instrument.amount == 0:
            instrument.status = "spent"
        self.db.flush()
        return transaction

    def refund(self, instrument_id: str):
        instrument = (
            self.db.query(ProgrammableInstrument)
            .filter_by(instrument_id=instrument_id)
            .one()
        )
        if instrument.status != "active":
            raise ValueError("instrument is not refundable")
        transaction = transfer(
            self.db,
            f"acct-program-{instrument_id}",
            f"acct-wallet-{instrument.owner_wallet}",
            instrument.amount,
            {"instrument_id": instrument_id, "purpose": "refund"},
        )
        instrument.amount = 0
        instrument.status = "refunded"
        self.db.flush()
        return transaction

    def _validate_conditions(self, template: str, conditions: dict[str, Any]) -> None:
        required = {
            "directed_subsidy": {"merchant_categories"},
            "merchant_category": {"merchant_categories"},
            "expiry": {"expires_at"},
            "staged_payment": {"max_release"},
            "escrow_release": {"approval_key"},
            "conditional_refund": {"condition_key"},
            "multi_approval": {"threshold", "approvers"},
        }[template]
        missing = required - conditions.keys()
        if missing:
            raise ValueError(f"Missing template conditions: {sorted(missing)}")

    def _allows(
        self,
        template: str,
        conditions: dict[str, Any],
        amount: int,
        context: dict[str, Any],
    ) -> bool:
        if template in {"directed_subsidy", "merchant_category"}:
            return context.get("merchant_category") in conditions["merchant_categories"]
        if template == "expiry":
            return utcnow() <= dt.datetime.fromisoformat(conditions["expires_at"])
        if template == "staged_payment":
            return amount <= int(conditions["max_release"])
        if template == "escrow_release":
            return bool(context.get(conditions["approval_key"]))
        if template == "conditional_refund":
            return bool(context.get(conditions["condition_key"]))
        if template == "multi_approval":
            approvals = set(context.get("approvals", [])) & set(conditions["approvers"])
            return len(approvals) >= int(conditions["threshold"])
        return False


class MultiCbdcService:
    def __init__(self, db: Session):
        self.db = db

    def register_jurisdiction(
        self,
        code: str,
        currency: str,
        central_bank: str,
        data_residency: str,
        policy: dict[str, Any] | None = None,
    ) -> CbdcJurisdiction:
        jurisdiction = CbdcJurisdiction(
            code=code,
            currency=currency,
            central_bank=central_bank,
            data_residency=data_residency,
            policy=_json(policy or {}),
        )
        self.db.add(jurisdiction)
        self.db.flush()
        return jurisdiction

    def register_node(
        self,
        node_id: str,
        jurisdiction: str,
        participant: str,
        role: str,
    ) -> CbdcNode:
        if role not in {"central_bank", "commercial_bank", "operator", "observer"}:
            raise ValueError("Unsupported multi-CBDC node role")
        if not self.db.query(CbdcJurisdiction).filter_by(code=jurisdiction, active=True).first():
            raise ValueError("Unknown or inactive jurisdiction")
        node = CbdcNode(
            node_id=node_id,
            jurisdiction=jurisdiction,
            participant=participant,
            role=role,
        )
        self.db.add(node)
        self.db.flush()
        return node

    def authorize_cross_border(
        self,
        source_jurisdiction: str,
        destination_jurisdiction: str,
        amount: int,
        purpose: str,
    ) -> dict[str, Any]:
        source = self.db.query(CbdcJurisdiction).filter_by(code=source_jurisdiction).one()
        destination = self.db.query(CbdcJurisdiction).filter_by(code=destination_jurisdiction).one()
        reasons = []
        for jurisdiction in (source, destination):
            policy = json.loads(jurisdiction.policy)
            max_amount = int(policy.get("max_cross_border_amount", 0))
            if max_amount and amount > max_amount:
                reasons.append(f"{jurisdiction.code}: amount exceeds policy")
            allowed = policy.get("allowed_purposes")
            if allowed and purpose not in allowed:
                reasons.append(f"{jurisdiction.code}: purpose not allowed")
        return {
            "allowed": not reasons,
            "reasons": reasons,
            "data_residency": [source.data_residency, destination.data_residency],
        }

    def create_quote(
        self,
        provider: str,
        base_currency: str,
        quote_currency: str,
        rate: str,
        max_amount: int,
        fee: int = 0,
        ttl_seconds: int = 60,
    ) -> FxQuote:
        try:
            parsed_rate = Decimal(rate)
        except InvalidOperation as exc:
            raise ValueError("Invalid FX rate") from exc
        if parsed_rate <= 0 or max_amount <= 0 or fee < 0 or ttl_seconds <= 0:
            raise ValueError("Invalid quote parameters")
        quote = FxQuote(
            quote_id=f"quote-{uuid.uuid4().hex}",
            provider=provider,
            base_currency=base_currency,
            quote_currency=quote_currency,
            rate=format(parsed_rate, "f"),
            fee=fee,
            max_amount=max_amount,
            expires_at=utcnow() + dt.timedelta(seconds=ttl_seconds),
        )
        self.db.add(quote)
        self.db.flush()
        return quote

    def quote_amount(self, quote_id: str, base_amount: int) -> int:
        quote = self._active_quote(quote_id, base_amount)
        converted = Decimal(base_amount) * Decimal(quote.rate)
        result = int(converted.quantize(Decimal("1"), rounding=ROUND_DOWN)) - quote.fee
        if result <= 0:
            raise ValueError("Quote produces a non-positive settlement amount")
        return result

    def create_pvp(
        self,
        quote_id: str,
        debit_leg: dict[str, Any],
        credit_leg: dict[str, Any],
    ) -> PvpSettlement:
        quote = self._active_quote(quote_id, int(debit_leg["amount"]))
        expected = self.quote_amount(quote.quote_id, int(debit_leg["amount"]))
        if int(credit_leg["amount"]) != expected:
            raise ValueError("Credit leg does not match the accepted quote")
        pvp = PvpSettlement(
            pvp_id=f"pvp-{uuid.uuid4().hex}",
            quote_id=quote_id,
            debit_leg=_json(debit_leg),
            credit_leg=_json(credit_leg),
        )
        self.db.add(pvp)
        self.db.flush()
        return pvp

    def lock_pvp(self, pvp_id: str, expected_version: int) -> PvpSettlement:
        pvp = self.db.query(PvpSettlement).filter_by(pvp_id=pvp_id).one()
        if pvp.version != expected_version or pvp.state != "CREATED":
            raise ValueError("PvP state or version conflict")
        debit = json.loads(pvp.debit_leg)
        credit = json.loads(pvp.credit_leg)
        self._active_quote(pvp.quote_id, int(debit["amount"]))
        for leg in (debit, credit):
            account = self.db.query(EcnyAccount).filter_by(account_id=leg["from_account"]).one()
            if account.currency != leg["currency"] or account.balance < int(leg["amount"]):
                raise ValueError("Insufficient or mismatched PvP source account")
        pvp.state = "LOCKED"
        pvp.version += 1
        self.db.flush()
        return pvp

    def commit_pvp(self, pvp_id: str, expected_version: int) -> PvpSettlement:
        pvp = self.db.query(PvpSettlement).filter_by(pvp_id=pvp_id).one()
        if pvp.version != expected_version or pvp.state != "LOCKED":
            raise ValueError("PvP state or version conflict")
        debit = json.loads(pvp.debit_leg)
        credit = json.loads(pvp.credit_leg)
        lease = LeaseService(self.db)
        resources = sorted({debit["from_account"], credit["from_account"]})
        locks: list[tuple[str, str]] = []
        owner = f"pvp-{pvp_id}"
        try:
            for resource in resources:
                locks.append((resource, lease.acquire(f"pvp-account:{resource}", owner)))
            self._active_quote(pvp.quote_id, int(debit["amount"]))
            with self.db.begin_nested():
                transfer(
                    self.db,
                    debit["from_account"],
                    debit["to_account"],
                    int(debit["amount"]),
                    {"pvp_id": pvp_id, "leg": "debit"},
                )
                transfer(
                    self.db,
                    credit["from_account"],
                    credit["to_account"],
                    int(credit["amount"]),
                    {"pvp_id": pvp_id, "leg": "credit"},
                )
            pvp.state = "COMMITTED"
            pvp.version += 1
            OutboxService(self.db).enqueue(
                "cbdc.pvp.committed",
                pvp_id,
                {"quote_id": pvp.quote_id},
            )
        except (LedgerError, ValueError) as exc:
            pvp.state = "ABORTED"
            pvp.failure_reason = str(exc)
            pvp.version += 1
        finally:
            for resource, token in reversed(locks):
                lease.release(f"pvp-account:{resource}", token)
        self.db.flush()
        return pvp

    def abort_pvp(self, pvp_id: str, reason: str) -> PvpSettlement:
        pvp = self.db.query(PvpSettlement).filter_by(pvp_id=pvp_id).one()
        if pvp.state == "COMMITTED":
            raise ValueError("Committed PvP settlement cannot be aborted")
        pvp.state = "ABORTED"
        pvp.failure_reason = reason
        pvp.version += 1
        self.db.flush()
        return pvp

    def _active_quote(self, quote_id: str, amount: int) -> FxQuote:
        quote = self.db.query(FxQuote).filter_by(quote_id=quote_id).one()
        if quote.status != "active" or quote.expires_at < utcnow():
            raise ValueError("FX quote is expired or inactive")
        if amount <= 0 or amount > quote.max_amount:
            raise ValueError("Amount exceeds quote capacity")
        return quote


def privacy_digest(value: str, salt: str) -> str:
    """Return a salted pseudonymous identifier for cross-jurisdiction exchange."""
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()
