import datetime as dt

import pytest

from production.events import EventEnvelope
from production.schema_registry import InMemorySchemaRegistry, SchemaUnknown


def _event(version="1.0"):
    return EventEnvelope(
        event_id="e1", event_type="payment.created", schema_version=version, tenant_id="t1", participant_id="p1",
        aggregate_id="p1", aggregate_type="PAYMENT", aggregate_version=1, sequence=1, partition_key="p1",
        correlation_id="c1", trace_id="tr1", occurred_at=dt.datetime.now(dt.UTC), payload={},
    )


def test_unknown_schema_goes_to_dlq_and_registered_schema_dispatches():
    registry = InMemorySchemaRegistry({("payment.created", "1.0"): {"payload"}})
    assert registry.validate(_event()).event_id == "e1"
    with pytest.raises(SchemaUnknown, match="unknown"):
        registry.validate(_event("2.0"))
    assert registry.dlq[0]["reason"] == "UNKNOWN_SCHEMA"
