"""Client-side X-SWIFT-Signature generator (mirrors auth.signature verifier).

Ported from ``research/api-sample-code/python/messaging-api/app/api/swift_signature.py``.
The digest uses SWIFT's double-encoding quirk: ``base64(sha256(base64(body)))``.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Optional

import jwt


def _now_epoch() -> int:
    return int(time.time())


def sign_request(
    body: str,
    private_key,
    cert_subject: str,
    audience: str,
    x5c: list[str],
) -> str:
    """Sign a request body, returning the ``X-SWIFT-Signature`` header value.

    Args:
        body: The raw request body string (what the client will send).
        private_key: RSA private key (cryptography object) for RS256 signing.
        cert_subject: RFC4514 lowercased cert subject (the ``sub`` claim).
        audience: host+path, ``https://`` stripped (the ``aud`` claim).
        x5c: list of base64 DER cert segments (the JWT ``x5c`` header).
    """
    body_b64 = base64.b64encode(body.encode("utf-8"))
    digest = hashlib.sha256(body_b64).digest()
    digest_b64 = base64.b64encode(digest).decode("utf-8")

    now = _now_epoch()
    payload = {
        "iat": now,
        "nbf": now,
        "exp": now + 15,  # 15-second window (real SWIFT)
        "jti": secrets.token_hex(16),
        "sub": cert_subject,
        "aud": audience,
        "digest": digest_b64,
    }
    headers = {"alg": "RS256", "x5c": x5c, "typ": "JWT"}
    return jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
