"""OAuth2 JWT-bearer grant and bearer-token verification.

Raw consumer secrets and access tokens are returned only at creation/issuance.
The database stores a salted secret verifier and a deterministic token digest.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import secrets
from datetime import UTC, datetime

import jwt
from cryptography.x509 import load_pem_x509_certificate
from fastapi import APIRouter, Depends, Form, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.jti_store import check_and_record
from config import get_settings
from core.errors import (
    SEVERITY_FATAL,
    SwiftApiException,
    invalid_token,
    malformed_request,
    token_not_provided,
)
from core.security import hash_secret, token_digest, verify_secret
from core.time import epoch_seconds, now_utc
from database import AppCredential, OAuthToken, get_db

router = APIRouter(prefix="/oauth2", tags=["OAuth2"])
JWT_BEARER_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str


def _decode_basic_auth(authorization: str | None) -> tuple[str, str]:
    if not authorization or not authorization.startswith("Basic "):
        raise malformed_request("Missing or invalid Authorization header (expected Basic)")
    try:
        raw = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
        key, secret = raw.split(":", 1)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise malformed_request("Invalid Basic auth encoding") from None
    if not key or not secret:
        raise malformed_request("Consumer key and secret are required")
    return key, secret


def _find_credential(db: Session, consumer_key: str, consumer_secret: str) -> AppCredential:
    cred = db.query(AppCredential).filter(AppCredential.consumer_key == consumer_key).first()
    if not cred or not verify_secret(consumer_secret, cred.consumer_secret):
        raise SwiftApiException(
            "SwAP001",
            SEVERITY_FATAL,
            "API Service not provisioned (invalid client credentials)",
            401,
        )
    # Opportunistic one-way migration for databases created by v2.0.
    if not cred.consumer_secret.startswith("pbkdf2_sha256$"):
        cred.consumer_secret = hash_secret(consumer_secret)
        db.flush()
    return cred


def _token_audience(request: Request) -> str:
    host = request.url.hostname or "localhost"
    port = request.url.port
    netloc = f"{host}:{port}" if port and port not in (80, 443) else host
    return f"{netloc}/oauth2/token"


def _verify_assertion(
    db: Session,
    request: Request,
    assertion: str,
    cred: AppCredential,
    requested_scope: str,
) -> None:
    if not cred.cert_x5c:
        raise malformed_request("Credential has no PKI certificate")
    try:
        x5c_list = json.loads(cred.cert_x5c)
        der_b64 = x5c_list[0]
        cert_pem = "-----BEGIN CERTIFICATE-----\n" + der_b64 + "\n-----END CERTIFICATE-----"
        public_key = load_pem_x509_certificate(cert_pem.encode()).public_key()
    except (ValueError, TypeError, IndexError, json.JSONDecodeError) as exc:
        raise malformed_request("Credential certificate is invalid") from exc

    settings = get_settings()
    try:
        claims = jwt.decode(
            assertion,
            public_key,
            algorithms=["RS256"],
            audience=_token_audience(request),
            leeway=settings.clock_skew_seconds,
            options={"require": ["exp", "iat", "nbf", "jti", "iss", "sub", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise invalid_token("Assertion verification failed") from exc

    if claims.get("iss") != cred.consumer_key:
        raise invalid_token("Assertion iss does not match consumer key")
    if claims.get("sub") != cred.cert_subject:
        raise invalid_token("Assertion sub does not match certificate subject")

    allowed = set((cred.allowed_scopes or "").split())
    requested = set((requested_scope or "").split())
    missing = requested - allowed
    if missing:
        raise SwiftApiException(
            "SwAP003",
            SEVERITY_FATAL,
            f"OAuth token has insufficient scope: {sorted(missing)}",
            403,
        )

    exp_dt = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
    if check_and_record(db, claims["jti"], exp_dt, app_id=cred.id):
        raise invalid_token("Assertion jti has already been used (replay detected)")


def _issue_access_token(cred: AppCredential, scope: str) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.oauth_token_ttl_default
    if settings.is_sandbox:
        try:
            from core.utils import load_private_key_from_file

            ca_key_path = os.path.join(settings.certs_ca_dir(), "ca.key")
            if os.path.exists(ca_key_path):
                key = load_private_key_from_file(ca_key_path, password=None)
                now = epoch_seconds()
                return (
                    jwt.encode(
                        {
                            "iss": "swift-mock-oauth",
                            "sub": cred.consumer_key,
                            "iat": now,
                            "nbf": now,
                            "exp": now + expires_in,
                            "jti": secrets.token_hex(16),
                            "scope": scope,
                        },
                        key,
                        algorithm="RS256",
                    ),
                    expires_in,
                )
        except (OSError, ValueError):
            pass
    return secrets.token_urlsafe(48), expires_in


def _lookup_token(db: Session, raw_token: str, *, active_only: bool = True) -> OAuthToken | None:
    query = db.query(OAuthToken).filter(OAuthToken.access_token == token_digest(raw_token))
    if active_only:
        query = query.filter(OAuthToken.is_revoked.is_(False))
    return query.first()


@router.post("/token", response_model=TokenResponse)
def issue_token(
    request: Request,
    grant_type: str = Form(...),
    assertion: str | None = Form(None),
    scope: str = Form(""),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    if grant_type != JWT_BEARER_GRANT:
        raise malformed_request(f"Unsupported grant_type: {grant_type}")
    if not assertion:
        raise malformed_request("Missing assertion")

    consumer_key, consumer_secret = _decode_basic_auth(authorization)
    cred = _find_credential(db, consumer_key, consumer_secret)
    effective_scope = scope or " ".join((cred.allowed_scopes or "").split()) or "swift.api"
    _verify_assertion(db, request, assertion, cred, scope)

    db.query(OAuthToken).filter(
        OAuthToken.app_id == cred.id,
        OAuthToken.is_revoked.is_(False),
    ).update({"is_revoked": True})

    raw_token, expires_in = _issue_access_token(cred, effective_scope)
    record = OAuthToken(
        app_id=cred.id,
        access_token=token_digest(raw_token),
        token_type="Bearer",
        expires_in=expires_in,
        scope=effective_scope,
    )
    cred.last_used = now_utc()
    db.add(record)
    db.commit()
    return TokenResponse(
        access_token=raw_token,
        token_type="Bearer",
        expires_in=expires_in,
        scope=effective_scope,
    )


@router.post("/revoke")
def revoke_token(
    token: str = Form(...),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    key, secret = _decode_basic_auth(authorization)
    cred = _find_credential(db, key, secret)
    record = _lookup_token(db, token, active_only=False)
    if record and record.app_id == cred.id:
        record.is_revoked = True
        db.commit()
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "revoked"})


def verify_bearer_token(authorization: str | None, db: Session) -> AppCredential:
    if not authorization or not authorization.startswith("Bearer "):
        raise token_not_provided()
    raw = authorization[7:].strip()
    if not raw:
        raise token_not_provided()
    token = _lookup_token(db, raw)
    if not token:
        raise invalid_token()

    issued = token.issued_at
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=UTC)
    if (now_utc() - issued).total_seconds() > token.expires_in + get_settings().clock_skew_seconds:
        token.is_revoked = True
        db.commit()
        raise invalid_token("Access token expired")

    cred = db.query(AppCredential).filter(AppCredential.id == token.app_id).first()
    if not cred:
        raise invalid_token("App credential not found for token")
    return cred


def get_token_scopes(authorization: str | None, db: Session) -> list[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return []
    token = _lookup_token(db, authorization[7:].strip())
    return (token.scope or "").split() if token else []
