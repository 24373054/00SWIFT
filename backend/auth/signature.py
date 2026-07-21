"""X-SWIFT-Signature verification (non-repudiation).

Mirrors the client-side signer at
``research/api-sample-code/python/messaging-api/app/api/swift_signature.py``.
The client computes a digest over the request body and signs an RS256 JWT
containing that digest; the server verifies it.

The digest has a **double-encoding quirk** (a real SWIFT behaviour the sample
reveals):

    digest = base64( sha256( base64( body_string ) ) )

i.e. SHA-256 is computed over the *base64-encoded* body, not the raw bytes.
``verify_swift_signature`` reproduces this exactly.

Only POST write endpoints require a signature (Pre-validation, GPI
status/cancellation, Messaging send/ack/nak). GETs are never signed. A missing
signature on a non-repudiation endpoint yields ``SwAP509`` (400).
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime

import jwt
from sqlalchemy.orm import Session

from auth.jti_store import check_and_record
from config import get_settings
from core.errors import SEVERITY_FATAL, SwiftApiException, missing_signature
from database import AppCredential


def compute_body_digest(body: bytes) -> str:
    """Compute the SWIFT body digest: ``base64(sha256(base64(body)))``.

    ``body`` is the raw request body bytes. The double-encoding matches the
    client's ``base64.b64encode(body.encode())`` then ``sha256(...).digest()``
    then ``base64.b64encode(...).decode()`` sequence.
    """
    # The client does body.encode() (str -> bytes), then b64encode -> bytes.
    # We have body as bytes already; if it's already bytes, encode->b64 would
    # double-encode. To match the client exactly, we treat `body` as the raw
    # bytes the client would have encoded as a string.
    body_b64 = base64.b64encode(body)
    digest = hashlib.sha256(body_b64).digest()
    return base64.b64encode(digest).decode("utf-8")


def verify_swift_signature(
    body: bytes,
    sig_header: str | None,
    cred: AppCredential,
    audience: str,
    db: Session,
) -> None:
    """Verify an ``X-SWIFT-Signature`` header against the request body.

    Args:
        body: Raw request body bytes.
        sig_header: The ``X-SWIFT-Signature`` header value (an RS256 JWT).
        cred: The authenticated AppCredential (must have a stored cert).
        audience: Expected ``aud`` claim (host + path, ``https://`` stripped).
        db: DB session (for jti replay protection).

    Raises ``SwiftApiException`` (SwAP509 / SwAP502) on any failure.
    """
    if not sig_header:
        raise missing_signature()
    if not cred.cert_x5c:
        raise SwiftApiException(
            "SwAP509",
            SEVERITY_FATAL,
            "Missing PKI certificate on credential; cannot verify signature",
            400,
        )

    import json

    try:
        x5c_list = json.loads(cred.cert_x5c)
        der_b64 = x5c_list[0]
        cert_pem = "-----BEGIN CERTIFICATE-----\n" + der_b64 + "\n-----END CERTIFICATE-----"
        from cryptography.x509 import load_pem_x509_certificate

        public_key = load_pem_x509_certificate(cert_pem.encode("utf-8")).public_key()
    except (ValueError, TypeError, IndexError, json.JSONDecodeError):
        raise SwiftApiException(
            "SwAP502", SEVERITY_FATAL, "Stored certificate is invalid", 401
        ) from None

    try:
        claims = jwt.decode(
            sig_header,
            public_key,
            algorithms=["RS256"],
            audience=audience,
            leeway=get_settings().clock_skew_seconds,
            options={"require": ["exp", "iat", "nbf", "jti", "sub", "aud", "digest"]},
        )
    except jwt.PyJWTError:
        raise SwiftApiException(
            "SwAP502", SEVERITY_FATAL, "Signature verification failed", 401
        ) from None

    # sub must match the credential's cert_subject.
    if claims.get("sub") != cred.cert_subject:
        raise SwiftApiException(
            "SwAP502",
            SEVERITY_FATAL,
            "Signature sub does not match certificate subject",
            401,
        )

    # digest must match the recomputed body digest.
    expected_digest = compute_body_digest(body)
    if claims.get("digest") != expected_digest:
        raise SwiftApiException(
            "SwAP502",
            SEVERITY_FATAL,
            "Signature digest does not match request body",
            401,
        )

    # jti replay protection (signature JWTs have a 15s window per the client).
    exp_ts = claims.get("exp")
    if exp_ts:
        exp_dt = datetime.fromtimestamp(exp_ts, tz=UTC)
        if check_and_record(db, claims["jti"], exp_dt, app_id=cred.id):
            raise SwiftApiException(
                "SwAP502",
                SEVERITY_FATAL,
                "Signature jti has already been used (replay detected)",
                401,
            )
