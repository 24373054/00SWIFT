"""Policy, key-management, telemetry, audit-chain, and reconciliation primitives."""

from __future__ import annotations

import base64
import contextlib
import contextvars
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from .models import (
    CipsAccount,
    EcnyOperator,
    PolicyDecision,
    PvpSettlement,
    RuntimeAuditEvent,
)

_TRACE_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "00swift_trace_id",
    default=None,
)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def current_trace_id() -> str:
    trace_id = _TRACE_ID.get()
    if trace_id is None:
        trace_id = uuid.uuid4().hex
        _TRACE_ID.set(trace_id)
    return trace_id


@dataclass(frozen=True)
class SpanResult:
    trace_id: str
    name: str
    duration_ms: float
    status: str
    attributes: dict[str, Any]


@contextlib.contextmanager
def trace_span(name: str, **attributes: Any):
    """Minimal OpenTelemetry-compatible span boundary.

    Callers can map the returned structure into an OTLP exporter without making
    the financial domain depend on a particular telemetry backend.
    """
    token = None
    if _TRACE_ID.get() is None:
        token = _TRACE_ID.set(uuid.uuid4().hex)
    started = time.perf_counter()
    result: dict[str, Any] = {"status": "ok"}
    try:
        yield result
    except Exception:
        result["status"] = "error"
        raise
    finally:
        result["span"] = SpanResult(
            trace_id=current_trace_id(),
            name=name,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            status=result["status"],
            attributes=attributes,
        )
        if token is not None:
            _TRACE_ID.reset(token)


class KeyProvider(Protocol):
    """Provider contract implemented by local KMS, cloud KMS, or an HSM adapter."""

    def sign(self, key_id: str, payload: bytes) -> bytes: ...

    def verify(self, key_id: str, payload: bytes, signature: bytes) -> bool: ...

    def encrypt(self, key_id: str, payload: bytes) -> bytes: ...

    def decrypt(self, key_id: str, payload: bytes) -> bytes: ...


class LocalKeyProvider:
    """Development-only provider using environment-derived symmetric keys."""

    def __init__(self, master_secret: str | None = None):
        secret = master_secret or os.getenv("LOCAL_KMS_MASTER_KEY")
        if not secret:
            raise ValueError("LOCAL_KMS_MASTER_KEY is required")
        self._master = secret.encode()

    def _key(self, key_id: str) -> bytes:
        return hmac.new(self._master, key_id.encode(), hashlib.sha256).digest()

    def _fernet(self, key_id: str) -> Fernet:
        return Fernet(base64.urlsafe_b64encode(self._key(key_id)))

    def sign(self, key_id: str, payload: bytes) -> bytes:
        return hmac.new(self._key(key_id), payload, hashlib.sha256).digest()

    def verify(self, key_id: str, payload: bytes, signature: bytes) -> bool:
        return hmac.compare_digest(self.sign(key_id, payload), signature)

    def encrypt(self, key_id: str, payload: bytes) -> bytes:
        return self._fernet(key_id).encrypt(payload)

    def decrypt(self, key_id: str, payload: bytes) -> bytes:
        try:
            return self._fernet(key_id).decrypt(payload)
        except InvalidToken as exc:
            raise ValueError("Ciphertext authentication failed") from exc


class PolicyEngine:
    """Explainable RBAC/ABAC evaluator with persisted decisions."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate(
        self,
        subject: str,
        action: str,
        resource: str,
        context: dict[str, Any],
        policy: dict[str, Any],
    ) -> PolicyDecision:
        reasons: list[str] = []
        required_roles = set(policy.get("required_roles", []))
        subject_roles = set(context.get("roles", []))
        if required_roles and not required_roles.issubset(subject_roles):
            reasons.append("required role missing")
        max_amount = int(policy.get("max_amount", 0))
        if max_amount and int(context.get("amount", 0)) > max_amount:
            reasons.append("amount exceeds policy")
        allowed_jurisdictions = set(policy.get("allowed_jurisdictions", []))
        jurisdiction = context.get("jurisdiction")
        if allowed_jurisdictions and jurisdiction not in allowed_jurisdictions:
            reasons.append("jurisdiction not allowed")
        required_purpose = set(policy.get("allowed_purposes", []))
        if required_purpose and context.get("purpose") not in required_purpose:
            reasons.append("purpose not allowed")
        decision = PolicyDecision(
            decision_id=f"decision-{uuid.uuid4().hex}",
            subject=subject,
            action=action,
            resource=resource,
            result="deny" if reasons else "allow",
            reasons=_json(reasons or ["all policy predicates satisfied"]),
        )
        self.db.add(decision)
        self.db.flush()
        return decision


class AuditChainService:
    """Append-only, trace-correlated hash chain for operational evidence."""

    def __init__(self, db: Session):
        self.db = db

    def append(
        self,
        event_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        trace_id: str | None = None,
    ) -> RuntimeAuditEvent:
        previous = (
            self.db.query(RuntimeAuditEvent)
            .order_by(RuntimeAuditEvent.id.desc())
            .first()
        )
        encoded = _json(payload)
        previous_hash = previous.payload_hash if previous else None
        payload_hash = hashlib.sha256(
            f"{previous_hash or ''}:{encoded}".encode()
        ).hexdigest()
        event = RuntimeAuditEvent(
            trace_id=trace_id or current_trace_id(),
            event_type=event_type,
            aggregate_id=aggregate_id,
            payload_hash=payload_hash,
            previous_hash=previous_hash,
            payload=encoded,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def verify(self) -> bool:
        previous_hash = None
        for event in self.db.query(RuntimeAuditEvent).order_by(RuntimeAuditEvent.id).all():
            if event.previous_hash != previous_hash:
                return False
            expected = hashlib.sha256(
                f"{previous_hash or ''}:{event.payload}".encode()
            ).hexdigest()
            if not hmac.compare_digest(expected, event.payload_hash):
                return False
            previous_hash = event.payload_hash
        return True


class ReconciliationService:
    """Cross-domain invariant report suitable for scheduled end-of-day execution."""

    def __init__(self, db: Session):
        self.db = db

    def run(self) -> dict[str, Any]:
        cips_accounts = self.db.query(CipsAccount).all()
        operators = self.db.query(EcnyOperator).all()
        pvp_settlements = self.db.query(PvpSettlement).all()

        failures: list[dict[str, Any]] = [
            {
                "domain": "cips",
                "account_id": account.account_id,
                "reason": "invalid liquidity position",
            }
            for account in cips_accounts
            if account.balance < 0
            or account.reserved < 0
            or account.reserved > account.balance
        ]
        failures.extend(
            {
                "domain": "ecny",
                "operator_id": operator.operator_id,
                "reason": "issuance outside authorized range",
            }
            for operator in operators
            if operator.issued_amount < 0
            or operator.issued_amount > operator.issuance_limit
        )
        failures.extend(
            {
                "domain": "pvp",
                "pvp_id": pvp.pvp_id,
                "reason": "unknown terminal or workflow state",
            }
            for pvp in pvp_settlements
            if pvp.state not in {"ABORTED", "COMMITTED", "CREATED", "LOCKED"}
        )
        report = {
            "trace_id": current_trace_id(),
            "ok": not failures,
            "failures": failures,
            "counts": {
                "cips_accounts": len(cips_accounts),
                "ecny_operators": len(operators),
                "pvp_settlements": len(pvp_settlements),
            },
        }
        AuditChainService(self.db).append("reconciliation.completed", "system", report)
        return report
