"""FastAPI dependencies for auth: scope/signature/x-bic checks.

Usage in routes::

    @router.post("/payments/{uetr}/cancellation")
    def cancel(
        uetr: str,
        body: CamtA0600104,
        cred: AppCredential = Depends(get_cred),
        _: None = Depends(require_scopes("swift.apitracker/Update")),
        __: None = Depends(require_signature),
        ___: str = Depends(require_x_bic),  # preval only
    ):
        ...

``get_cred`` resolves the bearer token to an ``AppCredential``.
``require_scopes`` checks the token's scope is a superset of the required set.
``require_signature`` verifies ``X-SWIFT-Signature`` against the raw body.
``require_x_bic`` validates the lowercase ``x-bic`` header (Pre-validation).
"""

from __future__ import annotations

import secrets

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from auth.oauth import get_token_scopes, verify_bearer_token
from auth.signature import verify_swift_signature
from config import get_settings
from core.bic import validate_bic
from core.errors import (
    SwiftApiException,
    insufficient_scope,
    xbic_not_included,
    xbic_not_valid,
)
from database import AppCredential, get_db


def get_cred(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> AppCredential:
    """Resolve the Bearer token to the owning AppCredential."""
    return verify_bearer_token(authorization, db)


def require_scopes(*required: str):
    """Dependency factory: require the token to carry all ``required`` scopes.

    A token with a broad scope (e.g. ``swift.api``) satisfies any narrower
    requirement, matching the old prototype's loose scope model. For
    sandbox simplicity, an empty required list passes.
    """
    required_set = set(required)

    def _check(
        authorization: str | None = Header(None),
        db: Session = Depends(get_db),
    ) -> None:
        if not required_set:
            return
        token_scopes = set(get_token_scopes(authorization, db))
        # ``swift.api`` is a wildcard scope that satisfies everything.
        if "swift.api" in token_scopes:
            return
        missing = required_set - token_scopes
        if missing:
            raise insufficient_scope(" ".join(sorted(missing)))

    return _check


async def require_signature(
    request: Request,
    cred: AppCredential = Depends(get_cred),
    db: Session = Depends(get_db),
    x_swift_signature: str | None = Header(None, alias="X-SWIFT-Signature"),
) -> None:
    """Verify the signature against the exact cached ASGI request body."""
    body = getattr(request.state, "_raw_body", None)
    if body is None:
        body = await request.body()
        request.state._raw_body = body

    host = request.url.hostname or "localhost"
    port = request.url.port
    netloc = f"{host}:{port}" if port and port not in (80, 443) else host
    audience = f"{netloc}{request.url.path}"
    verify_swift_signature(body, x_swift_signature, cred, audience, db)


def require_x_bic(
    x_bic: str | None = Header(None, alias="x-bic"),
) -> str:
    """Validate the lowercase ``x-bic`` header (required on Pre-validation)."""
    if not x_bic:
        raise xbic_not_included()
    if not validate_bic(x_bic, mode="header"):
        raise xbic_not_valid()
    return x_bic


def require_admin_token(x_admin_token: str | None = Header(None, alias="X-Admin-Token")):
    """Require an admin token for /api/* management endpoints.

    In sandbox mode an empty ADMIN_API_TOKEN disables the check (local dev
    convenience). In pilot/live the token is mandatory.
    """
    s = get_settings()
    if not s.admin_api_token:
        if s.is_sandbox:
            return  # disabled in sandbox
        raise SwiftApiException("SwAP599", "Fatal", "Admin token required but not configured", 500)
    if not x_admin_token or not secrets.compare_digest(x_admin_token, s.admin_api_token):
        raise SwiftApiException("SwAP502", "Fatal", "Invalid admin token", 401)
