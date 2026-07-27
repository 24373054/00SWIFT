from production.models import ProductionOutboxEvent
from production.runtime import ProductionOutboxService


def test_publish_confirm_is_recorded_and_duplicate_completion_is_noop(db):
    event = ProductionOutboxEvent(
        event_id="publish-1", topic="payment.created", schema_version="1.0", partition_key="p1",
        aggregate_id="p1", tenant_id="t1", participant_id="p1", aggregate_sequence=1,
        payload="{}", payload_hash="0" * 64, content_hash="0" * 64,
    )
    db.add(event)
    db.commit()
    claimed = ProductionOutboxService(db).claim(owner="worker")[0]
    service = ProductionOutboxService(db)
    service.complete(claimed, owner="worker", broker_offset="42", broker_metadata={"receipt": "r1"})
    published_at = claimed.published_at
    service.complete(claimed, owner="worker", broker_offset="43")
    assert claimed.status == "PUBLISHED" and claimed.broker_offset == "42" and claimed.published_at == published_at
