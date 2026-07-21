"""Admin credential lifecycle with one-time secret disclosure."""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import require_admin_token
from config import get_settings
from core.security import hash_secret
from core.time import now_utc
from database import AppCredential, OAuthToken, get_db
from scripts.gen_mock_certs import _ensure_dirs, ensure_ca, issue_client_cert

router = APIRouter(
    prefix="/api/credentials",
    tags=["Admin — Credentials"],
    dependencies=[Depends(require_admin_token)],
)

DEFAULT_SCOPES = (
    "swift.api swift.preval swift.swiftref swift.apitracker "
    "swift.apitracker/FullViewer swift.apitracker/Update "
    "swift.messaging swift.fin.send ecny.wallet ecny.ledger ecny.bridge"
)


class CreateCredentialRequest(BaseModel):
    app_name: str = Field(..., min_length=1, max_length=200)
    environment: Literal["sandbox", "pilot", "live"] = "sandbox"
    allowed_scopes: str = DEFAULT_SCOPES
    cert_pem: str | None = None


def _generate_consumer_key() -> str:
    raw = f"ck:{secrets.token_hex(24)}:{now_utc().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _generate_consumer_secret() -> str:
    return secrets.token_urlsafe(48)


def _provision_cert(cred: AppCredential) -> None:
    settings = get_settings()
    if cred.cert_pem:
        from core.utils import load_certificate_from_pem

        loaded = load_certificate_from_pem(cred.cert_pem.encode())
        cred.cert_x5c = json.dumps(loaded.x5c)
        cred.cert_subject = loaded.cert_subject
        return
    if not settings.is_sandbox:
        raise HTTPException(400, "cert_pem is required in pilot/live mode")

    ca_dir, apps_dir = _ensure_dirs()
    ca_key, ca_cert = ensure_ca(ca_dir)
    _, cert_path, subject = issue_client_cert(cred.consumer_key, ca_key, ca_cert, apps_dir)
    with open(cert_path, encoding="utf-8") as fh:
        cred.cert_pem = fh.read()
    from core.utils import load_certificate_from_pem

    loaded = load_certificate_from_pem(cred.cert_pem.encode())
    cred.cert_x5c = json.dumps(loaded.x5c)
    cred.cert_subject = subject


def _public_credential(cred: AppCredential) -> dict:
    return {
        "id": cred.id,
        "app_name": cred.app_name,
        "consumer_key": cred.consumer_key,
        "environment": cred.environment,
        "allowed_scopes": cred.allowed_scopes,
        "cert_subject": cred.cert_subject,
        "created_at": cred.created_at.isoformat() if cred.created_at else "",
        "last_used": cred.last_used.isoformat() if cred.last_used else None,
    }


@router.get("")
def list_credentials(db: Session = Depends(get_db)):
    return [
        _public_credential(c)
        for c in db.query(AppCredential).order_by(AppCredential.created_at.desc()).all()
    ]


@router.post("", status_code=201)
def create_credential(body: CreateCredentialRequest, db: Session = Depends(get_db)):
    raw_secret = _generate_consumer_secret()
    cred = AppCredential(
        app_name=body.app_name.strip(),
        consumer_key=_generate_consumer_key(),
        consumer_secret=hash_secret(raw_secret),
        environment=body.environment,
        allowed_scopes=" ".join(dict.fromkeys(body.allowed_scopes.split())),
        cert_pem=body.cert_pem,
    )
    try:
        _provision_cert(cred)
        db.add(cred)
        db.commit()
        db.refresh(cred)
    except Exception:
        db.rollback()
        raise
    payload = _public_credential(cred)
    payload["consumer_secret"] = raw_secret
    payload["secret_notice"] = "Shown once; store it securely."
    return payload


@router.delete("/{cred_id}")
def delete_credential(cred_id: int, db: Session = Depends(get_db)):
    cred = db.query(AppCredential).filter(AppCredential.id == cred_id).first()
    if not cred:
        raise HTTPException(404, "Credential not found")
    db.query(OAuthToken).filter(OAuthToken.app_id == cred_id).delete()
    db.delete(cred)
    db.commit()
    return {"status": "deleted"}
