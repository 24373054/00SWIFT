from __future__ import annotations

import base64
import datetime as dt
import hashlib

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from production.signatures import (
    QualifiedHttpSignatureVerifier,
    SandboxHttpSignatureVerifier,
    SignatureVerificationError,
    SignedHttpRequest,
    canonical_signature_input,
)


def _signed_request(private_key, *, body: bytes = b'{"amount":10}', target_uri: str = "https://pay.example/production/v1/payments", expires_delta: int = 60, algorithm: str = "ed25519"):
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
    headers = {
        "content-digest": f"sha-256=:{digest}:",
        "content-type": "application/json",
        "date": now.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        "nonce": "nonce-unique-1",
        "participant-id": "participant-a",
        "service-identity": "payments-api",
    }
    signature_input = (
        'sig1=("@method" "@target-uri" "@authority" "content-digest" "content-type" '
        '"date" "nonce" "participant-id" "service-identity")'
        f";created={int(now.timestamp())};expires={int(now.timestamp()) + expires_delta}"
        ';nonce="nonce-unique-1";keyid="key-1";alg="' + algorithm + '"'
    )
    unsigned = SignedHttpRequest(
        method="POST", target_uri=target_uri, authority="pay.example", headers=headers, body=body,
        signature_input=signature_input, signature="sig1=:AA==:", participant_id="participant-a", service_identity="payments-api", now=now,
    )
    signature = base64.b64encode(
        private_key.sign(canonical_signature_input(unsigned, [
            "@method", "@target-uri", "@authority", "content-digest", "content-type", "date", "nonce", "participant-id", "service-identity"
        ], {"created": str(int(now.timestamp())), "expires": str(int(now.timestamp()) + expires_delta), "nonce": "nonce-unique-1", "keyid": "key-1", "alg": algorithm}))
    ).decode()
    return unsigned.__class__(**{**unsigned.__dict__, "signature": f"sig1=:{signature}:"})


def test_sandbox_verifier_checks_real_ed25519_and_body_digest():
    private_key = Ed25519PrivateKey.generate()
    request = _signed_request(private_key)
    result = SandboxHttpSignatureVerifier({"key-1": private_key.public_key().public_bytes_raw()}).verify(request)
    assert result.participant_id == "participant-a"
    tampered = request.__class__(**{**request.__dict__, "body": b"tampered"})
    with pytest.raises(SignatureVerificationError, match="digest"):
        SandboxHttpSignatureVerifier({"key-1": private_key.public_key().public_bytes_raw()}).verify(tampered)


def test_signature_rejects_uri_expiry_missing_component_and_weak_algorithm():
    private_key = Ed25519PrivateKey.generate()
    verifier = SandboxHttpSignatureVerifier({"key-1": private_key.public_key().public_bytes_raw()})
    request = _signed_request(private_key)
    with pytest.raises(SignatureVerificationError, match="verification failed"):
        verifier.verify(request.__class__(**{**request.__dict__, "target_uri": "https://pay.example/other"}))
    with pytest.raises(SignatureVerificationError, match="validity"):
        verifier.verify(_signed_request(private_key, expires_delta=-1))
    missing = request.__class__(**{**request.__dict__, "signature_input": request.signature_input.replace(' "date"', "")})
    with pytest.raises(SignatureVerificationError, match="missing"):
        verifier.verify(missing)
    with pytest.raises(SignatureVerificationError, match="not allowed"):
        verifier.verify(_signed_request(private_key, algorithm="none"))


def test_qualified_adapter_delegates_canonical_bytes_and_identity():
    private_key = Ed25519PrivateKey.generate()
    calls = []

    def verify(key_id, payload, signature):
        calls.append((key_id, payload))
        private_key.public_key().verify(signature, payload)
        return True

    result = QualifiedHttpSignatureVerifier(verify).verify(_signed_request(private_key))
    assert result.key_id == "key-1"
    assert calls and calls[0][0] == "key-1"
