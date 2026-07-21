"""End-to-end payment lifecycle, transaction-copy, case and quality services."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from .models import (
    DataQualityMetric,
    FieldLineage,
    PaymentCase,
    PaymentLensEvent,
    PaymentLifecycle,
    TransactionCopy,
    utcnow,
)
from .runtime import OutboxService
from .standards import finding_dicts, validate_message

ALLOWED_TRANSITIONS = {
    "RECEIVED": {"VALIDATED", "REJECTED"},
    "VALIDATED": {"IN_PROCESS", "REJECTED", "CANCELLED"},
    "IN_PROCESS": {"SETTLED", "ON_HOLD", "RETURNED", "REJECTED", "CANCELLED"},
    "ON_HOLD": {"IN_PROCESS", "REJECTED", "CANCELLED"},
    "SETTLED": {"RETURNED"},
    "RETURNED": set(),
    "REJECTED": set(),
    "CANCELLED": set(),
}


class PaymentLifecycleError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else key
            items.extend(_flatten(value[key], child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            items.extend(_flatten(item, f"{prefix}[{index}]"))
    else:
        items.append((prefix, value))
    return items


class PaymentService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        uetr: str,
        scenario: str = "CCT",
        original_uetr: str | None = None,
        deadline_minutes: int = 120,
    ) -> PaymentLifecycle:
        parsed = uuid.UUID(uetr)
        if parsed.version != 4:
            raise PaymentLifecycleError("UETR must be a UUIDv4")
        if scenario == "COV" and not original_uetr:
            raise PaymentLifecycleError("Cover payments must reference the original UETR")
        if original_uetr and original_uetr != uetr:
            raise PaymentLifecycleError("Cover payment must inherit the original UETR")
        if self.db.query(PaymentLifecycle).filter_by(uetr=uetr).first():
            raise PaymentLifecycleError("UETR already exists")
        lifecycle = PaymentLifecycle(
            uetr=uetr,
            scenario=scenario,
            original_uetr=original_uetr,
            deadline_at=utcnow() + dt.timedelta(minutes=deadline_minutes),
        )
        self.db.add(lifecycle)
        self._lens(uetr, "lifecycle.created", "RECEIVED", {"scenario": scenario})
        OutboxService(self.db).enqueue("payment.received", uetr, {"scenario": scenario})
        self.db.flush()
        return lifecycle

    def transition(
        self,
        uetr: str,
        expected_version: int,
        new_status: str,
        reason: str = "",
    ) -> PaymentLifecycle:
        lifecycle = self.db.query(PaymentLifecycle).filter_by(uetr=uetr).one()
        if lifecycle.version != expected_version:
            raise PaymentLifecycleError("Payment lifecycle version conflict")
        if new_status not in ALLOWED_TRANSITIONS.get(lifecycle.status, set()):
            raise PaymentLifecycleError(f"Illegal transition: {lifecycle.status} -> {new_status}")
        old_status = lifecycle.status
        lifecycle.status = new_status
        lifecycle.version += 1
        self._lens(
            uetr,
            "lifecycle.transition",
            new_status,
            {"from": old_status, "reason": reason},
        )
        OutboxService(self.db).enqueue(
            f"payment.{new_status.lower()}",
            uetr,
            {"from": old_status, "reason": reason},
        )
        self.db.flush()
        return lifecycle

    def append_transaction_copy(
        self,
        uetr: str,
        message_id: str,
        message_type: str,
        payload: dict[str, Any],
        source_party: str,
        reason: str = "",
    ) -> TransactionCopy:
        if not self.db.query(PaymentLifecycle).filter_by(uetr=uetr).first():
            raise PaymentLifecycleError("Unknown UETR")
        previous = (
            self.db.query(TransactionCopy)
            .filter_by(uetr=uetr)
            .order_by(TransactionCopy.id.desc())
            .first()
        )
        payload_hash = _hash(payload)
        copy = TransactionCopy(
            uetr=uetr,
            message_id=message_id,
            message_type=message_type,
            payload=_json(payload),
            payload_hash=payload_hash,
            previous_hash=previous.payload_hash if previous else None,
            source_party=source_party,
        )
        self.db.add(copy)
        for path, value in _flatten(payload):
            self.db.add(
                FieldLineage(
                    uetr=uetr,
                    message_id=message_id,
                    path=path,
                    source_party=source_party,
                    value_hash=_hash(value),
                    reason=reason,
                )
            )
        self._lens(
            uetr,
            "transaction.copy",
            "RECORDED",
            {"message_id": message_id, "message_type": message_type},
        )
        self.db.flush()
        return copy

    def verify_copy_chain(self, uetr: str) -> bool:
        copies = (
            self.db.query(TransactionCopy).filter_by(uetr=uetr).order_by(TransactionCopy.id).all()
        )
        previous_hash = None
        for copy in copies:
            if copy.previous_hash != previous_hash:
                return False
            if _hash(json.loads(copy.payload)) != copy.payload_hash:
                return False
            previous_hash = copy.payload_hash
        return True

    def open_case(
        self,
        uetr: str,
        case_type: str,
        owner: str,
        details: dict[str, Any],
        sla_minutes: int = 240,
    ) -> PaymentCase:
        if not self.db.query(PaymentLifecycle).filter_by(uetr=uetr).first():
            raise PaymentLifecycleError("Unknown UETR")
        payment_case = PaymentCase(
            case_id=f"case-{uuid.uuid4().hex}",
            uetr=uetr,
            case_type=case_type,
            owner=owner,
            details=_json(details),
            deadline_at=utcnow() + dt.timedelta(minutes=sla_minutes),
        )
        self.db.add(payment_case)
        self._lens(
            uetr,
            "case.opened",
            "OPEN",
            {"case_id": payment_case.case_id, "case_type": case_type},
        )
        self.db.flush()
        return payment_case

    def update_case(
        self,
        case_id: str,
        status: str,
        owner: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> PaymentCase:
        payment_case = self.db.query(PaymentCase).filter_by(case_id=case_id).one()
        allowed = {
            "OPEN": {"IN_REVIEW", "CLOSED"},
            "IN_REVIEW": {"WAITING_INFORMATION", "RESOLVED", "CLOSED"},
            "WAITING_INFORMATION": {"IN_REVIEW", "CLOSED"},
            "RESOLVED": {"CLOSED", "OPEN"},
            "CLOSED": {"OPEN"},
        }
        if status not in allowed.get(payment_case.status, set()):
            raise PaymentLifecycleError("Illegal case transition")
        payment_case.status = status
        if owner:
            payment_case.owner = owner
        if details is not None:
            payment_case.details = _json(details)
        self._lens(
            payment_case.uetr,
            "case.transition",
            status,
            {"case_id": case_id},
        )
        self.db.flush()
        return payment_case

    def assess_quality(
        self,
        entity_id: str,
        profile: str,
        message_type: str,
        payload: dict[str, Any],
    ) -> DataQualityMetric:
        findings = validate_message(profile, message_type, payload)
        flattened = _flatten(payload)
        populated = sum(value not in (None, "", [], {}) for _, value in flattened)
        completeness = 100.0 if not flattened else populated / len(flattened) * 100
        errors = sum(finding.severity == "error" for finding in findings)
        warnings = sum(finding.severity == "warning" for finding in findings)
        validity = max(0.0, 100.0 - errors * 15.0 - warnings * 5.0)
        consistency = 100.0
        if payload.get("header", {}).get("message_definition") != message_type:
            consistency -= 35.0
        integrity = 100.0 if self.verify_copy_chain(entity_id) else 0.0
        metric = DataQualityMetric(
            entity_type="payment",
            entity_id=entity_id,
            profile=profile,
            completeness=round(completeness, 2),
            validity=round(validity, 2),
            consistency=round(consistency, 2),
            integrity=round(integrity, 2),
            details=_json({"findings": finding_dicts(findings)}),
        )
        self.db.add(metric)
        self.db.flush()
        return metric

    def timeline(self, uetr: str) -> list[PaymentLensEvent]:
        return (
            self.db.query(PaymentLensEvent).filter_by(uetr=uetr).order_by(PaymentLensEvent.id).all()
        )

    def _lens(
        self,
        uetr: str,
        event_type: str,
        status: str,
        details: dict[str, Any],
    ) -> None:
        self.db.add(
            PaymentLensEvent(
                uetr=uetr,
                system="00SWIFT",
                event_type=event_type,
                status=status,
                details=_json(details),
            )
        )
