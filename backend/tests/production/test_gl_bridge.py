import pytest

from production.gl_bridge import GlBridge
from production.runtime import ProductionConflict


def test_gl_batch_requires_receipt_ack(db):
    bridge = GlBridge()
    batch = bridge.persist_batch(db, batch_id="gl-1", tenant_id="tenant:P1", mapping_version="map-v1", journal_ids=["j-1"], debit_total_minor=10, credit_total_minor=10)
    assert batch.state == "SENT"
    with pytest.raises(ProductionConflict, match="ACK"):
        bridge.record_receipt(db, receipt_id="rcpt-bad", tenant_id="tenant:P1", batch_id="gl-1", state="ACK", receipt_hash="")
    receipt = bridge.record_receipt(db, receipt_id="rcpt-1", tenant_id="tenant:P1", batch_id="gl-1", state="ACK", receipt_hash="a" * 64)
    assert receipt.state == "ACK" and batch.state == "ACK"
