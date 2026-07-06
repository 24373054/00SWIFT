"""Internal /api/credentials — application credential CRUD with PKI cert generation.

Replaces the old prototype's unauthenticated ``/api/credentials`` routes.
Now gated by ``require_admin_token`` and, in sandbox mode, automatically
generates a mock CA-signed client cert per credential (so the full JWT-Bearer
OAuth flow works end-to-end without a real SWIFT PKI cert).

In pilot/live mode the cert must be uploaded (POST with cert_pem); the mock
CA is not used.
"""
from __future__ import annotations

import json
import secrets
from typing import Optional

import hashlib
import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_settings
from core.time import now_utc
from auth.dependencies import require_admin_token
from database import AppCredential, OAuthToken, get_db
from scripts.gen_mock_certs import ensure_ca, issue_client_cert, _ensure_dirs

router = APIRouter(prefix="/api/credentials", tags=["Admin — Credentials"], dependencies=[Depends(require_admin_token)])


class CreateCredentialRequest(BaseModel):
    app_name: str
    environment: str = "sandbox"
    allowed_scopes: Optional[str] = "swift.api swift.preval swift.swiftref swift.apitracker swift.apitracker/FullViewer swift.apitracker/Update swift.messaging swift.fin.send"
    # Optional uploaded cert (pilot/live). If absent in sandbox, one is generated.
    cert_pem: Optional[str] = None


def _generate_consumer_key() -> str:
    raw = f"ck:{secrets.token_hex(24)}:{now_utc().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _generate_consumer_secret() -> str:
    raw = f"cs:{secrets.token_hex(32)}:{uuid.uuid4()}"
    return hashlib.sha512(raw.encode()).hexdigest()[:64]


def _provision_cert(cred: AppCredential) -> None:
    """Attach a PKI cert to the credential.

    In sandbox mode, generate a mock CA-signed cert and store its PEM + x5c +
    subject. In pilot/live, the caller must supply ``cert_pem``.
    """
    settings = get_settings()
    if cred.cert_pem:
        # Caller uploaded a cert — derive x5c + subject from it.
        from core.utils import load_certificate_from_pem
        loaded = load_certificate_from_pem(cred.cert_pem.encode("utf-8"))
        cred.cert_x5c = json.dumps(loaded.x5c)
        cred.cert_subject = loaded.cert_subject
        return

    if not settings.is_sandbox:
        raise HTTPException(status_code=400, detail="cert_pem is required in pilot/live mode")

    # Sandbox: generate via mock CA.
    ca_dir, apps_dir = _ensure_dirs()
    ca_key, ca_cert = ensure_ca(ca_dir)
    _, _, subject = issue_client_cert(cred.consumer_key, ca_key, ca_cert, apps_dir)
    # Read the generated cert PEM back into the credential.
    crt_path = f"{apps_dir}/{cred.consumer_key}.crt"
    with open(crt_path, "r", encoding="utf-8") as fh:
        cred.cert_pem = fh.read()
    from core.utils import load_certificate_from_pem
    loaded = load_certificate_from_pem(cred.cert_pem.encode("utf-8"))
    cred.cert_x5c = json.dumps(loaded.x5c)
    cred.cert_subject = subject


@router.get("")
def list_credentials(db: Session = Depends(get_db)):
    creds = db.query(AppCredential).order_by(AppCredential.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "app_name": c.app_name,
            "consumer_key": c.consumer_key,
            "consumer_secret": c.consumer_secret,
            "environment": c.environment,
            "allowed_scopes": c.allowed_scopes,
            "cert_subject": c.cert_subject,
            "created_at": c.created_at.isoformat() if c.created_at else "",
            "last_used": c.last_used.isoformat() if c.last_used else None,
        }
        for c in creds
    ]


@router.post("")
def create_credential(body: CreateCredentialRequest, db: Session = Depends(get_db)):
    key = _generate_consumer_key()
    secret = _generate_consumer_secret()
    cred = AppCredential(
        app_name=body.app_name,
        consumer_key=key,
        consumer_secret=secret,
        environment=body.environment,
        allowed_scopes=body.allowed_scopes,
        cert_pem=body.cert_pem,
    )
    _provision_cert(cred)
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return {
        "id": cred.id,
        "app_name": cred.app_name,
        "consumer_key": cred.consumer_key,
        "consumer_secret": cred.consumer_secret,
        "environment": cred.environment,
        "allowed_scopes": cred.allowed_scopes,
        "cert_subject": cred.cert_subject,
        "created_at": cred.created_at.isoformat() if cred.created_at else "",
    }


@router.delete("/{cred_id}")
def delete_credential(cred_id: int, db: Session = Depends(get_db)):
    cred = db.query(AppCredential).filter(AppCredential.id == cred_id).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    db.query(OAuthToken).filter(OAuthToken.app_id == cred_id).delete()
    db.delete(cred)
    db.commit()
    return {"status": "deleted"}
