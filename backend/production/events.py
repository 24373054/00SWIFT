"""Versioned production event envelope and compatibility rules."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventEnvelope(BaseModel):
    """Canonical envelope shared by outbox, broker and inbox consumers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1, max_length=100)
    event_type: str = Field(min_length=1, max_length=160)
    schema_version: str = Field(pattern=r"^\d+\.\d+$")
    tenant_id: str = Field(min_length=1, max_length=120)
    participant_id: str = Field(min_length=1, max_length=120)
    aggregate_id: str = Field(min_length=1, max_length=120)
    aggregate_type: str = Field(min_length=1, max_length=80)
    aggregate_version: int = Field(ge=1)
    sequence: int = Field(ge=1)
    partition_key: str = Field(min_length=1, max_length=160)
    correlation_id: str = Field(min_length=1, max_length=120)
    causation_id: str | None = Field(default=None, max_length=120)
    trace_id: str = Field(min_length=1, max_length=120)
    occurred_at: dt.datetime
    payload: dict[str, Any]

    @field_validator("occurred_at")
    @classmethod
    def require_utc(cls, value: dt.datetime) -> dt.datetime:
        if value.tzinfo is None or value.utcoffset() != dt.timedelta(0):
            raise ValueError("occurred_at must be timezone-aware UTC")
        return value


SUPPORTED_EVENT_TYPES = frozenset(
    {
        "payment",
        "funding",
        "fx",
        "message",
        "settlement",
        "compliance",
        "reconciliation",
        "case",
        "report",
    }
)


def event_type_family(event_type: str) -> str:
    family = event_type.split(".", 1)[0].lower()
    if family not in SUPPORTED_EVENT_TYPES:
        raise ValueError(f"unsupported production event family: {family}")
    return family


def parse_event(raw: dict[str, Any]) -> EventEnvelope:
    envelope = EventEnvelope.model_validate(raw)
    event_type_family(envelope.event_type)
    return envelope


def is_backward_compatible(previous: EventEnvelope, current: EventEnvelope) -> bool:
    """Compatibility gate: same aggregate identity and non-decreasing major version."""

    previous_major = int(previous.schema_version.split(".", 1)[0])
    current_major = int(current.schema_version.split(".", 1)[0])
    return (
        previous.event_type == current.event_type
        and previous.aggregate_type == current.aggregate_type
        and current_major == previous_major
        and current.sequence >= previous.sequence
    )
