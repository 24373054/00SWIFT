"""Public production-domain API contracts."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from nextgen.standards import list_profiles, parse_iso20022_xml

from .connectors import connector_capabilities
from .integrity import require_request_integrity
from .ledger import ProductionLedgerService, serialize_account
from .models import (
    ProductionApproval,
    ProductionEntitlement,
    ProductionEvidenceManifest,
    ProductionInvestigationCase,
    ProductionLedgerAccount,
    ProductionLimitProfile,
    ProductionOutboxEvent,
    ProductionPaymentOrder,
    ProductionServiceIdentity,
    ProductionStandardArtifact,
    utcnow,
)
from .operations import operations_summary, reconciliation_report
from .reporting import build_regulatory_report
from .runtime import ProductionConflict, ProductionEvidenceService
from .security import ProductionPrincipal, ensure_participant, require_production_scope
from .service import ProductionPaymentService
from .standards import ensure_artifact, validate_and_record
from .telemetry import dependency_snapshot, health_snapshot
from .worker import ProductionWorker

router = APIRouter(prefix="/production/v1", tags=["Production Payment Domain"])


class PaymentCreateRequest(BaseModel):
    instruction_id: str = Field(min_length=1, max_length=200)
    message_type: str = Field(default="pacs.008", min_length=1, max_length=80)
    uetr: str | None = None
    corridor: str = Field(default="CN-HK", min_length=3, max_length=40)
    debtor: dict[str, Any]
    creditor: dict[str, Any]
    instructed_amount: dict[str, Any]
    settlement_currency: str | None = None
    purpose: dict[str, Any] = Field(default_factory=dict)
    authorization: dict[str, Any] = Field(default_factory=dict)
    remittance_information: dict[str, Any] = Field(default_factory=dict)
    quote_id: str | None = None


class QuoteRequest(BaseModel):
    base_currency: str = Field(min_length=3, max_length=3)
    quote_currency: str = Field(min_length=3, max_length=3)
    base_amount: str | int
    corridor: str = Field(default="CN-HK", min_length=3, max_length=40)


class FxAcceptanceRequest(BaseModel):
    quote_id: str = Field(min_length=1, max_length=80)


class CancellationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=120)


class ReturnRequest(BaseModel):
    amount: str | int
    reason: str = Field(min_length=1, max_length=120)


class ParticipantRequest(BaseModel):
    participant_id: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    participant_type: str = Field(default="BANK", min_length=2, max_length=40)
    jurisdiction: str = Field(default="CN", min_length=2, max_length=12)


class EntitlementRequest(BaseModel):
    counterparty_id: str = Field(min_length=2, max_length=80)
    direction: str = Field(default="OUTBOUND", min_length=2, max_length=12)
    service: str = Field(default="payment.create", min_length=2, max_length=80)
    message_type: str = "*"
    corridor: str = "*"
    currency: str = "*"
    approved_by: str = Field(min_length=1, max_length=200)


class StandardsValidateRequest(BaseModel):
    profile: str = Field(min_length=1, max_length=120)
    message_type: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any] | None = None
    xml: str | None = None


class LedgerAccountRequest(BaseModel):
    account_id: str = Field(min_length=2, max_length=100)
    legal_entity: str = Field(min_length=1, max_length=100)
    book: str = Field(min_length=1, max_length=100)
    currency: str = Field(min_length=3, max_length=3)
    account_type: str = Field(min_length=2, max_length=50)
    opening_balance_minor: int = Field(default=0, ge=0)


class JournalRequest(BaseModel):
    journal_id: str = Field(min_length=2, max_length=80)
    legal_entity: str = Field(min_length=1, max_length=100)
    book: str = Field(min_length=1, max_length=100)
    reason_code: str = Field(min_length=1, max_length=80)
    order_id: str | None = None
    entries: list[dict[str, Any]] = Field(min_length=2)


class InvestigationRequest(BaseModel):
    case_type: str = Field(default="PAYMENT_REVIEW", min_length=2, max_length=60)
    priority: str = Field(default="P2", min_length=2, max_length=20)
    reason: str = Field(min_length=1, max_length=500)
    owner: str | None = Field(default=None, max_length=120)


class ServiceIdentityRequest(BaseModel):
    participant_id: str = Field(min_length=2, max_length=80)
    credential_id: int | None = None
    certificate_fingerprint: str | None = Field(default=None, max_length=128)
    scopes: list[str] = Field(default_factory=lambda: ["production.read", "production.write"])
    environment: str = Field(default="sandbox", min_length=3, max_length=20)


class LimitProfileRequest(BaseModel):
    participant_id: str
    service: str = "payment.create"
    corridor: str = "*"
    currency: str = "*"
    max_amount_minor: int | None = Field(default=None, ge=1)
    daily_amount_minor: int | None = Field(default=None, ge=1)
    approved_by: str


class ApprovalRequest(BaseModel):
    aggregate_type: str
    aggregate_id: str
    action: str
    maker: str
    checker: str | None = None
    reason: str
    state: str = "APPROVED"


def _handle_conflict(exc: ProductionConflict) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": "PRODUCTION_CONFLICT", "message": str(exc)})


@router.get("/health")
def production_health(db: Session = Depends(get_db)) -> dict[str, Any]:
    capabilities = connector_capabilities()
    dependencies = dependency_snapshot(db)
    return {"status": "ok", "domain": "production", "connectors": capabilities, "observability": health_snapshot(), "dependencies": dependencies["checks"], "ready": dependencies["ready"]}


@router.post("/payments", status_code=202)
def create_payment(
    request: PaymentCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: ProductionPrincipal = Depends(require_production_scope("production.write")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    try:
        response = ProductionPaymentService(db).create_payment(
            principal, request.model_dump(exclude_none=True), idempotency_key
        )
        db.commit()
        return response
    except ProductionConflict as exc:
        db.rollback()
        raise _handle_conflict(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.get("/payments")
def list_payments(
    principal: ProductionPrincipal = Depends(require_production_scope("production.read")),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    state: str | None = None,
):
    query = db.query(ProductionPaymentOrder).filter(
        ProductionPaymentOrder.initiator_participant == principal.participant_id
    )
    if principal.can("production.admin"):
        query = db.query(ProductionPaymentOrder)
    if state:
        query = query.filter(ProductionPaymentOrder.orchestration_state == state)
    return {"items": [ProductionPaymentService(db).serialize(row) for row in query.order_by(ProductionPaymentOrder.id.desc()).limit(limit).all()]}


@router.get("/payments/{order_id}")
def get_payment(
    order_id: str,
    principal: ProductionPrincipal = Depends(require_production_scope("production.read")),
    db: Session = Depends(get_db),
):
    try:
        order = ProductionPaymentService(db).get_order(order_id)
        if order.initiator_participant != principal.participant_id and not principal.can("production.admin"):
            raise ProductionConflict("Payment does not belong to the participant")
        return ProductionPaymentService(db).serialize(order)
    except ProductionConflict as exc:
        raise _handle_conflict(exc) from exc


@router.get("/payments/{order_id}/facts")
def get_payment_facts(
    order_id: str,
    principal: ProductionPrincipal = Depends(require_production_scope("production.read")),
    db: Session = Depends(get_db),
):
    try:
        order = ProductionPaymentService(db).get_order(order_id)
        if order.initiator_participant != principal.participant_id and not principal.can("production.admin"):
            raise ProductionConflict("Payment does not belong to the participant")
        return {"payment_id": order_id, "facts": ProductionPaymentService(db).facts(order_id)}
    except ProductionConflict as exc:
        raise _handle_conflict(exc) from exc


@router.post("/payments/{order_id}/investigation-cases")
def open_investigation_case(
    order_id: str,
    request: InvestigationRequest,
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    order = ProductionPaymentService(db).get_order(order_id)
    if order.initiator_participant != principal.participant_id and not principal.can("production.admin"):
        raise _handle_conflict(ProductionConflict("Payment does not belong to the participant"))
    case = ProductionInvestigationCase(
        case_id=f"case_{uuid.uuid4().hex}",
        order_id=order_id,
        case_type=request.case_type,
        priority=request.priority,
        reason=request.reason,
        owner=request.owner,
    )
    db.add(case)
    db.commit()
    return {"case_id": case.case_id, "order_id": case.order_id, "state": case.state, "priority": case.priority}


@router.get("/investigation-cases")
def list_investigation_cases(
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
):
    query = db.query(ProductionInvestigationCase)
    if not principal.can("production.admin"):
        query = query.join(ProductionPaymentOrder, ProductionPaymentOrder.order_id == ProductionInvestigationCase.order_id).filter(ProductionPaymentOrder.initiator_participant == principal.participant_id)
    return {"items": [{"case_id": item.case_id, "order_id": item.order_id, "case_type": item.case_type, "state": item.state, "priority": item.priority, "owner": item.owner, "reason": item.reason} for item in query.order_by(ProductionInvestigationCase.id.desc()).all()]}


@router.post("/fx-quotes")
def request_quote(
    request: QuoteRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: ProductionPrincipal = Depends(require_production_scope("production.write")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    try:
        response = ProductionPaymentService(db).create_fx_quote(
            principal, request.model_dump(), idempotency_key
        )
        db.commit()
        return response
    except ProductionConflict as exc:
        db.rollback()
        raise _handle_conflict(exc) from exc


@router.post("/payments/{order_id}/fx-acceptance-intents", status_code=202)
def accept_quote(
    order_id: str,
    request: FxAcceptanceRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: ProductionPrincipal = Depends(require_production_scope("production.write")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    try:
        response = ProductionPaymentService(db).create_fx_acceptance(
            principal, order_id, request.quote_id, idempotency_key
        )
        db.commit()
        return response
    except ProductionConflict as exc:
        db.rollback()
        raise _handle_conflict(exc) from exc


@router.post("/payments/{order_id}/cancellation-requests", status_code=202)
def cancellation_request(
    order_id: str,
    request: CancellationRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: ProductionPrincipal = Depends(require_production_scope("production.write")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    try:
        response = ProductionPaymentService(db).request_cancellation(
            principal, order_id, request.reason, idempotency_key
        )
        db.commit()
        return response
    except ProductionConflict as exc:
        db.rollback()
        raise _handle_conflict(exc) from exc


@router.post("/payments/{order_id}/return-requests", status_code=202)
def return_request(
    order_id: str,
    request: ReturnRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: ProductionPrincipal = Depends(require_production_scope("production.write")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    try:
        response = ProductionPaymentService(db).request_return(
            principal, order_id, request.amount, request.reason, idempotency_key
        )
        db.commit()
        return response
    except ProductionConflict as exc:
        db.rollback()
        raise _handle_conflict(exc) from exc


@router.post("/participants")
def create_participant(
    request: ParticipantRequest,
    principal: ProductionPrincipal = Depends(require_production_scope("production.admin")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    del principal
    participant = ensure_participant(
        db,
        request.participant_id,
        name=request.name,
        participant_type=request.participant_type,
        jurisdiction=request.jurisdiction,
    )
    participant.status = "PENDING"
    db.commit()
    return {"participant_id": participant.participant_id, "status": participant.status}


@router.post("/participants/{participant_id}/entitlements")
def create_entitlement(
    participant_id: str,
    request: EntitlementRequest,
    principal: ProductionPrincipal = Depends(require_production_scope("production.admin")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    del principal
    ensure_participant(db, participant_id)
    entitlement = ProductionEntitlement(
        entitlement_id=f"ent_{uuid.uuid4().hex}",
        participant_id=participant_id,
        counterparty_id=request.counterparty_id,
        direction=request.direction,
        service=request.service,
        message_type=request.message_type,
        corridor=request.corridor,
        currency=request.currency,
        status="ACTIVE",
        approved_by=request.approved_by,
    )
    db.add(entitlement)
    db.commit()
    return {"entitlement_id": entitlement.entitlement_id, "status": entitlement.status}


@router.post("/service-identities")
def create_service_identity(
    request: ServiceIdentityRequest,
    principal: ProductionPrincipal = Depends(require_production_scope("production.admin")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    del principal
    ensure_participant(db, request.participant_id)
    identity = ProductionServiceIdentity(
        identity_id=f"sid_{uuid.uuid4().hex}",
        participant_id=request.participant_id,
        credential_id=request.credential_id,
        certificate_fingerprint=request.certificate_fingerprint,
        scopes=json.dumps(sorted(set(request.scopes)), separators=(",", ":")),
        environment=request.environment,
        status="ACTIVE" if request.environment == "sandbox" else "PENDING",
    )
    db.add(identity)
    db.commit()
    return {"identity_id": identity.identity_id, "participant_id": identity.participant_id, "status": identity.status, "scopes": request.scopes}


@router.post("/participants/{participant_id}/limit-profiles")
def create_limit_profile(
    participant_id: str,
    request: LimitProfileRequest,
    principal: ProductionPrincipal = Depends(require_production_scope("production.admin")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    del principal
    ensure_participant(db, participant_id)
    if request.participant_id != participant_id:
        raise HTTPException(400, "participant_id mismatch")
    profile = ProductionLimitProfile(profile_id=f"lim_{uuid.uuid4().hex}", **request.model_dump(), status="ACTIVE")
    db.add(profile)
    db.commit()
    return {"profile_id": profile.profile_id, "status": profile.status}


@router.post("/approvals")
def create_approval(
    request: ApprovalRequest,
    principal: ProductionPrincipal = Depends(require_production_scope("production.admin")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    if request.maker == (principal.subject or "") and request.checker == request.maker:
        raise HTTPException(409, "Maker and checker must be distinct")
    approval = ProductionApproval(approval_id=f"apr_{uuid.uuid4().hex}", **request.model_dump())
    if approval.state == "APPROVED" and not approval.checker:
        raise HTTPException(422, "checker is required for APPROVED state")
    approval.approved_at = utcnow() if approval.state == "APPROVED" else None
    db.add(approval)
    db.commit()
    return {"approval_id": approval.approval_id, "state": approval.state}


@router.get("/outbox")
def list_outbox(
    status: str | None = None,
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
):
    del principal
    query = db.query(ProductionOutboxEvent)
    if status:
        query = query.filter_by(status=status)
    return {"items": [{"event_id": e.event_id, "topic": e.topic, "status": e.status, "attempts": e.attempts, "lease_until": e.lease_until, "last_error": e.last_error} for e in query.order_by(ProductionOutboxEvent.id.desc()).limit(500).all()]}


@router.post("/ledger/trial-balance")
def ledger_trial_balance(
    currency: str | None = None,
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
):
    del principal
    return ProductionLedgerService(db).trial_balance(currency)


@router.post("/worker/run")
def run_worker(
    principal: ProductionPrincipal = Depends(require_production_scope("production.worker")),
    db: Session = Depends(get_db),
):
    del principal
    return ProductionWorker(db).run_once()


@router.get("/operations/summary")
def operations_summary_route(
    principal: ProductionPrincipal = Depends(require_production_scope("production.read")),
    db: Session = Depends(get_db),
):
    del principal
    return operations_summary(db)


@router.post("/reconciliation/runs")
def reconciliation_run(
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    del principal
    report = reconciliation_report(db)
    db.commit()
    return report


@router.get("/ledger/accounts")
def ledger_accounts(
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
):
    del principal
    return {"items": [serialize_account(item) for item in db.query(ProductionLedgerAccount).order_by(ProductionLedgerAccount.account_id).all()]}


@router.post("/ledger/accounts")
def ledger_account_create(
    request: LedgerAccountRequest,
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    del principal
    try:
        account = ProductionLedgerService(db).create_account(**request.model_dump())
        db.commit()
        return serialize_account(account)
    except ProductionConflict as exc:
        db.rollback()
        raise _handle_conflict(exc) from exc


@router.post("/ledger/journals")
def ledger_journal_create(
    request: JournalRequest,
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    del principal
    try:
        journal = ProductionLedgerService(db).post_journal(**request.model_dump())
        db.commit()
        return {"journal_id": journal.journal_id, "state": journal.state, "payload_hash": journal.payload_hash}
    except ProductionConflict as exc:
        db.rollback()
        raise _handle_conflict(exc) from exc


@router.get("/evidence/{evidence_id}")
def evidence_get(
    evidence_id: str,
    principal: ProductionPrincipal = Depends(require_production_scope("production.read")),
    db: Session = Depends(get_db),
):
    del principal
    evidence = db.query(ProductionEvidenceManifest).filter_by(evidence_id=evidence_id).one_or_none()
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return {
        "evidence_id": evidence.evidence_id,
        "evidence_type": evidence.evidence_type,
        "aggregate_id": evidence.aggregate_id,
        "content_hash": evidence.content_hash,
        "previous_hash": evidence.previous_hash,
        "storage_uri": evidence.storage_uri,
        "retention_class": evidence.retention_class,
        "legal_hold": evidence.legal_hold,
        "metadata": evidence.metadata_json,
        "created_at": evidence.created_at,
    }


@router.get("/reporting/reports")
def regulatory_report(
    report_type: str = Query(default="payment-activity-v1", min_length=2, max_length=80),
    business_date: str | None = Query(default=None),
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
):
    del principal
    try:
        return build_regulatory_report(db, report_type, business_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_BUSINESS_DATE", "message": str(exc)}) from exc


@router.post("/evidence/{evidence_id}/legal-hold")
def evidence_legal_hold(
    evidence_id: str,
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    del principal
    evidence = db.query(ProductionEvidenceManifest).filter_by(evidence_id=evidence_id).one_or_none()
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    evidence.legal_hold = True
    db.commit()
    return {"evidence_id": evidence.evidence_id, "legal_hold": evidence.legal_hold}


@router.get("/standards/profiles")
def production_standard_profiles(
    principal: ProductionPrincipal = Depends(require_production_scope("production.read")),
):
    del principal
    return {"profiles": list_profiles()}


@router.post("/standards/validate")
def production_validate_standard_message(
    request: StandardsValidateRequest,
    principal: ProductionPrincipal = Depends(require_production_scope("production.write")),
    db: Session = Depends(get_db),
    _integrity: None = Depends(require_request_integrity),
):
    del principal
    if request.payload is None and request.xml is None:
        raise HTTPException(status_code=422, detail="payload or xml is required")
    try:
        payload = request.payload if request.payload is not None else parse_iso20022_xml(request.xml or "")
        if db.query(ProductionStandardArtifact).filter_by(profile=request.profile, message_type=request.message_type, status="ACTIVE").first() is None:
            ensure_artifact(db, profile=request.profile, message_type=request.message_type, simulation_only=True)
        result = validate_and_record(db, profile=request.profile, message_type=request.message_type, payload=payload)
        findings = result["findings"]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STANDARDS_REQUEST", "message": str(exc)}) from exc
    evidence = ProductionEvidenceService(db).record(
        "standards.validation",
        f"{request.profile}:{request.message_type}",
        {"profile": request.profile, "message_type": request.message_type, "findings": findings},
    )
    db.commit()
    return {
        "profile": request.profile,
        "message_type": request.message_type,
        "valid": not any(item["severity"].lower() == "error" for item in findings),
        "findings": findings,
        "validator_mode": "sandbox-registry-rule-engine",
        "artifact_id": result["artifact_id"],
        "evidence_id": evidence.evidence_id,
    }
