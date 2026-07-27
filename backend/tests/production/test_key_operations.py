from __future__ import annotations

import pytest

from production.key_operations import KeyOperationError, KeyOperationService
from production.key_provider import SandboxKeyProvider
from production.models import ProductionApproval


def _approval(db, *, maker="maker", checker="checker", action="ROTATE"):
    approval = ProductionApproval(
        approval_id="approval-key-1", aggregate_type="KEY", aggregate_id="key-1",
        action=action, maker=maker, checker=checker, reason="dual-control", state="APPROVED",
    )
    db.add(approval)
    db.commit()
    return approval


def test_key_operation_requires_independent_approved_checker(db):
    provider = SandboxKeyProvider()
    with pytest.raises(KeyOperationError, match="distinct"):
        KeyOperationService(db, provider).execute(
            operation="ROTATE", key_id="key-1", trust_domain="sandbox", maker="maker", checker="maker", approval_id="missing"
        )
    _approval(db)
    audit, result = KeyOperationService(db, provider).execute(
        operation="ROTATE", key_id="key-1", trust_domain="sandbox", maker="maker", checker="checker", approval_id="approval-key-1"
    )
    assert audit.status == "COMPLETED"
    assert result["version"] == 2


def test_key_revoke_is_audited_and_missing_approval_fails(db):
    provider = SandboxKeyProvider()
    provider.sign("key-1", b"seed")
    with pytest.raises(KeyOperationError, match="approved"):
        KeyOperationService(db, provider).execute(
            operation="REVOKE", key_id="key-1", trust_domain="sandbox", maker="maker", checker="checker", approval_id="missing"
        )
    _approval(db, action="REVOKE")
    audit, result = KeyOperationService(db, provider).execute(
        operation="REVOKE", key_id="key-1", trust_domain="sandbox", maker="maker", checker="checker", approval_id="approval-key-1"
    )
    assert audit.status == "COMPLETED"
    assert result["status"] == "REVOKED"
