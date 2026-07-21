"""Security primitives for credentials, tokens, and audit redaction.

The sandbox intentionally avoids external secret-management dependencies, but
never stores reusable secrets in plaintext. Consumer secrets use PBKDF2-HMAC
with a per-secret salt; bearer tokens use a deterministic SHA-256 digest so
that they can be looked up without retaining the raw token.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any
from urllib.parse import parse_qsl, urlencode

PBKDF2_ITERATIONS = 310_000
_SECRET_PREFIX = "pbkdf2_sha256"
SENSITIVE_KEYS = {
    "access_token",
    "assertion",
    "authorization",
    "client_secret",
    "consumer_secret",
    "password",
    "private_key",
    "refresh_token",
    "signature",
    "token",
    "x-swift-signature",
}


def hash_secret(secret: str, *, salt: bytes | None = None) -> str:
    """Return a salted PBKDF2 representation suitable for database storage."""
    if not secret:
        raise ValueError("secret must not be empty")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{_SECRET_PREFIX}${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_secret(secret: str, encoded: str) -> bool:
    """Verify a plaintext secret; legacy plaintext rows remain readable once."""
    if encoded.startswith(f"{_SECRET_PREFIX}$"):
        try:
            _, iterations, salt_hex, expected_hex = encoded.split("$", 3)
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                secret.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations),
            )
            return hmac.compare_digest(actual.hex(), expected_hex)
        except (TypeError, ValueError):
            return False
    return hmac.compare_digest(secret, encoded)


def token_digest(token: str) -> str:
    """Return the deterministic digest persisted for a bearer token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def redact_mapping(value: Any) -> Any:
    """Recursively redact common secret-bearing fields."""
    if isinstance(value, dict):
        return {
            str(k): "***" if str(k).lower() in SENSITIVE_KEYS else redact_mapping(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_mapping(v) for v in value]
    return value


def redact_body(body: bytes, content_type: str | None, *, limit: int = 4000) -> str:
    """Return a bounded, redacted representation of an HTTP request body."""
    if not body:
        return ""
    text = body.decode("utf-8", errors="replace")
    content_type = (content_type or "").lower()
    try:
        if "application/json" in content_type:
            return json.dumps(redact_mapping(json.loads(text)), ensure_ascii=False)[:limit]
        if "application/x-www-form-urlencoded" in content_type:
            pairs = [
                (key, "***" if key.lower() in SENSITIVE_KEYS else value)
                for key, value in parse_qsl(text, keep_blank_values=True)
            ]
            return urlencode(pairs)[:limit]
    except (ValueError, TypeError):
        return "[unparseable body]"
    return text[:limit]
