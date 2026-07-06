"""OAuth2 token endpoint with JWT-Bearer grant (server-side mock).

Mirrors the real SWIFT OAuth flow from the SWIFT-API-Guide ``security.md`` and
the api-sample-code client implementation
(``research/api-sample-code/python/messaging-api/app/api/oauth_token.py``):

    POST /oauth2/token
    Authorization: Basic <base64(consumer_key:consumer_secret)>
    Content-Type: application/x-www-form-urlencoded

    grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=<RS256 JWT>&scope=<...>

The client signs a JWT assertion with its RSA private key and includes the
matching x509 cert chain in the JWT ``x5c`` header. The server:

1. Decodes Basic auth -> (consumer_key, consumer_secret) -> AppCredential.
2. Verifies the RS256 assertion signature against the stored client cert.
3. Validates claims: iss == consumer_key, sub == cert_subject (RFC4514 lower),
   aud == this token endpoint, exp/iat/nbf within bounds, jti not replayed.
4. Issues an access_token (in sandbox, a self-signed RS256 JWT for higher
   fidelity; opaque in pilot/live to match SWIFT's current opaque tokens).
5. Records the token + persists the assertion jti for replay protection.

Also provides ``/oauth2/revoke`` (RFC 7009) and ``verify_bearer_token`` for
downstream route dependencies.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_settings
from core.errors import (
    SEVERITY_FATAL,
    SwiftApiException,
    invalid_token,
    malformed_request,
    token_not_provided,
)
from core.time import epoch_seconds, now_utc
from auth.jti_store import check_and_record
from database import AppCredential, OAuthToken, get_db

router = APIRouter(prefix="/oauth2", tags=["OAuth2"])

JWT_BEARER_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _decode_basic_auth(authorization: Optional[str]) -> tuple[str, str]:
    """Decode an ``Authorization: Basic ...`` header into (key, secret)."""
    if not authorization or not authorization.startswith("Basic "):
        raise malformed_request("Missing or invalid Authorization header (expected Basic)")
    try:
        decoded = base64.b64decode(authorization[6:]).decode("utf-8")
        key, secret = decoded.split(":", 1)
        return key, secret
    except Exception:
        raise malformed_request("Invalid Basic auth encoding")


def _find_credential(db: Session, consumer_key: str, consumer_secret: str) -> AppCredential:
    cred = db.query(AppCredential).filter(
        AppCredential.consumer_key == consumer_key,
        AppCredential.consumer_secret == consumer_secret,
    ).first()
    if not cred:
        raise SwiftApiException("SwAP001", SEVERITY_FATAL, "API Service not provisioned (invalid client credentials)", 401)
    return cred


def _token_audience(request: Request) -> str:
    """The expected ``aud`` claim: this server's token endpoint URL.

    Matches the client's ``aud = endpoint[8:]`` convention (strips ``https://``).
    For the mock we use the request's host + path so the client and server
    agree without a hardcoded URL.
    """
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
) -> str:
    """Verify a JWT-Bearer assertion and return the jti (for replay store).

    Raises ``SwiftApiException`` on any failure.
    """
    if not cred.cert_x5c:
        raise malformed_request("Credential has no PKI certificate; cannot verify assertion")

    x5c_list = __import__("json").loads(cred.cert_x5c)
    if not x5c_list:
        raise malformed_request("Credential has empty x5c chain")

    # Rebuild the PEM cert from the stored x5c base64 DER segment.
    der_b64 = x5c_list[0]
    cert_pem = "-----BEGIN CERTIFICATE-----\n" + der_b64 + "\n-----END CERTIFICATE-----"
    public_key = __import__("cryptography.x509", fromlist=["load_pem_x509_certificate"]).load_pem_x509_certificate(
        cert_pem.encode("utf-8")
    ).public_key()

    expected_aud = _token_audience(request)

    try:
        claims = jwt.decode(
            assertion,
            public_key,
            algorithms=["RS256"],
            audience=expected_aud,
            options={"require": ["exp", "iat", "nbf", "jti", "iss", "sub", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise invalid_token(f"Assertion verification failed: {exc}")

    # Claim-by-claim validation (PyJWT checks exp/iat/aud; we add sub/iss/jti).
    if claims.get("iss") != cred.consumer_key:
        raise invalid_token("Assertion iss does not match consumer key")
    if claims.get("sub") != cred.cert_subject:
        raise invalid_token("Assertion sub does not match certificate subject")

    # Scope check: requested scope must be a subset of allowed_scopes.
    allowed = (cred.allowed_scopes or "").split()
    requested = (requested_scope or "").split()
    if requested:
        missing = [s for s in requested if s not in allowed]
        if missing:
            raise SwiftApiException(
                "SwAP003", SEVERITY_FATAL,
                f"OAuth token has insufficient scope for the requested service: {missing}",
                403,
            )

    # jti replay protection.
    exp_ts = claims.get("exp")
    if not exp_ts:
        raise invalid_token("Assertion missing exp")
    exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
    if check_and_record(db, claims["jti"], exp_dt, app_id=cred.id):
        raise invalid_token("Assertion jti has already been used (replay detected)")

    return claims["jti"]


def _issue_access_token(cred: AppCredential, scope: str) -> tuple[str, int]:
    """Issue an access token. Returns (token, expires_in).

    In sandbox mode we issue an RS256 JWT signed by the mock CA for higher
    fidelity (so the client can decode it). In pilot/live we issue an opaque
    token to match SWIFT's current behaviour (security.md: "SWIFT currently
    uses opaque tokens").
    """
    settings = get_settings()
    expires_in = settings.oauth_token_ttl_default

    if settings.is_sandbox:
        # Self-signed JWT using the mock CA key. The CA key path is derived
        # from the certs dir; if unavailable, fall back to opaque.
        try:
            from core.utils import load_private_key_from_file
            import os
            ca_key_path = os.path.join(settings.certs_ca_dir(), "ca.key")
            if os.path.exists(ca_key_path):
                key = load_private_key_from_file(ca_key_path, password=None)
                now = epoch_seconds()
                payload = {
                    "iss": "swift-mock-oauth",
                    "sub": cred.consumer_key,
                    "iat": now,
                    "nbf": now,
                    "exp": now + expires_in,
                    "jti": secrets.token_hex(16),
                    "scope": scope,
                }
                token = jwt.encode(payload, key, algorithm="RS256")
                return token, expires_in
        except Exception:
            pass  # fall through to opaque

    # Opaque token (matches real SWIFT).
    raw = f"tok:{cred.id}:{secrets.token_hex(32)}:{epoch_seconds()}"
    return hashlib.sha256(raw.encode()).hexdigest(), expires_in


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@router.post("/token", response_model=TokenResponse)
def issue_token(
    request: Request,
    grant_type: str = Form(...),
    assertion: Optional[str] = Form(None),
    scope: str = Form(""),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Issue an OAuth2 access token via the JWT-Bearer grant."""
    if grant_type != JWT_BEARER_GRANT:
        raise malformed_request(
            f"Unsupported grant_type: {grant_type}. Expected {JWT_BEARER_GRANT}"
        )
    if not assertion:
        raise malformed_request("Missing assertion (JWT-Bearer grant requires an assertion)")

    consumer_key, consumer_secret = _decode_basic_auth(authorization)
    cred = _find_credential(db, consumer_key, consumer_secret)
    _verify_assertion(db, request, assertion, cred, scope)

    # Revoke prior active tokens for this app (matches old prototype behaviour
    # and real SWIFT: a new token issuance supersedes the old).
    db.query(OAuthToken).filter(
        OAuthToken.app_id == cred.id,
        OAuthToken.is_revoked == False,  # noqa: E712
    ).update({"is_revoked": True})

    access_token, expires_in = _issue_access_token(cred, scope or " ".join((cred.allowed_scopes or "").split()) or "swift.api")
    token = OAuthToken(
        app_id=cred.id,
        access_token=access_token,
        token_type="Bearer",
        expires_in=expires_in,
        scope=scope or " ".join((cred.allowed_scopes or "").split()) or "swift.api",
    )
    cred.last_used = now_utc()
    db.add(token)
    db.commit()
    db.refresh(token)

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=expires_in,
        scope=token.scope,
    )


@router.post("/revoke")
def revoke_token(
    token: str = Form(...),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Revoke an access token (RFC 7009)."""
    _decode_basic_auth(authorization)  # validate client auth, ignore which client
    record = db.query(OAuthToken).filter(OAuthToken.access_token == token).first()
    if record:
        record.is_revoked = True
        db.commit()
    # RFC 7009: always return 200, even if the token was unknown.
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "revoked"})


# --------------------------------------------------------------------------
# Bearer verification (used by downstream dependencies)
# --------------------------------------------------------------------------

def verify_bearer_token(authorization: Optional[str], db: Session) -> AppCredential:
    """Verify a ``Bearer`` access token. Returns the owning AppCredential.

    Used by ``auth.dependencies.get_cred`` and any route that needs the
    authenticated credential. Raises ``SwiftApiException`` on failure.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise token_not_provided()

    token_str = authorization[7:]
    token = db.query(OAuthToken).filter(
        OAuthToken.access_token == token_str,
        OAuthToken.is_revoked == False,  # noqa: E712
    ).first()
    if not token:
        raise invalid_token()

    # Expiry check with clock-skew tolerance.
    issued = token.issued_at
    if issued.tzinfo is None:
        # SQLite returns naive datetimes; treat them as UTC.
        from datetime import timezone as _tz
        issued = issued.replace(tzinfo=_tz.utc)
    elapsed = (now_utc() - issued).total_seconds()
    settings = get_settings()
    if elapsed > token.expires_in + settings.clock_skew_seconds:
        token.is_revoked = True
        db.commit()
        raise invalid_token("Access token expired")

    cred = db.query(AppCredential).filter(AppCredential.id == token.app_id).first()
    if not cred:
        raise invalid_token("App credential not found for token")

    return cred


def get_token_scopes(authorization: Optional[str], db: Session) -> list[str]:
    """Return the scopes of the bearer token in ``authorization``."""
    if not authorization or not authorization.startswith("Bearer "):
        return []
    token_str = authorization[7:]
    token = db.query(OAuthToken).filter(
        OAuthToken.access_token == token_str,
        OAuthToken.is_revoked == False,  # noqa: E712
    ).first()
    return (token.scope or "").split() if token else []
