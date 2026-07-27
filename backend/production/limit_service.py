"""Limit policy evaluation separated from atomic counter reservation."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from .models import ProductionLimitProfile, utcnow


class LimitError(ValueError):
    pass


class LimitService:
    def __init__(self, db: Session):
        self.db = db

    def profile(self, *, participant_id: str, service: str, corridor: str, currency: str, now: dt.datetime | None = None) -> ProductionLimitProfile:
        current = now or utcnow()
        profile = self.db.query(ProductionLimitProfile).filter(ProductionLimitProfile.participant_id == participant_id, ProductionLimitProfile.service == service, ProductionLimitProfile.status == "ACTIVE", ProductionLimitProfile.effective_from <= current, (ProductionLimitProfile.effective_to.is_(None) | (ProductionLimitProfile.effective_to >= current)), ProductionLimitProfile.corridor.in_(["*", corridor]), ProductionLimitProfile.currency.in_(["*", currency.upper()])).order_by(ProductionLimitProfile.id.desc()).first()
        if profile is None:
            raise LimitError("active limit profile is required")
        return profile

    def assert_amount(self, profile: ProductionLimitProfile, amount_minor: int, *, exposure_minor: int = 0) -> None:
        if amount_minor <= 0:
            raise LimitError("amount must be positive")
        if profile.max_amount_minor is not None and amount_minor > profile.max_amount_minor:
            raise LimitError("single transaction limit exceeded")
        if profile.max_exposure_minor is not None and exposure_minor + amount_minor > profile.max_exposure_minor:
            raise LimitError("FX exposure limit exceeded")
