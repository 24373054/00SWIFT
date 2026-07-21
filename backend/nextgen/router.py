"""Next-generation standards, payment lifecycle, CIPS and e-CNY API."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import require_admin_token
from database import get_db
from nextgen.cips import CipsService, EcnyOperatorService
from nextgen.payments import PaymentLifecycleError, PaymentService
from nextgen.runtime import IdempotencyConflict, IdempotencyService, OutboxService
from nextgen.standards import (
    build_iso20022_xml,
    finding_dicts,
    list_profiles,
    parse_iso20022_xml,
    run_conformance,
    validate_message,
)

router = APIRouter(prefix="/nextgen/v1", tags=["NextGen"])


class ValidateRequest(BaseModel):
    profile: str
    message_type: str
    payload: dict[str, Any] | None = None
    xml: str | None = None


class BuildRequest(BaseModel):
    message_type: str
    payload: dict[str, Any]


class Vector(BaseModel):
    name: str
    profile: str
    message_type: str
    payload: dict[str, Any]
    expected_valid: bool


class ConformanceRequest(BaseModel):
    vectors: list[Vector] = Field(min_length=1, max_length=1000)


class OutboxRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    aggregate_id: str = Field(min_length=1, max_length=120)
    payload: dict[str, Any]


class LifecycleCreate(BaseModel):
    uetr: str
    scenario: str = "CCT"
    original_uetr: str | None = None
    deadline_minutes: int = Field(default=120, ge=1, le=10080)


class LifecycleTransition(BaseModel):
    expected_version: int = Field(ge=1)
    status: str
    reason: str = ""


class TransactionCopyRequest(BaseModel):
    message_id: str
    message_type: str
    payload: dict[str, Any]
    source_party: str
    reason: str = ""


class CaseCreate(BaseModel):
    case_type: str
    owner: str
    details: dict[str, Any] = Field(default_factory=dict)
    sla_minutes: int = Field(default=240, ge=1, le=43200)


class CaseUpdate(BaseModel):
    status: str
    owner: str | None = None
    details: dict[str, Any] | None = None


class QualityRequest(BaseModel):
    profile: str
    message_type: str
    payload: dict[str, Any]


class ParticipantRequest(BaseModel):
    participant_id: str
    name: str
    participant_type: str
    country: str
    bic: str | None = None
    lei: str | None = None
    capabilities: list[str] = Field(default_factory=lambda: ["RTGS"])
    settlement_hours: dict[str, str] = Field(default_factory=dict)


class CipsAccountRequest(BaseModel):
    participant_id: str
    initial_balance: int = Field(default=0, ge=0)
    currency: str = "CNY"


class CipsSettlementRequest(BaseModel):
    uetr: str
    mode: str
    debtor_participant: str
    creditor_participant: str
    amount: int = Field(gt=0)
    priority: int = Field(default=5, ge=0, le=9)
    batch_id: str | None = None


class CipsPrevalidateRequest(BaseModel):
    message_type: str
    payload: dict[str, Any]


class OperatorRequest(BaseModel):
    operator_id: str
    name: str
    issuance_limit: int = Field(gt=0)
    reserve_amount: int = Field(default=0, ge=0)


class OperatorAmount(BaseModel):
    amount: int = Field(gt=0)


def _commit(db: Session, value: Any):
    db.commit()
    return value


@router.get("/standards/profiles")
def profiles():
    return {"profiles": list_profiles()}


@router.post("/standards/validate")
def validate(request: ValidateRequest):
    payload = request.payload
    if request.xml:
        payload = parse_iso20022_xml(request.xml)
    if payload is None:
        raise HTTPException(422, "payload or xml is required")
    findings = validate_message(request.profile, request.message_type, payload)
    return {
        "valid": not any(item.severity == "error" for item in findings),
        "findings": finding_dicts(findings),
    }


@router.post("/standards/build")
def build(request: BuildRequest):
    return {"xml": build_iso20022_xml(request.message_type, request.payload)}


@router.post("/standards/conformance")
def conformance(request: ConformanceRequest):
    return run_conformance([item.model_dump() for item in request.vectors])


@router.post("/runtime/outbox")
def enqueue_outbox(
    request: OutboxRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    idempotency = IdempotencyService(db)
    try:
        record, replay = idempotency.begin(idempotency_key, request.model_dump())
    except IdempotencyConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    if replay and record.status == "completed":
        return json.loads(record.response_body or "{}")
    event = OutboxService(db).enqueue(request.topic, request.aggregate_id, request.payload)
    response = {"event_id": event.event_id, "status": event.status, "replayed": replay}
    idempotency.complete(record, 200, response)
    return _commit(db, response)


@router.post("/payments")
def create_payment(
    request: LifecycleCreate,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        payment = PaymentService(db).create(**request.model_dump())
        response = {
            "uetr": payment.uetr,
            "status": payment.status,
            "version": payment.version,
            "deadline_at": payment.deadline_at,
        }
        return _commit(db, response)
    except (PaymentLifecycleError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/payments/{uetr}/transitions")
def transition_payment(
    uetr: str,
    request: LifecycleTransition,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        payment = PaymentService(db).transition(
            uetr,
            request.expected_version,
            request.status,
            request.reason,
        )
        return _commit(
            db,
            {"uetr": payment.uetr, "status": payment.status, "version": payment.version},
        )
    except PaymentLifecycleError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/payments/{uetr}/copies")
def append_copy(
    uetr: str,
    request: TransactionCopyRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        copy = PaymentService(db).append_transaction_copy(uetr, **request.model_dump())
        return _commit(
            db,
            {
                "message_id": copy.message_id,
                "payload_hash": copy.payload_hash,
                "previous_hash": copy.previous_hash,
            },
        )
    except PaymentLifecycleError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/payments/{uetr}/copy-integrity")
def copy_integrity(
    uetr: str,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    return {"uetr": uetr, "valid": PaymentService(db).verify_copy_chain(uetr)}


@router.post("/payments/{uetr}/cases")
def open_case(
    uetr: str,
    request: CaseCreate,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        payment_case = PaymentService(db).open_case(uetr, **request.model_dump())
        return _commit(
            db,
            {
                "case_id": payment_case.case_id,
                "status": payment_case.status,
                "deadline_at": payment_case.deadline_at,
            },
        )
    except PaymentLifecycleError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/cases/{case_id}/transitions")
def update_case(
    case_id: str,
    request: CaseUpdate,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        payment_case = PaymentService(db).update_case(case_id, **request.model_dump())
        return _commit(db, {"case_id": case_id, "status": payment_case.status})
    except PaymentLifecycleError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/payments/{uetr}/quality")
def assess_quality(
    uetr: str,
    request: QualityRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    metric = PaymentService(db).assess_quality(uetr, **request.model_dump())
    return _commit(
        db,
        {
            "completeness": metric.completeness,
            "validity": metric.validity,
            "consistency": metric.consistency,
            "integrity": metric.integrity,
        },
    )


@router.get("/payments/{uetr}/timeline")
def payment_timeline(
    uetr: str,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    return {
        "events": [
            {
                "system": event.system,
                "event_type": event.event_type,
                "status": event.status,
                "details": json.loads(event.details),
                "created_at": event.created_at,
            }
            for event in PaymentService(db).timeline(uetr)
        ]
    }


@router.post("/cips/participants")
def register_participant(
    request: ParticipantRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    participant = CipsService(db).register_participant(**request.model_dump())
    return _commit(db, {"participant_id": participant.participant_id})


@router.get("/cips/routes")
def cips_routes(
    destination_country: str,
    capability: str = "RTGS",
    destination_bic: str | None = None,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    return {
        "routes": CipsService(db).route_candidates(
            destination_country,
            capability,
            destination_bic,
        )
    }


@router.post("/cips/accounts")
def open_cips_account(
    request: CipsAccountRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    account = CipsService(db).open_account(**request.model_dump())
    return _commit(
        db,
        {"account_id": account.account_id, "balance": account.balance},
    )


@router.post("/cips/settlements")
def submit_cips_settlement(
    request: CipsSettlementRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    settlement = CipsService(db).submit_settlement(**request.model_dump())
    return _commit(
        db,
        {"settlement_id": settlement.settlement_id, "status": settlement.status},
    )


@router.post("/cips/rtgs/release")
def release_rtgs(
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    settled = CipsService(db).release_rtgs_queue()
    return _commit(db, {"settled": settled})


@router.post("/cips/dns/{batch_id}/settle")
def settle_dns(
    batch_id: str,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        net = CipsService(db).settle_dns_batch(batch_id)
        return _commit(db, {"batch_id": batch_id, "net_positions": net})
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/cips/prevalidate")
def cips_prevalidate(request: CipsPrevalidateRequest):
    return CipsService.__new__(CipsService).prevalidate(request.message_type, request.payload)


@router.post("/ecny/operators")
def register_operator(
    request: OperatorRequest,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    operator = EcnyOperatorService(db).register(**request.model_dump())
    return _commit(db, {"operator_id": operator.operator_id})


@router.post("/ecny/operators/{operator_id}/issue")
def issue_operator(
    operator_id: str,
    request: OperatorAmount,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        transaction = EcnyOperatorService(db).issue(operator_id, request.amount)
        return _commit(db, {"tx_id": transaction.tx_id, "status": transaction.status})
    except PaymentLifecycleError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/ecny/operators/{operator_id}/redeem")
def redeem_operator(
    operator_id: str,
    request: OperatorAmount,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    try:
        transaction = EcnyOperatorService(db).redeem(operator_id, request.amount)
        return _commit(db, {"tx_id": transaction.tx_id, "status": transaction.status})
    except PaymentLifecycleError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/ecny/operators/{operator_id}/reconciliation")
def reconcile_operator(
    operator_id: str,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    return EcnyOperatorService(db).reconcile(operator_id)
