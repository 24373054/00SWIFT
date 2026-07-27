"""Canonical ledger service entrypoint."""

from ._ledger_core import ProductionLedgerService, serialize_account
from .models import ProductionBalanceSnapshot, ProductionJournalEntry, ProductionLedgerPeriod
from .runtime import ProductionConflict, digest

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


class BalanceSnapshotService:
    def __init__(self, db):
        self.db = db

    def create(self, snapshot_id, tenant_id, book_id, account_id, business_date):
        entries = self.db.query(ProductionJournalEntry).filter_by(account_id=account_id).order_by(ProductionJournalEntry.id).all()
        source_hash = digest([{"entry_id": item.entry_id, "amount_minor": item.amount_minor, "direction": item.direction} for item in entries])
        balance = sum(item.amount_minor if item.direction == "DEBIT" else -item.amount_minor for item in entries)
        snapshot = ProductionBalanceSnapshot(snapshot_id=snapshot_id, tenant_id=tenant_id, book_id=book_id, account_id=account_id, business_date=business_date, balance_minor=balance, source_max_entry_sequence=entries[-1].id if entries else 0, source_hash=source_hash)
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

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
