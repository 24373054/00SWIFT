from __future__ import annotations

import asyncio
import base64
import hashlib
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from starlette.requests import Request
from test_http_signatures import _signed_request

import production.integrity as integrity
from production.signatures import SandboxHttpSignatureVerifier


def _request(headers: dict[str, str], body: bytes = b"{}"): 
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/production/v1/payments",
        "raw_path": b"/production/v1/payments",
        "query_string": b"",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        "scheme": "https",
        "server": ("pay.example", 443),
        "client": ("127.0.0.1", 1234),
    }
    return Request(scope, receive)


def _run(coro):
    return asyncio.run(coro)


def test_digest_is_verified_before_any_signature_dependency():
    integrity.configure_signature_verifier(None)
    bad = _request({"content-digest": "sha-256=:AAAA:"})
    with pytest.raises(HTTPException) as exc:
        _run(integrity.require_request_integrity(bad))
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "INVALID_CONTENT_DIGEST"


def test_pilot_requires_injected_qualified_verifier(monkeypatch):
    integrity.configure_signature_verifier(None)
    monkeypatch.setattr(integrity, "get_settings", lambda: SimpleNamespace(swift_env="pilot"))
    body = b"{}"
    digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
    request = _request({
        "content-digest": f"sha-256=:{digest}:",
        "signature-input": 'sig1=("@method");created=1',
        "signature": "sig1=:AA==:",
    }, body)
    with pytest.raises(HTTPException) as exc:
        _run(integrity.require_request_integrity(request))
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "QUALIFIED_SIGNATURE_VERIFIER_NOT_CONFIGURED"


def test_sandbox_without_signature_remains_explicitly_compatibility_only(monkeypatch):
    integrity.configure_signature_verifier(None)
    monkeypatch.setattr(integrity, "get_settings", lambda: SimpleNamespace(swift_env="sandbox"))
    _run(integrity.require_request_integrity(_request({})))


def test_integrity_consumes_nonce_and_rejects_second_request(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    integrity.configure_signature_verifier(
        SandboxHttpSignatureVerifier({"key-1": private_key.public_key().public_bytes_raw()})
    )
    monkeypatch.setattr(
        integrity,
        "get_settings",
        lambda: SimpleNamespace(swift_env="sandbox", production_signature_trust_domain="cn-hk"),
    )
    signed = _signed_request(private_key)
    headers = {
        **dict(signed.headers),
        "host": "pay.example",
        "signature-input": signed.signature_input,
        "signature": signed.signature,
    }
    first = _request(headers, signed.body)
    _run(integrity.require_request_integrity(first))
    second = _request(headers, signed.body)
    with pytest.raises(HTTPException) as exc:
        _run(integrity.require_request_integrity(second))
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "MESSAGE_REPLAY_DETECTED"
