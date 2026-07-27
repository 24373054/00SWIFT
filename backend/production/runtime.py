"""Runtime primitives for the production domain."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    ProductionAuditEvent,
    ProductionEvidenceManifest,
    ProductionIdempotencyKey,
    ProductionOutboxEvent,
    ProductionPaymentOrder,
    utcnow,
)


class ProductionConflict(ValueError):
    """A business or idempotency conflict that must be returned as 409."""


def _aware(value: dt.datetime) -> dt.datetime:
    return value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def body_digest(body: str | bytes) -> str:
    data = body.encode("utf-8") if isinstance(body, str) else body
    return hashlib.sha256(data).hexdigest()


def minor_amount(value: str | int | Decimal, currency: str) -> int:
    """Convert a decimal API amount to an integer minor unit.

    Currency metadata belongs in a versioned registry.  This implementation
    intentionally keeps only the common two-decimal currencies and rejects
    more precision rather than silently truncating money.
    """

    digits = {"CNY": 2, "HKD": 2, "USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}.get(currency)
    if digits is None:
        raise ProductionConflict(f"Currency metadata is not configured: {currency}")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProductionConflict("Amount must be a decimal string") from exc
    quantum = Decimal(1).scaleb(-digits)
    rounded = amount.quantize(quantum, rounding=ROUND_HALF_UP)
    if rounded <= 0 or rounded != amount:
        raise ProductionConflict("Amount precision or sign is invalid")
    return int(rounded * (10**digits))


class ProductionIdempotencyService:
    def __init__(self, db: Session):
        self.db = db

    def begin(
        self,
        scope: str,
        key: str,
        request: Any,
        ttl_seconds: int = 86400,
        *,
        owner: str = "production-api",
        trace_id: str | None = None,
    ) -> tuple[ProductionIdempotencyKey, bool]:
        if not key.strip():
            raise ProductionConflict("Idempotency-Key is required")
        request_hash = digest(request)
        now = utcnow()
        record = self.db.query(ProductionIdempotencyKey).filter_by(scope=scope, key=key).with_for_update().first()
        if record:
            if record.request_hash != request_hash:
                raise ProductionConflict("Idempotency key was reused with a different payload")
            if _aware(record.expires_at) <= now:
                record.status = "EXPIRED"
                self.db.flush()
                raise ProductionConflict("Idempotency key has expired; create a new key")
            if record.status == "STARTED":
                if record.locked_until is None or _aware(record.locked_until) > now:
                    raise ProductionConflict("Idempotent operation is already in progress") from None
                record.owner = owner
                record.trace_id = trace_id
                record.locked_until = now + dt.timedelta(seconds=ttl_seconds)
                record.attempt += 1
                self.db.flush()
                return record, False
            if record.status == "COMPLETED":
                return record, True
            if record.status == "FAILED_RETRYABLE":
                record.status = "STARTED"
                record.owner = owner
                record.trace_id = trace_id
                record.locked_until = now + dt.timedelta(seconds=ttl_seconds)
                record.attempt += 1
                self.db.flush()
                return record, False
            if record.status in {"FAILED_FINAL", "EXPIRED"}:
                raise ProductionConflict(f"Idempotent operation is not replayable: {record.status}")
            return record, True
        record = ProductionIdempotencyKey(
            scope=scope,
            key=key,
            request_hash=request_hash,
            expires_at=now + dt.timedelta(seconds=ttl_seconds),
            owner=owner,
            locked_until=now + dt.timedelta(seconds=ttl_seconds),
            attempt=1,
            trace_id=trace_id,
        )
        try:
            with self.db.begin_nested():
                self.db.add(record)
                self.db.flush()
        except IntegrityError:
            record = self.db.query(ProductionIdempotencyKey).filter_by(scope=scope, key=key).with_for_update().one()
            if record.request_hash != request_hash:
                raise ProductionConflict("Concurrent idempotency payload conflict") from None
            if record.status == "COMPLETED":
                return record, True
            raise ProductionConflict("Idempotent operation is already in progress") from None
        return record, False

    def complete(self, record: ProductionIdempotencyKey, status: int, response: Any) -> None:
        record.status = "COMPLETED"
        record.response_status = status
        record.response_body = canonical_json(response)
        record.locked_until = None
        record.owner = None
        self.db.flush()

    def fail(self, record: ProductionIdempotencyKey, error: str, *, final: bool = False) -> None:
        record.status = "FAILED_FINAL" if final else "FAILED_RETRYABLE"
        record.last_error = error[:2000]
        record.locked_until = None
        record.owner = None
        self.db.flush()

    def recover_started(
        self,
        record: ProductionIdempotencyKey,
        query_aggregate,
        *,
        now: dt.datetime | None = None,
    ) -> tuple[str, Any | None]:
        """Resolve an expired STARTED record before allowing a retry.

        ``query_aggregate`` must query the local aggregate and/or connector by
        stable client reference.  A takeover is returned only when it proves
        that no prior business effect exists; the service never blindly reruns.
        """

        now = now or utcnow()
        if record.status != "STARTED" or record.locked_until is None or _aware(record.locked_until) > now:
            raise ProductionConflict("idempotency record is not eligible for recovery")
        result = query_aggregate(record.scope, record.key)
        if result is not None:
            self.complete(record, 200, result)
            return "COMPLETED", result
        record.owner = None
        record.locked_until = now
        self.db.flush()
        return "TAKEOVER_REQUIRED", None


class ProductionOutboxService:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(
        self,
        topic: str,
        aggregate_id: str,
        payload: Any,
        *,
        schema_version: str = "1.0",
        partition_key: str | None = None,
    ) -> ProductionOutboxEvent:
        payload_json = canonical_json(payload)
        resolved_tenant = payload.get("tenant_id") if isinstance(payload, dict) else None
        resolved_participant = payload.get("participant_id") if isinstance(payload, dict) else None
        order_id = payload.get("order_id") if isinstance(payload, dict) else aggregate_id
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=order_id).one_or_none()
        if order is not None:
            resolved_tenant = resolved_tenant or order.tenant_id
            resolved_participant = resolved_participant or order.initiator_participant
        if not resolved_tenant or not resolved_participant:
            raise ProductionConflict("outbox event requires tenant and participant context")
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        event = ProductionOutboxEvent(
            event_id=str(uuid.uuid4()),
            topic=topic,
            schema_version=schema_version,
            partition_key=partition_key or aggregate_id,
            aggregate_id=aggregate_id,
            tenant_id=resolved_tenant,
            participant_id=resolved_participant,
            payload=payload_json,
            payload_hash=payload_hash,
            content_hash=payload_hash,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def claim(self, limit: int = 50, *, owner: str = "production-worker", lease_seconds: int = 60) -> list[ProductionOutboxEvent]:
        now = utcnow()
        self.db.query(ProductionOutboxEvent).filter(
            ProductionOutboxEvent.status == "PROCESSING",
            ProductionOutboxEvent.lease_until < now,
        ).update(
            {"status": "PENDING", "lease_owner": None, "lease_until": None},
            synchronize_session=False,
        )
        rows = (
            self.db.query(ProductionOutboxEvent)
            .filter(
                ProductionOutboxEvent.status == "PENDING",
                ProductionOutboxEvent.available_at <= now,
            )
            .order_by(ProductionOutboxEvent.id)
            .limit(max(1, min(limit, 500)))
            .with_for_update(skip_locked=True)
            .all()
        )
        for row in rows:
            row.status = "PROCESSING"
            row.attempts += 1
            row.lease_owner = owner
            row.lease_until = now + dt.timedelta(seconds=lease_seconds)
        self.db.flush()
        return rows

    def complete(self, event: ProductionOutboxEvent) -> None:
        event.status = "PUBLISHED"
        event.lease_owner = None
        event.lease_until = None
        self.db.flush()

    def fail(self, event: ProductionOutboxEvent, error: str, retry_seconds: int = 10) -> None:
        event.last_error = error[:2000]
        event.lease_owner = None
        event.lease_until = None
        if event.attempts >= 8:
            event.status = "DEAD_LETTER"
        else:
            event.status = "PENDING"
            event.available_at = utcnow() + dt.timedelta(seconds=retry_seconds)
        self.db.flush()


class ProductionEvidenceService:
    """Append-only evidence manifest service.

    A production deployment must replace the ``db://`` storage URI with an
    approved WORM object store.  The manifest and hash-chain semantics are
    still enforced in the local sandbox so the adapter contract is stable.
    """

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        evidence_type: str,
        aggregate_id: str,
        payload: Any,
        *,
        retention_class: str = "PAYMENT-10Y",
        actor: str = "system",
    ) -> ProductionEvidenceManifest:
        previous = (
            self.db.query(ProductionEvidenceManifest)
            .order_by(ProductionEvidenceManifest.id.desc())
            .first()
        )
        content_hash = digest(payload)
        evidence_id = f"evd_{uuid.uuid4().hex}"
        manifest = ProductionEvidenceManifest(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            aggregate_id=aggregate_id,
            content_hash=content_hash,
            previous_hash=previous.content_hash if previous else None,
            storage_uri=f"db://production-evidence/{evidence_id}",
            retention_class=retention_class,
            metadata_json=canonical_json({"actor": actor, "payload": payload}),
        )
        self.db.add(manifest)
        self.db.flush()
        return manifest


class ProductionAuditService:
    def __init__(self, db: Session):
        self.db = db

    def append(self, event_type: str, aggregate_id: str, payload: Any, actor: str) -> str:
        previous = self.db.query(ProductionAuditEvent).order_by(ProductionAuditEvent.id.desc()).first()
        payload_hash = hashlib.sha256(
            f"{previous.payload_hash if previous else ''}:{canonical_json(payload)}".encode()
        ).hexdigest()
        event = ProductionAuditEvent(
            event_id=f"audit_{uuid.uuid4().hex}",
            trace_id=f"trace_{uuid.uuid4().hex}",
            event_type=event_type,
            aggregate_id=aggregate_id,
            payload_hash=payload_hash,
            previous_hash=previous.payload_hash if previous else None,
            payload=canonical_json(payload),
            actor=actor,
        )
        self.db.add(event)
        self.db.flush()
        return event.event_id
