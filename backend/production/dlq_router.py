from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db

from .dlq_replay import approve_replay, create_replay
from .models import ProductionOutboxEvent
from .security import ProductionPrincipal, require_production_scope

dlq_router = APIRouter(prefix="/production/v1")


@dlq_router.post("/dlq/{event_id}/replay")
def request_replay(event_id: str, reason: str, principal: ProductionPrincipal = Depends(require_production_scope("production.operator")), db: Session = Depends(get_db)):
    request = create_replay(db, principal, event_id, reason)
    return {"replay_id": request.replay_id, "state": request.state, "event_id": request.event_id}


@dlq_router.post("/dlq/replays/{replay_id}/approve")
def approve_replay_request(replay_id: str, principal: ProductionPrincipal = Depends(require_production_scope("production.operator")), db: Session = Depends(get_db)):
    request = approve_replay(db, principal, replay_id)
    return {"replay_id": request.replay_id, "state": request.state, "checker": request.checker}


@dlq_router.get("/dlq")
def list_dlq(
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
):
    rows = db.query(ProductionOutboxEvent).filter_by(status="DEAD_LETTER", tenant_id=principal.tenant_id).order_by(ProductionOutboxEvent.id.desc()).limit(500).all()
    return {"items": [{"event_id": row.event_id, "topic": row.topic, "tenant_id": row.tenant_id, "attempts": row.attempts, "last_error": row.last_error, "payload_hash": row.payload_hash} for row in rows]}


@dlq_router.get("/dlq/{event_id}")
def get_dlq(
    event_id: str,
    principal: ProductionPrincipal = Depends(require_production_scope("production.operator")),
    db: Session = Depends(get_db),
):
    row = db.query(ProductionOutboxEvent).filter_by(event_id=event_id, status="DEAD_LETTER", tenant_id=principal.tenant_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="dead-letter event not found")
    return {"event_id": row.event_id, "topic": row.topic, "tenant_id": row.tenant_id, "payload": row.payload, "payload_hash": row.payload_hash, "attempts": row.attempts, "last_error": row.last_error, "broker_metadata": row.broker_metadata}
