import pytest

from production.gl_bridge import GlBridge
from production.ledger_service import ProductionLedgerService
from production.runtime import ProductionConflict


def test_ledger_service_boundary_and_gl_ack_are_explicit(db):
    service = ProductionLedgerService(db)
    account = service.create_account("payer", "LE-CN", "SUBLEDGER", "CNY", 1000)
    assert account.account_id == "payer"
    batch = GlBridge().build_batch("batch-1", ["j-2", "j-1"], "map-v1")
    assert batch.journal_ids == ("j-1", "j-2")
    with pytest.raises(ProductionConflict, match="receipt hash"):
        GlBridge().acknowledge("ACK")
