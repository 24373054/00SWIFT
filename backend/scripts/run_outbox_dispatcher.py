"""Standalone outbox dispatcher entry point; never import FastAPI app workers."""

from __future__ import annotations

import datetime as dt
import json
import os
import time

from database import SessionLocal
from production.broker import build_broker
from production.events import EventEnvelope
from production.runtime import ProductionOutboxService


def dispatch_once() -> dict[str, int]:
    db = SessionLocal()
    try:
        broker = build_broker()
        service = ProductionOutboxService(db)
        processed = 0
        for event in service.claim(owner="outbox-dispatcher"):
            envelope = EventEnvelope(
                event_id=event.event_id,
                event_type=event.topic,
                schema_version=event.schema_version,
                tenant_id=event.tenant_id,
                participant_id=event.participant_id,
                aggregate_id=event.aggregate_id,
                aggregate_type=event.topic.split(".", 1)[0].upper(),
                aggregate_version=event.aggregate_sequence,
                sequence=event.aggregate_sequence,
                partition_key=event.partition_key,
                correlation_id=event.event_id,
                trace_id=event.event_id,
                occurred_at=(event.created_at.replace(tzinfo=dt.UTC) if event.created_at.tzinfo is None else event.created_at),
                payload=json.loads(event.payload),
            )
            receipt = broker.publish(event.topic, envelope)
            service.complete(event, owner="outbox-dispatcher", broker_offset=str(receipt.get("offset")), broker_metadata=receipt)
            processed += 1
        db.commit()
        return {"published": processed}
    finally:
        db.close()


if __name__ == "__main__":
    while True:
        dispatch_once()
        time.sleep(float(os.getenv("OUTBOX_POLL_SECONDS", "1")))
