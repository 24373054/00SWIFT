import datetime as dt

from production.broker import MemoryBrokerAdapter
from production.events import EventEnvelope


def test_broker_nack_then_restart_like_reconsume_is_not_lost():
    event = EventEnvelope(
        event_id="broker-e1", event_type="payment.created", schema_version="1.0", tenant_id="t1", participant_id="p1",
        aggregate_id="p1", aggregate_type="PAYMENT", aggregate_version=1, sequence=1, partition_key="p1",
        correlation_id="c1", trace_id="tr1", occurred_at=dt.datetime.now(dt.UTC), payload={},
    )
    broker = MemoryBrokerAdapter()
    broker.publish("payment.created", event)
    broker.nack("payment.created", "worker", event.event_id, "timeout")
    assert [item.event_id for item in broker.subscribe("payment.created", "worker")] == [event.event_id]
    assert broker.health()["available"] is True
