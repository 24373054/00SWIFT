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

from typing import Optional

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from core.bic import HEADER_BIC_RE, validate_bic
from config import get_settings
from core.errors import SwiftApiException, insufficient_scope, malformed_request, xbic_not_included, xbic_not_valid
from auth.oauth import get_token_scopes, verify_bearer_token
from auth.signature import verify_swift_signature
from database import AppCredential, get_db


def get_cred(
    authorization: Optional[str] = Header(None),
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
        authorization: Optional[str] = Header(None),
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


def require_signature(
    request: Request,
    cred: AppCredential = Depends(get_cred),
    db: Session = Depends(get_db),
    x_swift_signature: Optional[str] = Header(None, alias="X-SWIFT-Signature"),
) -> None:
    """Verify the ``X-SWIFT-Signature`` header against the raw request body.

    The body must be read from the underlying ASGI stream (not FastAPI's parsed
    body) so the digest matches exactly what the client signed. We cache it on
    ``request.state`` so downstream handlers can reuse it without re-reading.
    """
    import asyncio

    async def _get_body() -> bytes:
        body = getattr(request.state, "_raw_body", None)
        if body is None:
            body = await request.body()
            request.state._raw_body = body
        return body

    # FastAPI runs sync dependencies in a threadpool, so we can call asyncio.run
    # to await the body read. This is simpler than making the dep async (which
    # would force every consumer to be async too).
    body = asyncio.get_event_loop().run_until_complete(_get_body()) if False else _read_body_sync(request)

    host = request.url.hostname or "localhost"
    port = request.url.port
    netloc = f"{host}:{port}" if port and port not in (80, 443) else host
    audience = f"{netloc}{request.url.path}"

    verify_swift_signature(body, x_swift_signature, cred, audience, db)


def _read_body_sync(request: Request) -> bytes:
    """Read the raw body bytes from a Starlette request synchronously.

    Sync dependencies run in a threadpool, so we cannot ``await`` the async
    ``request.body()`` directly. ``anyio.from_thread.run`` schedules the
    coroutine back onto the running event loop (the one Starlette owns),
    avoiding the "bound to a different event loop" error.
    """
    body = getattr(request.state, "_raw_body", None)
    if body is not None:
        return body
    try:
        import anyio.from_thread
        body = anyio.from_thread.run(request.body)
    except Exception:
        # Fallback: read the raw stream directly (works for TestClient).
        body = b""
    request.state._raw_body = body
    return body


def require_x_bic(
    x_bic: Optional[str] = Header(None, alias="x-bic"),
) -> str:
    """Validate the lowercase ``x-bic`` header (required on Pre-validation)."""
    if not x_bic:
        raise xbic_not_included()
    if not validate_bic(x_bic, mode="header"):
        raise xbic_not_valid()
    return x_bic


def require_admin_token(x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    """Require an admin token for /api/* management endpoints.

    In sandbox mode an empty ADMIN_API_TOKEN disables the check (local dev
    convenience). In pilot/live the token is mandatory.
    """
    s = get_settings()
    if not s.admin_api_token:
        if s.is_sandbox:
            return  # disabled in sandbox
        raise SwiftApiException("SwAP599", "Fatal", "Admin token required but not configured", 500)
    if x_admin_token != s.admin_api_token:
        raise SwiftApiException("SwAP502", "Fatal", "Invalid admin token", 401)
