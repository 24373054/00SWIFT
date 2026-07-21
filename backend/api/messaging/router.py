"""Messaging API router — mounted at /alliancecloud/v2.

P1 endpoints: POST /fin/messages (send), GET /distributions (inbox),
POST /distributions/{id}/acks | /naks. Send/ack/nak require
X-SWIFT-Signature.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.messaging import service
from api.messaging.schemas import AckNakRequest, FinMessageEmission
from auth.dependencies import get_cred, require_scopes, require_signature
from database import get_db

router = APIRouter(
    prefix="/alliancecloud/v2",
    tags=["Messaging"],
    dependencies=[Depends(get_cred), Depends(require_scopes("swift.messaging"))],
)


@router.post("/fin/messages", status_code=201)
def send_fin_message(
    body: FinMessageEmission,
    cred=Depends(get_cred),
    _sig=Depends(require_signature),
    db: Session = Depends(get_db),
):
    return service.send_fin_message(db, body.model_dump())


@router.get("/distributions")
def list_distributions(
    limit: int = Query(50, ge=1, le=200),
    cred=Depends(get_cred),
    db: Session = Depends(get_db),
):
    return {"distributions": service.list_distributions(db, limit)}


@router.post("/distributions/{distribution_id}/acks", status_code=204)
def ack_distribution(
    distribution_id: str,
    cred=Depends(get_cred),
    _sig=Depends(require_signature),
    db: Session = Depends(get_db),
):
    service.ack_distribution(db, distribution_id)
    return None


@router.post("/distributions/{distribution_id}/naks", status_code=204)
def nak_distribution(
    distribution_id: str,
    body: AckNakRequest,
    cred=Depends(get_cred),
    _sig=Depends(require_signature),
    db: Session = Depends(get_db),
):
    service.nak_distribution(db, distribution_id, body.reason)
    return None
