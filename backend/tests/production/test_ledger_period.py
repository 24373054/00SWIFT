import pytest

from production.ledger_service import LedgerPeriodService
from production.runtime import ProductionConflict


def test_ledger_period_close_requires_maker_checker_and_cas(db):
    service = LedgerPeriodService(db)
    service.open("p-1", "tenant:P1", "book-1", "2026-07-01", "2026-07-31")
    with pytest.raises(ProductionConflict, match="maker-checker"):
        service.close("p-1", 1, "alice", "alice")
    assert service.close("p-1", 1, "alice", "bob").state == "CLOSED"
