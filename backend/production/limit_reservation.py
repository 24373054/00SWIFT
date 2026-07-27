"""Atomic row-locked limit and FX exposure reservations."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from .models import ProductionExposurePosition, ProductionLimitCounter


class LimitReservationError(ValueError):
    pass


class LimitReservationService:
    def __init__(self, db: Session):
        self.db = db

    def reserve(self, *, tenant_id: str, participant_id: str, service: str, corridor: str, currency: str, business_date: dt.date, amount_minor: int, daily_limit_minor: int | None, exposure_limit_minor: int | None) -> tuple[ProductionLimitCounter, ProductionExposurePosition | None]:
        if amount_minor <= 0:
            raise LimitReservationError("reservation amount must be positive")
        counter = self.db.query(ProductionLimitCounter).filter_by(tenant_id=tenant_id, participant_id=participant_id, service=service, corridor=corridor, currency=currency, business_date=business_date.isoformat()).with_for_update().one_or_none()
        if counter is None:
            counter = ProductionLimitCounter(counter_id=f"limc_{uuid.uuid4().hex}", tenant_id=tenant_id, participant_id=participant_id, service=service, corridor=corridor, currency=currency, business_date=business_date.isoformat())
            self.db.add(counter)
            self.db.flush()
        projected = counter.reserved_amount_minor + counter.consumed_amount_minor + amount_minor
        if daily_limit_minor is not None and projected > daily_limit_minor:
            raise LimitReservationError("daily limit exceeded")
        position = None
        if exposure_limit_minor is not None:
            position = self.db.query(ProductionExposurePosition).filter_by(tenant_id=tenant_id, participant_id=participant_id, corridor=corridor, currency=currency).with_for_update().one_or_none()
            if position is None:
                position = ProductionExposurePosition(position_id=f"exp_{uuid.uuid4().hex}", tenant_id=tenant_id, participant_id=participant_id, corridor=corridor, currency=currency)
                self.db.add(position)
                self.db.flush()
            if position.exposure_minor + amount_minor > exposure_limit_minor:
                raise LimitReservationError("exposure limit exceeded")
            position.exposure_minor += amount_minor
            position.version += 1
        counter.reserved_amount_minor += amount_minor
        counter.version += 1
        self.db.flush()
        return counter, position

    def release(self, counter: ProductionLimitCounter, position: ProductionExposurePosition | None, amount_minor: int) -> None:
        if amount_minor <= 0 or counter.reserved_amount_minor < amount_minor:
            raise LimitReservationError("invalid release amount")
        counter.reserved_amount_minor -= amount_minor
        counter.version += 1
        if position is not None:
            if position.exposure_minor < amount_minor:
                raise LimitReservationError("invalid exposure release amount")
            position.exposure_minor -= amount_minor
            position.version += 1
        self.db.flush()

    def finalize(self, counter: ProductionLimitCounter, position: ProductionExposurePosition | None, amount_minor: int, *, consumed: bool) -> None:
        if amount_minor <= 0 or counter.reserved_amount_minor < amount_minor:
            raise LimitReservationError("invalid finalization amount")
        counter.reserved_amount_minor -= amount_minor
        if consumed:
            counter.consumed_amount_minor += amount_minor
        counter.version += 1
        if position is not None:
            if position.exposure_minor < amount_minor:
                raise LimitReservationError("invalid exposure finalization amount")
            position.exposure_minor -= amount_minor
            position.version += 1
        self.db.flush()
