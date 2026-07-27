from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from .models import ProductionPaymentTimer, utcnow

TIMER_TYPES = frozenset({"authorization", "compliance", "funding", "FX", "delivery", "settlement", "beneficiary", "reconciliation"})


class TimerService:
    def __init__(self, db: Session):
        self.db = db

    def schedule(self, order_id: str, timer_type: str, due_at: dt.datetime) -> ProductionPaymentTimer:
        if timer_type not in TIMER_TYPES:
            raise ValueError("unsupported payment timer type")
        timer = self.db.query(ProductionPaymentTimer).filter_by(order_id=order_id, timer_type=timer_type).one_or_none()
        if timer is not None:
            return timer
        timer = ProductionPaymentTimer(timer_id=f"tmr_{uuid.uuid4().hex}", order_id=order_id, timer_type=timer_type, due_at=due_at, state="SCHEDULED")
        self.db.add(timer)
        self.db.flush()
        return timer

    def claim_due(self, limit: int = 100) -> list[ProductionPaymentTimer]:
        rows = self.db.query(ProductionPaymentTimer).filter(ProductionPaymentTimer.state == "SCHEDULED", ProductionPaymentTimer.due_at <= utcnow()).with_for_update(skip_locked=True).limit(limit).all()
        for row in rows:
            row.state = "FIRED"
            row.attempts += 1
        self.db.flush()
        return rows
