from production.models import ProductionOutboxEvent
from production.runtime import ProductionOutboxService


def _event(event_id: str, sequence: int, partition: str):
    return ProductionOutboxEvent(
        event_id=event_id,
        topic="payment.created",
        schema_version="1.0",
        partition_key=partition,
        aggregate_id=partition,
        tenant_id="t1",
        participant_id="p1",
        aggregate_sequence=sequence,
        payload="{}",
        payload_hash="0" * 64,
        content_hash="0" * 64,
    )


def test_same_partition_claims_lowest_sequence_first_and_other_partition_parallel(db):
    db.add_all([_event("p1-2", 2, "p1"), _event("p1-1", 1, "p1"), _event("p2-1", 1, "p2")])
    db.commit()
    claimed = ProductionOutboxService(db).claim(limit=10, owner="worker")
    assert {event.event_id for event in claimed} == {"p1-1", "p2-1"}
