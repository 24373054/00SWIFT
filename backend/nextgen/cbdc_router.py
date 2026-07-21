"""API routes for retail e-CNY, offline value, programmable money and multi-CBDC PvP."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import require_admin_token
from database import get_db
from nextgen.cbdc import (
    HkRetailService,
    MultiCbdcService,
    OfflineValueService,
    ProgrammableMoneyService,
    RetailProfileError,
    privacy_digest,
)
from nextgen.platform import (
    AuditChainService,
    LocalKeyProvider,
    PolicyEngine,
    ReconciliationService,
)

router = APIRouter(prefix="/nextgen/v1", tags=["NextGen CBDC"])


class HkWalletRequest(BaseModel):
    operator_id: str
    tier: int = Field(default=4, ge=1, le=4)
    phone_hash: str | None = None
    country_code: str = "HK"


class TopUpRequest(BaseModel):
    operator_id: str
    amount: int = Field(gt=0)
    quote_id: str | None = None


class MerchantPaymentRequest(BaseModel):
    merchant_wallet_id: str
    amount: int = Field(gt=0)
    merchant_category: str


class OfflineIssueRequest(BaseModel):
    wallet_id: str
    device_id: str
    amount: int = Field(gt=0)
    ttl_minutes: int = Field(default=60, ge=1, le=10080)


class OfflineRedeemRequest(BaseModel):
    nonce: str
    merchant_wallet_id: str


class ProgramCreateRequest(BaseModel):
    owner_wallet: str
    amount: int = Field(gt=0)
    template: str
    conditions: dict[str, Any]


class ProgramExecuteRequest(BaseModel):
    destination_wallet: str
    amount: int = Field(gt=0)
    context: dict[str, Any] = Field(default_factory=dict)


class JurisdictionRequest(BaseModel):
    code: str
    currency: str
    central_bank: str
    data_residency: str
    policy: dict[str, Any] = Field(default_factory=dict)


class NodeRequest(BaseModel):
    node_id: str
    jurisdiction: str
    participant: str
    role: str


class AuthorizationRequest(BaseModel):
    source_jurisdiction: str
    destination_jurisdiction: str
    amount: int = Field(gt=0)
    purpose: str


class QuoteRequest(BaseModel):
    provider: str
    base_currency: str
    quote_currency: str
    rate: str
    max_amount: int = Field(gt=0)
    fee: int = Field(default=0, ge=0)
    ttl_seconds: int = Field(default=60, ge=1, le=86400)


class PvpRequest(BaseModel):
    quote_id: str
    debit_leg: dict[str, Any]
    credit_leg: dict[str, Any]


class VersionRequest(BaseModel):
    expected_version: int = Field(ge=1)


class AbortRequest(BaseModel):
    reason: str


class PolicyRequest(BaseModel):
    subject: str
    action: str
    resource: str
    context: dict[str, Any]
    policy: dict[str, Any]


class CryptoRequest(BaseModel):
    key_id: str
    payload: str


class VerifyRequest(CryptoRequest):
    signature: str


def _commit(db: Session, value: Any):
    db.commit()
    return value


@router.post("/hk-retail/wallets")
def create_hk_wallet(
    request: HkWalletRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    wallet = HkRetailService(db).create_wallet(**request.model_dump())
    return _commit(db, {"wallet_id": wallet.wallet_id, "tier": wallet.tier})


@router.post("/hk-retail/wallets/{wallet_id}/top-up")
def top_up_hk_wallet(
    wallet_id: str,
    request: TopUpRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        return _commit(db, HkRetailService(db).fps_top_up(wallet_id=wallet_id, **request.model_dump()))
    except (RetailProfileError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/hk-retail/wallets/{wallet_id}/merchant-payment")
def hk_merchant_payment(
    wallet_id: str,
    request: MerchantPaymentRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        tx = HkRetailService(db).merchant_payment(wallet_id=wallet_id, **request.model_dump())
        return _commit(db, {"tx_id": tx.tx_id, "status": tx.status})
    except (RetailProfileError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/offline/vouchers")
def issue_offline_voucher(
    request: OfflineIssueRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    voucher = OfflineValueService(db).issue(**request.model_dump())
    return _commit(
        db,
        {
            "voucher_id": voucher.voucher_id,
            "nonce": voucher.nonce,
            "expires_at": voucher.expires_at,
        },
    )


@router.post("/offline/vouchers/{voucher_id}/redeem")
def redeem_offline_voucher(
    voucher_id: str,
    request: OfflineRedeemRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        tx = OfflineValueService(db).redeem(voucher_id=voucher_id, **request.model_dump())
        return _commit(db, {"tx_id": tx.tx_id, "status": tx.status})
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/programmable/instruments")
def create_programmable_instrument(
    request: ProgramCreateRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    instrument = ProgrammableMoneyService(db).create(**request.model_dump())
    return _commit(db, {"instrument_id": instrument.instrument_id, "status": instrument.status})


@router.post("/programmable/instruments/{instrument_id}/execute")
def execute_programmable_instrument(
    instrument_id: str,
    request: ProgramExecuteRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        tx = ProgrammableMoneyService(db).execute(instrument_id=instrument_id, **request.model_dump())
        return _commit(db, {"tx_id": tx.tx_id, "status": tx.status})
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/cbdc/jurisdictions")
def register_jurisdiction(
    request: JurisdictionRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    jurisdiction = MultiCbdcService(db).register_jurisdiction(**request.model_dump())
    return _commit(db, {"code": jurisdiction.code})


@router.post("/cbdc/nodes")
def register_cbdc_node(
    request: NodeRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    node = MultiCbdcService(db).register_node(**request.model_dump())
    return _commit(db, {"node_id": node.node_id})


@router.post("/cbdc/authorize")
def authorize_cbdc_payment(
    request: AuthorizationRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    return MultiCbdcService(db).authorize_cross_border(**request.model_dump())


@router.post("/fx/quotes")
def create_fx_quote(
    request: QuoteRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    quote = MultiCbdcService(db).create_quote(**request.model_dump())
    return _commit(
        db,
        {"quote_id": quote.quote_id, "rate": quote.rate, "expires_at": quote.expires_at},
    )


@router.post("/pvp")
def create_pvp(
    request: PvpRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    pvp = MultiCbdcService(db).create_pvp(**request.model_dump())
    return _commit(db, {"pvp_id": pvp.pvp_id, "state": pvp.state, "version": pvp.version})


@router.post("/pvp/{pvp_id}/lock")
def lock_pvp(
    pvp_id: str,
    request: VersionRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    pvp = MultiCbdcService(db).lock_pvp(pvp_id, request.expected_version)
    return _commit(db, {"pvp_id": pvp.pvp_id, "state": pvp.state, "version": pvp.version})


@router.post("/pvp/{pvp_id}/commit")
def commit_pvp(
    pvp_id: str,
    request: VersionRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    pvp = MultiCbdcService(db).commit_pvp(pvp_id, request.expected_version)
    return _commit(
        db,
        {
            "pvp_id": pvp.pvp_id,
            "state": pvp.state,
            "version": pvp.version,
            "failure_reason": pvp.failure_reason,
        },
    )


@router.post("/policy/evaluate")
def evaluate_policy(
    request: PolicyRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    decision = PolicyEngine(db).evaluate(**request.model_dump())
    AuditChainService(db).append(
        "policy.decision",
        decision.decision_id,
        {"result": decision.result, "reasons": decision.reasons},
    )
    return _commit(
        db,
        {
            "decision_id": decision.decision_id,
            "result": decision.result,
            "reasons": decision.reasons,
        },
    )


@router.post("/kms/sign")
def kms_sign(request: CryptoRequest, _: None = Depends(require_admin_token)):
    signature = LocalKeyProvider().sign(request.key_id, request.payload.encode())
    return {"signature": signature.hex()}


@router.post("/kms/verify")
def kms_verify(request: VerifyRequest, _: None = Depends(require_admin_token)):
    try:
        signature = bytes.fromhex(request.signature)
    except ValueError as exc:
        raise HTTPException(422, "signature must be hexadecimal") from exc
    valid = LocalKeyProvider().verify(request.key_id, request.payload.encode(), signature)
    return {"valid": valid}


@router.get("/reconciliation")
def reconcile_platform(
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    return _commit(db, ReconciliationService(db).run())


@router.get("/audit/integrity")
def audit_integrity(
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    return {"valid": AuditChainService(db).verify()}


@router.get("/privacy/digest/{value}")
def pseudonymous_digest(
    value: str,
    salt: str,
    _: None = Depends(require_admin_token),
):
    return {"digest": privacy_digest(value, salt)}
