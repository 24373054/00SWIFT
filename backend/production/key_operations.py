"""Dual-control key rotation/revocation execution and audit."""

from __future__ import annotations

import hashlib
import json
import uuid

from .key_provider import KeyProvider, KeyProviderError
from .models import ProductionApproval, ProductionKeyOperationAudit, utcnow


class KeyOperationError(ValueError):
    """Raised when dual-control approval or provider execution fails."""


class KeyOperationService:
    def __init__(self, db, provider: KeyProvider):
        self.db = db
        self.provider = provider

    def execute(self, *, operation: str, key_id: str, trust_domain: str, maker: str, checker: str | None, approval_id: str):
        if operation not in {"ROTATE", "REVOKE"}:
            raise KeyOperationError("unsupported key operation")
        if not checker or maker == checker:
            raise KeyOperationError("key operation requires distinct maker and checker")
        approval = self.db.query(ProductionApproval).filter_by(
            approval_id=approval_id,
            action=operation,
            maker=maker,
            checker=checker,
            state="APPROVED",
        ).one_or_none()
        if approval is None:
            raise KeyOperationError("approved dual-control record is required")
        audit = ProductionKeyOperationAudit(
            operation_id=f"kop_{uuid.uuid4().hex}", operation=operation, key_id=key_id,
            trust_domain=trust_domain, maker=maker, checker=checker, approval_id=approval_id,
            status="STARTED", created_at=utcnow(),
        )
        self.db.add(audit)
        self.db.flush()
        try:
            if operation == "ROTATE":
                result = self.provider.rotate(key_id)
                result_payload = {"version": result.version, "public_key": result.public_key.hex()}
            else:
                revoke = getattr(self.provider, "revoke", None)
                if revoke is None:
                    raise KeyProviderError("provider does not support revocation")
                revoke(key_id)
                result_payload = {"status": self.provider.revoke_status(key_id)}
            audit.status = "COMPLETED"
            audit.result_digest = hashlib.sha256(json.dumps(result_payload, sort_keys=True).encode()).hexdigest()
            audit.completed_at = utcnow()
            self.db.flush()
            return audit, result_payload
        except Exception as exc:  # noqa: BLE001 - persist failed operation evidence
            audit.status = "FAILED"
            audit.evidence_ref = f"error:{type(exc).__name__}"
            audit.completed_at = utcnow()
            self.db.flush()
            raise KeyOperationError(str(exc)) from exc
