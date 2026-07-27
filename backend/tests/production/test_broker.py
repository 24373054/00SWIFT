import datetime as dt

import pytest

from production.broker import (
    ApprovedBrokerAdapter,
    BrokerUnavailable,
    MemoryBrokerAdapter,
    build_broker,
)
from production.events import EventEnvelope


def _event():
    return EventEnvelope(
        event_id="e1", event_type="payment.created", schema_version="1.0", tenant_id="t1", participant_id="p1",
        aggregate_id="p1", aggregate_type="PAYMENT", aggregate_version=1, sequence=1, partition_key="p1",
        correlation_id="c1", trace_id="tr1", occurred_at=dt.datetime.now(dt.UTC), payload={"amount_minor": 1},
    )


def test_memory_broker_publish_subscribe_ack_and_duplicate():
    broker = MemoryBrokerAdapter()
    assert broker.publish("payment", _event())["duplicate"] is False
    assert broker.publish("payment", _event())["duplicate"] is True
    assert len(broker.subscribe("payment", "worker")) == 1
    broker.ack("payment", "worker", "e1")
    assert broker.subscribe("payment", "worker") == []


def test_pilot_requires_approved_client_and_sandbox_selects_memory():
    assert build_broker("sandbox").health()["adapter"] == "memory"
    with pytest.raises(BrokerUnavailable, match="not configured"):
        build_broker("pilot")
    with pytest.raises(BrokerUnavailable, match="not configured"):
        ApprovedBrokerAdapter()
