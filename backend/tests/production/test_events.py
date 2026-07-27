import datetime as dt

import pytest

from production.events import EventEnvelope, is_backward_compatible, parse_event


def _event(**overrides):
    value = {
        "event_id": "e1", "event_type": "payment.created", "schema_version": "1.0",
        "tenant_id": "t1", "participant_id": "p1", "aggregate_id": "pay-1",
        "aggregate_type": "PAYMENT", "aggregate_version": 1, "sequence": 1,
        "partition_key": "pay-1", "correlation_id": "c1", "trace_id": "tr1",
        "occurred_at": dt.datetime.now(dt.UTC), "payload": {"amount_minor": 100},
    }
    value.update(overrides)
    return value


def test_event_envelope_requires_utc_and_forbids_unknown_fields():
    assert parse_event(_event()).event_type == "payment.created"
    with pytest.raises(ValueError):
        EventEnvelope.model_validate(_event(occurred_at=dt.datetime.now()))
    with pytest.raises(ValueError):
        EventEnvelope.model_validate(_event(unexpected="x"))


def test_old_consumer_compatibility_rejects_breaking_major_change():
    old = parse_event(_event())
    current = parse_event(_event(event_id="e2", schema_version="1.1", sequence=2))
    breaking = parse_event(_event(event_id="e3", schema_version="2.0", sequence=3))
    assert is_backward_compatible(old, current)
    assert not is_backward_compatible(old, breaking)
