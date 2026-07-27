import datetime as dt

from production.funding_service import HoldService
from production.ledger_service import ProductionLedgerService


def test_hold_expiry_unknown_does_not_release_without_external_reference(db):
    ProductionLedgerService(db).create_account("expiry-a", "LE-CN", "SUBLEDGER", "CNY", "asset", opening_balance_minor=100)
    service = HoldService(db)
    service.create(hold_id="expiry-1", tenant_id="tenant:P1", legal_entity_id="LE-CN", book_id="SUBLEDGER", account_id="expiry-a", amount_minor=10, currency="CNY", purpose="PAYMENT", expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1))
    assert service.expire_due(dt.datetime.now(dt.UTC))[0].state == "UNKNOWN"
