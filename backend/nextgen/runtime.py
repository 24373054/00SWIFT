"""Idempotency, transactional outbox, durable workflow and database lease primitives."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import secrets
import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import IdempotencyRecord, LeaseLock, OutboxEvent, WorkflowInstance, utcnow


class IdempotencyConflict(ValueError):
    pass


def request_digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


class IdempotencyService:
    def __init__(self, db: Session):
        self.db = db

    def begin(
        self,
        key: str,
        payload: Any,
        ttl_seconds: int = 86400,
    ) -> tuple[IdempotencyRecord, bool]:
        digest = request_digest(payload)
        record = self.db.query(IdempotencyRecord).filter_by(key=key).first()
        if record:
            if record.request_hash != digest:
                raise IdempotencyConflict(
                    "Idempotency key was already used with a different request"
                )
            return record, True
        record = IdempotencyRecord(
            key=key,
            request_hash=digest,
            expires_at=utcnow() + dt.timedelta(seconds=ttl_seconds),
        )
        self.db.add(record)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            record = self.db.query(IdempotencyRecord).filter_by(key=key).one()
            if record.request_hash != digest:
                raise IdempotencyConflict(
                    "Concurrent request used the key with a different request"
                ) from None
            return record, True
        return record, False

    def complete(
        self,
        record: IdempotencyRecord,
        response_status: int,
        response: Any,
    ) -> None:
        record.status = "completed"
        record.response_status = response_status
        record.response_body = json.dumps(response, sort_keys=True, default=str)
        self.db.flush()


class OutboxService:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(self, topic: str, aggregate_id: str, payload: Any) -> OutboxEvent:
        event = OutboxEvent(
            event_id=str(uuid.uuid4()),
            topic=topic,
            aggregate_id=aggregate_id,
            payload=json.dumps(payload, sort_keys=True, default=str),
        )
        self.db.add(event)
        self.db.flush()
        return event

    def claim(self, limit: int = 100) -> list[OutboxEvent]:
        events = (
            self.db.query(OutboxEvent)
            .filter(
                OutboxEvent.status == "pending",
                OutboxEvent.available_at <= utcnow(),
            )
            .order_by(OutboxEvent.id)
            .limit(max(1, min(limit, 1000)))
            .all()
        )
        for event in events:
            event.status = "processing"
            event.attempts += 1
        self.db.flush()
        return events

    def complete(self, event: OutboxEvent) -> None:
        event.status = "published"
        self.db.flush()

    def fail(
        self,
        event: OutboxEvent,
        error: str,
        retry_seconds: int = 30,
        max_attempts: int = 5,
    ) -> None:
        event.last_error = error[:2000]
        if event.attempts >= max_attempts:
            event.status = "dead_letter"
        else:
            event.status = "pending"
            event.available_at = utcnow() + dt.timedelta(seconds=retry_seconds)
        self.db.flush()


class WorkflowService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, kind: str, state: str, payload: Any) -> WorkflowInstance:
        workflow = WorkflowInstance(
            workflow_id=str(uuid.uuid4()),
            kind=kind,
            state=state,
            payload=json.dumps(payload, sort_keys=True, default=str),
        )
        self.db.add(workflow)
        self.db.flush()
        return workflow

    def transition(
        self,
        workflow_id: str,
        expected_version: int,
        state: str,
        payload: Any | None = None,
    ) -> WorkflowInstance:
        workflow = self.db.query(WorkflowInstance).filter_by(workflow_id=workflow_id).one()
        if workflow.version != expected_version:
            raise ValueError("Workflow version conflict")
        workflow.state = state
        workflow.version += 1
        if payload is not None:
            workflow.payload = json.dumps(payload, sort_keys=True, default=str)
        self.db.flush()
        return workflow


class LeaseService:
    def __init__(self, db: Session):
        self.db = db

    def acquire(self, resource: str, owner: str, ttl_seconds: int = 30) -> str:
        now = utcnow()
        lock = self.db.query(LeaseLock).filter_by(resource=resource).first()
        token = secrets.token_hex(16)
        if lock and lock.expires_at > now and lock.owner != owner:
            raise ValueError("Resource is locked")
        if lock is None:
            lock = LeaseLock(
                resource=resource,
                owner=owner,
                token=token,
                expires_at=now + dt.timedelta(seconds=ttl_seconds),
            )
            self.db.add(lock)
        else:
            lock.owner = owner
            lock.token = token
            lock.expires_at = now + dt.timedelta(seconds=ttl_seconds)
        self.db.flush()
        return token

    def release(self, resource: str, token: str) -> None:
        lock = self.db.query(LeaseLock).filter_by(resource=resource).one()
        if not secrets.compare_digest(lock.token, token):
            raise ValueError("Invalid lease token")
        self.db.delete(lock)
        self.db.flush()
