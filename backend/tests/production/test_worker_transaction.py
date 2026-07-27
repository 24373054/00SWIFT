from production.models import ProductionInboxMessage, ProductionOutboxEvent
from production.runtime import ProductionOutboxService
from production.worker import ProductionWorker


def test_inbox_receipt_and_followup_outbox_share_transaction(db):
    event = ProductionOutboxEvent(
        event_id="tx-in-1", topic="payment.created", schema_version="1.0", partition_key="p1",
        aggregate_id="p1", tenant_id="t1", participant_id="p1", aggregate_sequence=1,
        payload='{"order_id":"p1"}', payload_hash="0" * 64, content_hash="0" * 64,
    )
    db.add(event)
    db.commit()
    worker = ProductionWorker(db)
    assert worker._register_inbox(event) is True
    ProductionOutboxService(db).enqueue("payment.followup", "p1", {"tenant_id": "t1", "participant_id": "p1", "order_id": "p1"})
    db.rollback()
    assert db.query(ProductionInboxMessage).filter_by(event_id="tx-in-1").first() is None
    assert db.query(ProductionOutboxEvent).filter_by(topic="payment.followup").first() is None
