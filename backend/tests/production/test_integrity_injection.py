from __future__ import annotations

import asyncio
import base64
import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import production.integrity as integrity


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
