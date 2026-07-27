"""Funding boundary around ledger-backed holds."""

from ._ledger_core import ProductionLedgerService


class FundingService:
    """Explicit funding API; payment workers must use this boundary."""

    def __init__(self, db):
        self._ledger = ProductionLedgerService(db)

    def reserve(self, account_id, reservation_id, amount_minor, currency):
        return self._ledger.reserve(account_id, reservation_id, amount_minor, currency)

    def release(self, reservation_id):
        return self._ledger.release(reservation_id)

    def consume(self, reservation_id):
        return self._ledger.consume(reservation_id)
