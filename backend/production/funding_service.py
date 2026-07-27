"""Funding boundary around ledger-backed holds."""

from ._ledger_core import ProductionLedgerService
from .models import ProductionHold, ProductionLedgerAccount, ProductionLiabilityProfile
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


class HoldService:
    """Row-locked hold lifecycle with version fencing."""

    def __init__(self, db):
        self.db = db

    def create(self, *, hold_id, tenant_id, legal_entity_id, book_id, account_id, amount_minor, currency, purpose, payment_id=None, expires_at=None, evidence_ref=None):
        if amount_minor <= 0:
            raise ProductionConflict("Hold amount must be positive")
        account = self.db.query(ProductionLedgerAccount).filter_by(account_id=account_id, currency=currency.upper(), active=True).with_for_update().one_or_none()
        if account is None or account.balance_minor - account.reserved_minor < amount_minor:
            raise ProductionConflict("Insufficient available funds")
        if self.db.query(ProductionHold).filter_by(hold_id=hold_id).one_or_none():
            raise ProductionConflict("Hold already exists")
        account.reserved_minor += amount_minor
        hold = ProductionHold(hold_id=hold_id, tenant_id=tenant_id, legal_entity_id=legal_entity_id, book_id=book_id, account_id=account_id, payment_id=payment_id, purpose=purpose, amount_minor=amount_minor, currency=currency.upper(), state="HELD", expires_at=expires_at, evidence_ref=evidence_ref)
        self.db.add(hold)
        self.db.flush()
        return hold

    def transition(self, hold_id, state, expected_version):
        hold = self.db.query(ProductionHold).filter_by(hold_id=hold_id).with_for_update().one_or_none()
        if hold is None or hold.version != expected_version:
            raise ProductionConflict("Hold version conflict")
        if state not in {"CONSUMED", "RELEASED", "EXPIRED", "UNKNOWN"} or hold.state != "HELD":
            raise ProductionConflict("Invalid hold transition")
        if state in {"CONSUMED", "RELEASED", "EXPIRED"}:
            account = self.db.query(ProductionLedgerAccount).filter_by(account_id=hold.account_id).with_for_update().one()
            account.reserved_minor -= hold.amount_minor
        hold.state = state
        hold.version += 1
        self.db.flush()
        return hold

    def expire_due(self, now):
        due = self.db.query(ProductionHold).filter(ProductionHold.state == "HELD", ProductionHold.expires_at.is_not(None), ProductionHold.expires_at <= now).with_for_update().all()
        results = []
        for hold in due:
            state = "EXPIRED" if hold.external_reference else "UNKNOWN"
            results.append(self.transition(hold.hold_id, state, hold.version))
        return results

    def release(self, reservation_id):
        return self._ledger.release(reservation_id)

    def consume(self, reservation_id):
        return self._ledger.consume(reservation_id)
