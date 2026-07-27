import datetime as dt

import pytest

from production.events import is_backward_compatible, parse_event


def _raw(version: str, sequence: int, payload: dict):
    return {
        "event_id": f"e-{sequence}",
        "event_type": "payment.created",
        "schema_version": version,
        "tenant_id": "t1",
        "participant_id": "p1",
        "aggregate_id": "pay-1",
        "aggregate_type": "PAYMENT",
        "aggregate_version": sequence,
        "sequence": sequence,
        "partition_key": "pay-1",
        "correlation_id": "c1",
        "trace_id": "tr1",
        "occurred_at": dt.datetime.now(dt.UTC),
        "payload": payload,
    }


def test_additive_minor_event_is_compatible_but_major_break_is_not():
    old = parse_event(_raw("1.0", 1, {"amount_minor": 100}))
    additive = parse_event(_raw("1.1", 2, {"amount_minor": 100, "purpose": "TRADE"}))
    breaking = parse_event(_raw("2.0", 3, {"amount_minor": 100}))
    assert is_backward_compatible(old, additive)
    assert not is_backward_compatible(old, breaking)


def test_unknown_event_family_is_rejected_before_dispatch():
    raw = _raw("1.0", 1, {})
    raw["event_type"] = "unknown.created"
    with pytest.raises(ValueError, match="unsupported"):
        parse_event(raw)
