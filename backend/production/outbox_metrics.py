from __future__ import annotations

import datetime as dt

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import ProductionOutboxEvent, utcnow


def snapshot(db: Session) -> dict[str, int | float | None]:
    now = utcnow()
    pending = db.query(func.count(ProductionOutboxEvent.id)).filter(ProductionOutboxEvent.status == "PENDING").scalar() or 0
    processing = db.query(func.count(ProductionOutboxEvent.id)).filter(ProductionOutboxEvent.status == "PROCESSING").scalar() or 0
    dead_letter = db.query(func.count(ProductionOutboxEvent.id)).filter(ProductionOutboxEvent.status == "DEAD_LETTER").scalar() or 0
    oldest = db.query(func.min(ProductionOutboxEvent.created_at)).filter(ProductionOutboxEvent.status.in_(("PENDING", "PROCESSING"))).scalar()
    oldest_age = None if oldest is None else max(0.0, (now - (oldest.replace(tzinfo=dt.UTC) if oldest.tzinfo is None else oldest)).total_seconds())
    retries = db.query(func.coalesce(func.sum(ProductionOutboxEvent.attempts), 0)).filter(ProductionOutboxEvent.attempts > 0).scalar() or 0
    return {"pending": pending, "processing": processing, "dead_letter": dead_letter, "oldest_event_age_seconds": oldest_age, "retry_attempts": retries}
