"""Schema registry validation before broker dispatch."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .events import EventEnvelope, parse_event


class SchemaUnknown(ValueError):
    pass


class SchemaRegistry(ABC):
    @abstractmethod
    def validate(self, event: EventEnvelope) -> EventEnvelope: ...


class InMemorySchemaRegistry(SchemaRegistry):
    def __init__(self, schemas: dict[tuple[str, str], set[str]] | None = None) -> None:
        self.schemas = schemas or {}
        self.dlq: list[dict[str, Any]] = []

    def validate(self, event: EventEnvelope) -> EventEnvelope:
        key = (event.event_type, event.schema_version)
        if key not in self.schemas:
            self.dlq.append({"event_id": event.event_id, "reason": "UNKNOWN_SCHEMA", "event_type": event.event_type, "schema_version": event.schema_version})
            raise SchemaUnknown(f"unknown event schema: {event.event_type}@{event.schema_version}")
        return parse_event(event.model_dump())


class ApprovedSchemaRegistry(SchemaRegistry):
    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            raise SchemaUnknown("approved schema registry client is not configured")
        self.client = client

    def validate(self, event: EventEnvelope) -> EventEnvelope:
        if not self.client.is_registered(event.event_type, event.schema_version):
            raise SchemaUnknown(f"unknown event schema: {event.event_type}@{event.schema_version}")
        return event
