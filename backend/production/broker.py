"""Broker adapter boundary with a real sandbox memory implementation."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .events import EventEnvelope, parse_event


class BrokerUnavailable(RuntimeError):
    pass


class BrokerAdapter(ABC):
    @abstractmethod
    def publish(self, topic: str, event: EventEnvelope) -> dict[str, Any]: ...

    @abstractmethod
    def subscribe(self, topic: str, consumer: str) -> list[EventEnvelope]: ...

    @abstractmethod
    def ack(self, topic: str, consumer: str, event_id: str) -> None: ...

    @abstractmethod
    def nack(self, topic: str, consumer: str, event_id: str, reason: str) -> None: ...

    @abstractmethod
    def health(self) -> dict[str, Any]: ...


@dataclass
class _Delivery:
    event: EventEnvelope
    attempts: int = 0


class MemoryBrokerAdapter(BrokerAdapter):
    """Deterministic in-memory broker for sandbox and unit tests."""

    def __init__(self) -> None:
        self._topics: dict[str, list[_Delivery]] = defaultdict(list)
        self._acked: set[tuple[str, str, str]] = set()
        self._nacked: dict[tuple[str, str, str], str] = {}

    def publish(self, topic: str, event: EventEnvelope) -> dict[str, Any]:
        if any(item.event.event_id == event.event_id for item in self._topics[topic]):
            return {"event_id": event.event_id, "duplicate": True, "offset": str(self._offset(topic, event.event_id))}
        self._topics[topic].append(_Delivery(event))
        return {"event_id": event.event_id, "duplicate": False, "offset": str(len(self._topics[topic]) - 1)}

    def subscribe(self, topic: str, consumer: str) -> list[EventEnvelope]:
        return [item.event for item in self._topics[topic] if (topic, consumer, item.event.event_id) not in self._acked]

    def ack(self, topic: str, consumer: str, event_id: str) -> None:
        self._acked.add((topic, consumer, event_id))

    def nack(self, topic: str, consumer: str, event_id: str, reason: str) -> None:
        self._nacked[(topic, consumer, event_id)] = reason

    def health(self) -> dict[str, Any]:
        return {"available": True, "adapter": "memory", "topics": len(self._topics)}

    def _offset(self, topic: str, event_id: str) -> int:
        return next(index for index, item in enumerate(self._topics[topic]) if item.event.event_id == event_id)


class ApprovedBrokerAdapter(BrokerAdapter):
    """Production adapter requiring an injected approved client implementation."""

    def __init__(self, client: Any | None = None) -> None:
        self.client = client
        if client is None:
            raise BrokerUnavailable("approved broker client is not configured")

    def publish(self, topic: str, event: EventEnvelope) -> dict[str, Any]:
        return dict(self.client.publish(topic, event.model_dump(mode="json")))

    def subscribe(self, topic: str, consumer: str) -> list[EventEnvelope]:
        return [parse_event(item) for item in self.client.subscribe(topic, consumer)]

    def ack(self, topic: str, consumer: str, event_id: str) -> None:
        self.client.ack(topic, consumer, event_id)

    def nack(self, topic: str, consumer: str, event_id: str, reason: str) -> None:
        self.client.nack(topic, consumer, event_id, reason)

    def health(self) -> dict[str, Any]:
        return dict(self.client.health())


def build_broker(environment: str | None = None, client: Any | None = None) -> BrokerAdapter:
    environment = environment or os.getenv("SWIFT_ENV", "sandbox")
    if environment == "sandbox":
        return MemoryBrokerAdapter()
    return ApprovedBrokerAdapter(client)
