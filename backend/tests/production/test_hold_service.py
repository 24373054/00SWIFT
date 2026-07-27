import pytest

from production.funding_service import HoldService
from production.ledger_service import ProductionLedgerService
from production.runtime import ProductionConflict


def test_hold_lifecycle_is_locked_and_versioned(db):
    ProductionLedgerService(db).create_account("hold-a", "LE-CN", "SUBLEDGER", "CNY", "asset", opening_balance_minor=100)
    service = HoldService(db)
    hold = service.create(hold_id="hold-1", tenant_id="tenant:P1", legal_entity_id="LE-CN", book_id="SUBLEDGER", account_id="hold-a", amount_minor=30, currency="CNY", purpose="PAYMENT")
    assert hold.state == "HELD"
    with pytest.raises(ProductionConflict, match="version"):
        service.transition("hold-1", "RELEASED", expected_version=99)
    assert service.transition("hold-1", "CONSUMED", expected_version=1).state == "CONSUMED"
