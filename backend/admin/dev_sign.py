"""Dev-only signing helper (sandbox only).

The public SWIFT endpoints (preval, gpi status/cancellation, messaging send)
require an ``X-SWIFT-Signature`` computed with the client's RSA private key.
The private key lives in ``backend/certs/apps/<key>.key`` and is NOT readable
from the browser.

For sandbox dev convenience, this endpoint signs a request body on behalf of a
credential (identified by consumer_key), returning the signature + a valid
bearer token. This lets the frontend exercise the full signed flow without
exposing the private key. DISABLED in pilot/live.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import require_admin_token
from config import get_settings
from core.security import token_digest
from core.time import epoch_seconds, now_utc
from core.utils import load_certificate_from_file, load_private_key_from_file
from database import AppCredential, OAuthToken, get_db

router = APIRouter(
    prefix="/api/dev", tags=["Admin — Dev Helpers"], dependencies=[Depends(require_admin_token)]
)


class SignRequest(BaseModel):
    consumer_key: str
    body: str  # raw request body to sign
    audience: str  # host+path (the aud claim)
    scope: str = ""  # if provided, also mint a bearer token with this scope


class SignResponse(BaseModel):
    signature: str
    access_token: str | None = None
    cert_subject: str


@router.post("/sign", response_model=SignResponse)
def dev_sign(body: SignRequest, db: Session = Depends(get_db)):
    """Sign a request body with a credential's private key (sandbox only).

    Optionally mints a short-lived bearer token so the frontend can call the
    public endpoint in one round-trip.
    """
    settings = get_settings()
    if not settings.is_sandbox:
        raise HTTPException(status_code=403, detail="Dev signing is disabled outside sandbox mode")

    cred = db.query(AppCredential).filter(AppCredential.consumer_key == body.consumer_key).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    key_path = f"{settings.certs_apps_dir()}/{cred.consumer_key}.key"
    crt_path = f"{settings.certs_apps_dir()}/{cred.consumer_key}.crt"
    try:
        priv = load_private_key_from_file(key_path, None)
        loaded = load_certificate_from_file(crt_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Cannot load credential key/cert") from exc

    # Compute the SWIFT double-encoded digest + sign an RS256 JWT (mirrors client.swift_signature).
    body_b64 = base64.b64encode(body.body.encode("utf-8"))
    digest = hashlib.sha256(body_b64).digest()
    digest_b64 = base64.b64encode(digest).decode("utf-8")
    now = epoch_seconds()
    sig_jwt = jwt.encode(
        {
            "iat": now,
            "nbf": now,
            "exp": now + 15,
            "jti": secrets.token_hex(16),
            "sub": cred.cert_subject,
            "aud": body.audience,
            "digest": digest_b64,
        },
        priv,
        algorithm="RS256",
        headers={"alg": "RS256", "x5c": loaded.x5c, "typ": "JWT"},
    )

    # Optionally mint a bearer token (opaque, sandbox-style).
    access_token = None
    if body.scope:
        requested = set(body.scope.split())
        allowed = set((cred.allowed_scopes or "").split())
        if not requested.issubset(allowed):
            raise HTTPException(status_code=403, detail="Requested scope is not allowed")
        access_token = secrets.token_urlsafe(48)
        db.add(
            OAuthToken(
                app_id=cred.id,
                access_token=token_digest(access_token),
                token_type="Bearer",
                expires_in=settings.oauth_token_ttl_default,
                scope=body.scope,
                issued_at=now_utc(),
            )
        )
        cred.last_used = now_utc()
        db.commit()

    return SignResponse(
        signature=sig_jwt, access_token=access_token, cert_subject=cred.cert_subject
    )
