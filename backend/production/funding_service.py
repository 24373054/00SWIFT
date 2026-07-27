"""Funding boundary around ledger-backed holds."""

from ._ledger_core import ProductionLedgerService
from .models import ProductionLiabilityProfile
from .runtime import ProductionConflict


class FundingService:
    """Explicit funding API; payment workers must use this boundary."""

    def __init__(self, db):
        self._ledger = ProductionLedgerService(db)

    def reserve(self, account_id, reservation_id, amount_minor, currency, liability_profile_id=None):
        if liability_profile_id:
            profile = self._ledger.db.query(ProductionLiabilityProfile).filter_by(profile_id=liability_profile_id, active=True).one_or_none()
            if profile is None:
                raise ProductionConflict("Active liability profile is required")
        return self._ledger.reserve(account_id, reservation_id, amount_minor, currency)

    def assert_liability_profile(self, profile_id: str) -> ProductionLiabilityProfile:
        profile = self._ledger.db.query(ProductionLiabilityProfile).filter_by(profile_id=profile_id, active=True).one_or_none()
        if profile is None:
            raise ProductionConflict("Active liability profile is required")
        return profile

    def release(self, reservation_id):
        return self._ledger.release(reservation_id)

    def consume(self, reservation_id):
        return self._ledger.consume(reservation_id)
