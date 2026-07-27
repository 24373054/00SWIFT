from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from config import Settings


def _qualified_attestation(tmp_path, *, connector: str = "qualified-value-v1") -> tuple[str, str]:
    artifact = tmp_path / "connector.bin"
    artifact.write_bytes(b"qualified-connector")
    key = Ed25519PrivateKey.generate()
    public_key = key.public_key().public_bytes_raw()
    now = dt.datetime.now(dt.UTC)
    document = {
        "artifact_id": "pilot-attestation-1",
        "artifact_type": "connector-binary",
        "environment": "pilot",
        "subject": "participant-a",
        "issuer": "qualification-authority",
        "connector": connector,
        "connector_version": "1.0.0",
        "artifact_path": artifact.name,
        "artifact_digest": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "signature_algorithm": "Ed25519",
        "valid_from": (now - dt.timedelta(minutes=1)).isoformat(),
        "valid_to": (now + dt.timedelta(hours=1)).isoformat(),
        "public_key": base64.b64encode(public_key).decode(),
    }
    unsigned = {key: value for key, value in document.items() if key not in {"signature", "public_key"}}
    payload = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    document["signature"] = base64.b64encode(key.sign(payload)).decode()
    attestation = tmp_path / "attestation.json"
    attestation.write_text(json.dumps(document), encoding="utf-8")
    return str(attestation), base64.b64encode(public_key).decode()


def _pilot_settings(**overrides) -> Settings:
    values = {
        "swift_env": "pilot",
        "db_url": "postgresql+psycopg://user:pass@localhost/test",
        "admin_api_token": "admin-token",
        "live_host_oauth": "https://oauth.example",
        "live_host_preval": "https://preval.example",
        "live_host_swiftref": "https://swiftref.example",
        "live_host_tracker": "https://tracker.example",
        "live_host_messaging": "https://messaging.example",
        "production_connector_mode": "qualified",
        "production_signature_verifier": "qualified",
        "production_hsm_provider": "qualified",
        "production_key_provider": "qualified",
        "production_trust_domain": "cn-hk-qualified",
        "production_key_label": "payment-signing-key",
        "production_worker_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_pilot_gate_verifies_signed_attestation(tmp_path):
    path, trust_anchor = _qualified_attestation(tmp_path)
    settings = _pilot_settings(
        production_qualified_attestation_path=path,
        production_qualification_trust_anchor=trust_anchor,
        production_qualification_expected_connector="qualified-value-v1",
    )
    settings.validate_for_pilot()


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"production_qualified_attestation_path": "missing.json", "production_qualification_trust_anchor": "x"}, "does not exist"),
        ({"production_qualified_attestation_path": "missing.json"}, "attestation"),
    ],
)
def test_pilot_gate_rejects_missing_attestation(overrides, message):
    with pytest.raises(RuntimeError, match=message):
        _pilot_settings(**overrides).validate_for_pilot()


def test_pilot_gate_rejects_connector_mismatch(tmp_path):
    path, trust_anchor = _qualified_attestation(tmp_path, connector="other-connector")
    settings = _pilot_settings(
        production_qualified_attestation_path=path,
        production_qualification_trust_anchor=trust_anchor,
        production_qualification_expected_connector="qualified-value-v1",
    )
    with pytest.raises(RuntimeError, match="does not match"):
        settings.validate_for_pilot()


def test_pilot_gate_rejects_file_key_provider_even_with_attestation(tmp_path):
    path, trust_anchor = _qualified_attestation(tmp_path)
    settings = _pilot_settings(
        production_key_provider="file",
        production_qualified_attestation_path=path,
        production_qualification_trust_anchor=trust_anchor,
    )
    with pytest.raises(RuntimeError, match="qualified HSM/KMS"):
        settings.validate_for_pilot()
