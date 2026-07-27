from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from production.models import ProductionQualificationArtifact


def _artifact(
    artifact_id: str,
    *,
    status: str = "VERIFIED",
    expired: bool = False,
    connector_version: str = "1.0.0",
):
    now = dt.datetime.now(dt.UTC)
    return ProductionQualificationArtifact(
        artifact_id=artifact_id,
        artifact_type="connector-binary",
        environment="pilot",
        subject="participant-a",
        issuer="qualification-authority",
        connector="qualified-value-v1",
        connector_version=connector_version,
        artifact_path="connector.bin",
        artifact_digest="a" * 64,
        signature_algorithm="Ed25519",
        valid_from=now - dt.timedelta(minutes=1),
        valid_to=now - dt.timedelta(minutes=1) if expired else now + dt.timedelta(hours=1),
        document_digest="b" * 64,
        status=status,
        verifier_version="qualification-v1",
    )


def test_qualification_tables_persist_and_enforce_identity_uniqueness(db):
    db.add(_artifact("a-1"))
    db.commit()
    db.add(_artifact("a-2"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_expired_qualification_cannot_become_active(db):
    db.add(_artifact("expired", status="ACTIVE", expired=True))
    with pytest.raises(ValueError, match="expired qualification artifact"):
        db.commit()
