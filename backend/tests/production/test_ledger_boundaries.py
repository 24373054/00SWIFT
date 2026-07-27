import pytest

from production.gl_bridge import GlBridge
from production.ledger_service import ProductionLedgerService
from production.runtime import ProductionConflict


def test_ledger_service_boundary_and_gl_ack_are_explicit(db):
    service = ProductionLedgerService(db)
    account = service.create_account("payer", "LE-CN", "SUBLEDGER", "CNY", "asset", opening_balance_minor=1000)
    assert account.account_id == "payer"
    batch = GlBridge().build_batch("batch-1", ["j-2", "j-1"], "map-v1")
    assert batch.journal_ids == ("j-1", "j-2")
    with pytest.raises(ProductionConflict, match="receipt hash"):
        GlBridge().acknowledge("ACK")


def test_account_type_controls_normal_balance_direction(db):
    service = ProductionLedgerService(db)
    service.create_account("asset", "LE-CN", "SUBLEDGER", "CNY", "asset", opening_balance_minor=100)
    service.create_account("liability", "LE-CN", "SUBLEDGER", "CNY", "liability", opening_balance_minor=100)
    service.post_journal(journal_id="j-1", legal_entity="LE-CN", book="SUBLEDGER", reason_code="funding", entries=[{"account_id": "asset", "direction": "CREDIT", "currency": "CNY", "amount_minor": 10}, {"account_id": "liability", "direction": "DEBIT", "currency": "CNY", "amount_minor": 10}])
