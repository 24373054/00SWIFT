from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from production.qualification import QualificationError, QualificationStatus, QualificationVerifier


def _document(tmp_path, *, expired: bool = False):
    artifact = tmp_path / "connector.bin"
    artifact.write_bytes(b"qualified-connector-v1")
    key = Ed25519PrivateKey.generate()
    public_key = key.public_key().public_bytes_raw()
    now = dt.datetime.now(dt.UTC)
    valid_from = now - dt.timedelta(minutes=2)
    valid_to = now - dt.timedelta(minutes=1) if expired else now + dt.timedelta(hours=1)
    document = {
        "artifact_id": "attestation-1",
        "environment": "pilot",
        "subject": "participant-a",
        "issuer": "qualification-authority",
        "connector": "qualified-value-v1",
        "connector_version": "1.0.0",
        "artifact_path": artifact.name,
        "artifact_digest": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "signature_algorithm": "Ed25519",
        "valid_from": valid_from.isoformat(),
        "valid_to": valid_to.isoformat(),
        "public_key": base64.b64encode(public_key).decode(),
    }
    unsigned_document = {key: value for key, value in document.items() if key not in {"signature", "public_key"}}
    unsigned = json.dumps(unsigned_document, sort_keys=True, separators=(",", ":")).encode()
    document["signature"] = base64.b64encode(key.sign(unsigned)).decode()
    attestation = tmp_path / "attestation.json"
    attestation.write_text(json.dumps(document), encoding="utf-8")
    return attestation, base64.b64encode(public_key).decode(), document


def test_signed_qualification_and_artifact_digest(tmp_path):
    path, trust_anchor, _ = _document(tmp_path)
    result = QualificationVerifier().verify_file(
        str(path), expected_environment="pilot", trust_anchor=trust_anchor
    )
    assert result.connector == "qualified-value-v1"
    assert result.artifact_digest == hashlib.sha256(b"qualified-connector-v1").hexdigest()
    assert result.status is QualificationStatus.VERIFIED


def test_qualification_rejects_missing_file_and_expiry(tmp_path):
    with pytest.raises(QualificationError, match="does not exist"):
        QualificationVerifier().verify_file(
            str(tmp_path / "missing.json"), expected_environment="pilot", trust_anchor="x"
        )
    path, trust_anchor, _ = _document(tmp_path, expired=True)
    with pytest.raises(QualificationError, match="outside"):
        QualificationVerifier().verify_file(
            str(path), expected_environment="pilot", trust_anchor=trust_anchor
        )


def test_qualification_rejects_wrong_environment_digest_and_trust(tmp_path):
    path, trust_anchor, document = _document(tmp_path)
    with pytest.raises(QualificationError, match="environment"):
        QualificationVerifier().verify_file(
            str(path), expected_environment="live", trust_anchor=trust_anchor
        )
    document["artifact_digest"] = "0" * 64
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(QualificationError, match="signature verification"):
        QualificationVerifier().verify_file(
            str(path), expected_environment="pilot", trust_anchor=trust_anchor
        )
