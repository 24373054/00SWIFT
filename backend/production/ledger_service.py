"""Canonical ledger service entrypoint."""

from ._ledger_core import ProductionLedgerService, serialize_account
from .models import ProductionLedgerPeriod
from .runtime import ProductionConflict

__all__ = ["ProductionLedgerService", "serialize_account"]


class LedgerPeriodService:
    def __init__(self, db):
        self.db = db

    def open(self, period_id, tenant_id, book_id, period_start, period_end):
        if self.db.query(ProductionLedgerPeriod).filter_by(period_id=period_id).one_or_none():
            raise ProductionConflict("Ledger period already exists")
        period = ProductionLedgerPeriod(period_id=period_id, tenant_id=tenant_id, book_id=book_id, period_start=period_start, period_end=period_end, state="OPEN")
        self.db.add(period)
        self.db.flush()
        return period

    def close(self, period_id, expected_version, maker, checker):
        if maker == checker:
            raise ProductionConflict("Period close requires maker-checker")
        period = self.db.query(ProductionLedgerPeriod).filter_by(period_id=period_id).with_for_update().one_or_none()
        if period is None or period.version != expected_version or period.state not in {"OPEN", "SOFT_CLOSED"}:
            raise ProductionConflict("Ledger period close conflict")
        period.state = "CLOSED"
        period.version += 1
        self.db.flush()
        return period
