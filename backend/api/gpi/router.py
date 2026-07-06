"""GPI Tracker v4 router — mounted at /swift-apitracker/v4.

5 endpoints (read paths need swift.apitracker/FullViewer; write paths need
swift.apitracker/Update + X-SWIFT-Signature). The invented /transition route
is removed (state moves via POST /payments/{uetr}/status).

Pydantic models use ``from_`` for the ``from`` field (Python keyword); an
alias makes the JSON wire name ``from``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import get_cred, require_scopes, require_signature
from database import get_db
from api.gpi import service

router = APIRouter(prefix="/swift-apitracker/v4", tags=["GPI Tracker"])


# Wire-name ``from`` -> Python ``from_`` (keyword-safe).
class _FromMixin(BaseModel):
    from_: str | None = Field(default=None, alias="from")

    model_config = {"populate_by_name": True}


class StatusConfirmation(_FromMixin):
    business_service: str | None = None
    instruction_identification: str | None = None
    transaction_status: str
    confirmed_amount_amount: str | None = None
    confirmed_amount_currency: str | None = None


class CancellationRequest(_FromMixin):
    business_service: str | None = None
    case_identification: str | None = None
    cancellation_reason: str = "DUPL"


class CancellationStatusReport(_FromMixin):
    business_service: str | None = None
    case_identification: str | None = None
    investigation_execution_status: str = "CNCL"


@router.get("/payments/{uetr}/transactions")
def get_payment_transactions(
    uetr: str,
    cred=Depends(get_cred),
    db: Session = Depends(get_db),
):
    """Get full payment transaction details for a UETR (CamtA0200205)."""
    return service.get_payment(db, uetr)


@router.get("/payments/changed/transactions")
def get_changed_transactions(
    from_date_time: str = Query(..., alias="from_date_time"),
    to_date_time: str = Query(..., alias="to_date_time"),
    maximum_number: int = Query(50, ge=1, le=200),
    payment_scenario: str | None = Query(None),
    cred=Depends(get_cred),
    db: Session = Depends(get_db),
):
    return service.list_changed_payments(db, from_date_time, to_date_time, maximum_number, payment_scenario)


@router.post("/payments/{uetr}/status", status_code=200)
def confirm_payment_status(
    uetr: str,
    body: StatusConfirmation,
    cred=Depends(get_cred),
    _sig=Depends(require_signature),
    db: Session = Depends(get_db),
):
    """Push a status confirmation (CamtA0100105). Requires signature + Update scope."""
    service.confirm_status(db, uetr, body.model_dump(by_alias=True, exclude_none=True))
    return {"uetr": uetr, "transaction_status": body.transaction_status}


@router.post("/payments/{uetr}/cancellation", status_code=200)
def request_cancellation(
    uetr: str,
    body: CancellationRequest,
    cred=Depends(get_cred),
    _sig=Depends(require_signature),
    db: Session = Depends(get_db),
):
    return service.request_cancellation(db, uetr, body.model_dump(by_alias=True, exclude_none=True))


@router.post("/payments/{uetr}/cancellation/status", status_code=200)
def report_cancellation_status(
    uetr: str,
    body: CancellationStatusReport,
    cred=Depends(get_cred),
    _sig=Depends(require_signature),
    db: Session = Depends(get_db),
):
    return service.report_cancellation_status(db, uetr, body.model_dump(by_alias=True, exclude_none=True))
