"""Fail-closed qualification artifact verification.

The verifier validates a signed, immutable connector/standards attestation
before pilot/live startup.  It intentionally does not trust a path string or
an environment variable as proof of qualification.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class QualificationError(RuntimeError):
    """Raised when a production qualification artifact is invalid."""


class QualificationStatus(StrEnum):
    """Terminal verification status for a qualification artifact."""

    VERIFIED = "VERIFIED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class QualificationArtifact:
    artifact_id: str
    artifact_type: str
    environment: str
    subject: str
    issuer: str
    connector: str
    connector_version: str
    artifact_path: str
    artifact_digest: str
    signature_algorithm: str
    valid_from: dt.datetime
    valid_to: dt.datetime
    document_digest: str
    source_path: str
    status: QualificationStatus = QualificationStatus.VERIFIED


def _parse_time(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str):
        raise QualificationError(f"qualification.{field} must be an ISO-8601 timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QualificationError(f"qualification.{field} is not a valid timestamp") from exc
    if parsed.tzinfo is None:
        raise QualificationError(f"qualification.{field} must include timezone")
    return parsed.astimezone(dt.UTC)


def _decode_b64(value: Any, field: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise QualificationError(f"qualification.{field} is required")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise QualificationError(f"qualification.{field} is not valid base64") from exc


def _signed_payload(document: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in document.items() if key not in {"signature", "public_key"}}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


class QualificationVerifier:
    """Verify a signed JSON qualification document and referenced artifact."""

    def verify_file(
        self,
        path: str,
        *,
        expected_environment: str,
        trust_anchor: str | None,
        now: dt.datetime | None = None,
    ) -> QualificationArtifact:
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise QualificationError(f"qualification artifact does not exist: {source}")
        try:
            document = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise QualificationError("qualification artifact is not readable JSON") from exc
        if not isinstance(document, dict):
            raise QualificationError("qualification artifact root must be an object")

        required = {
            "artifact_id", "artifact_type", "environment", "subject", "issuer", "connector",
            "connector_version", "artifact_path", "artifact_digest",
            "signature_algorithm", "valid_from", "valid_to", "public_key", "signature",
        }
        missing = sorted(required - document.keys())
        if missing:
            raise QualificationError(f"qualification artifact missing fields: {missing}")
        if document["environment"] != expected_environment:
            raise QualificationError("qualification environment does not match runtime environment")
        if document["signature_algorithm"] != "Ed25519":
            raise QualificationError("qualification signature algorithm must be Ed25519")

        valid_from = _parse_time(document["valid_from"], "valid_from")
        valid_to = _parse_time(document["valid_to"], "valid_to")
        if valid_to <= valid_from:
            raise QualificationError("qualification validity window is invalid")
        current = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)
        if not valid_from <= current <= valid_to:
            raise QualificationError("qualification artifact is outside its validity window")

        public_key = _decode_b64(document["public_key"], "public_key")
        signature = _decode_b64(document["signature"], "signature")
        if trust_anchor is None:
            raise QualificationError("qualification trust anchor is not configured")
        trusted_key = _decode_b64(trust_anchor, "trust_anchor")
        if trusted_key != public_key:
            raise QualificationError("qualification signer is not in the configured trust domain")
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, _signed_payload(document))
        except (InvalidSignature, ValueError) as exc:
            raise QualificationError("qualification signature verification failed") from exc

        artifact = (source.parent / str(document["artifact_path"])).resolve()
        if not artifact.is_file():
            raise QualificationError(f"qualified artifact does not exist: {artifact}")
        actual_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        expected_digest = str(document["artifact_digest"]).lower()
        if actual_digest != expected_digest:
            raise QualificationError("qualified artifact digest does not match attestation")

        document_digest = hashlib.sha256(_signed_payload(document)).hexdigest()
        return QualificationArtifact(
            artifact_id=str(document["artifact_id"]),
            artifact_type=str(document["artifact_type"]),
            environment=str(document["environment"]),
            subject=str(document["subject"]),
            issuer=str(document["issuer"]),
            connector=str(document["connector"]),
            connector_version=str(document["connector_version"]),
            artifact_path=str(artifact),
            artifact_digest=actual_digest,
            signature_algorithm=str(document["signature_algorithm"]),
            valid_from=valid_from,
            valid_to=valid_to,
            document_digest=document_digest,
            source_path=str(source),
        )
