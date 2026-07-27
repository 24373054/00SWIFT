from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import ProductionOutboxEvent, ProductionReplayRequest, utcnow
from .security import ProductionPrincipal


def create_replay(db: Session, principal: ProductionPrincipal, event_id: str, reason: str) -> ProductionReplayRequest:
    event = db.query(ProductionOutboxEvent).filter_by(event_id=event_id, status="DEAD_LETTER", tenant_id=principal.tenant_id).one_or_none()
    if event is None:
        raise HTTPException(404, "dead-letter event not found")
    existing = db.query(ProductionReplayRequest).filter_by(event_id=event_id).one_or_none()
    if existing is not None:
        raise HTTPException(409, "replay already requested")
    request = ProductionReplayRequest(replay_id=f"replay_{uuid.uuid4().hex}", event_id=event.event_id, tenant_id=event.tenant_id, original_hash=event.payload_hash, maker=principal.subject, reason=reason, state="PENDING")
    db.add(request)
    db.commit()
    return request


def approve_replay(db: Session, principal: ProductionPrincipal, replay_id: str) -> ProductionReplayRequest:
    request = db.query(ProductionReplayRequest).filter_by(replay_id=replay_id, tenant_id=principal.tenant_id, state="PENDING").one_or_none()
    if request is None:
        raise HTTPException(404, "pending replay not found")
    if request.maker == principal.subject:
        raise HTTPException(409, "replay maker and checker must be distinct")
    request.checker = principal.subject
    request.state = "APPROVED"
    request.approved_at = utcnow()
    event = db.query(ProductionOutboxEvent).filter_by(event_id=request.event_id, status="DEAD_LETTER", payload_hash=request.original_hash).one_or_none()
    if event is None:
        raise HTTPException(409, "dead-letter payload changed")
    event.status = "PENDING"
    event.available_at = utcnow()
    event.lease_owner = None
    event.lease_until = None
    db.commit()
    return request
