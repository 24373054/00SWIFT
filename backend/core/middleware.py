"""HTTP middleware: X-Request-ID propagation and request auditing.

Implements two SWIFT-API-Guide requirements:

1. **X-Request-ID** (``http-headers.md`` §Trace Identifier): the consumer may
   send an optional ``X-Request-ID`` (UUID v4); the server copies it into the
   response header for request/response correlation. If absent, the server
   generates one.

2. **Audit logging**: every request to a SWIFT API path is recorded in the
   ``api_requests`` table with the **real measured latency** (replacing the
   old prototype's hardcoded ``120``/``95``/``80`` ms constants in
   ``sandbox.log_api_request`` — which also had a double-``commit()`` bug).
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# Paths that get audited to the api_requests table.
_AUDITED_PREFIXES = (
    "/oauth2/",
    "/swift-preval/",
    "/swiftrefdata/",
    "/swift-apitracker/",
    "/alliancecloud/",
)


def _is_audited(path: str) -> bool:
    return any(path.startswith(p) for p in _AUDITED_PREFIXES)


def _valid_request_id(value: str) -> bool:
    """A relaxed UUID check — accept any UUID version, not just v4."""
    if not value:
        return False
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Injects/echoes ``X-Request-ID`` and records audit rows.

    The audit row is written *after* the response is sent, so the recorded
    latency includes the full request handling time. The request body is
    captured for logging only (not the response body, to avoid buffering large
    responses); the response status is recorded.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # --- X-Request-ID ---
        request_id = request.headers.get("x-request-id", "")
        if not _valid_request_id(request_id):
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Capture request body for audit (read once, re-inject for downstream).
        body_bytes = await request.body()
        audit_body = body_bytes.decode("utf-8", errors="replace")[:4000] if body_bytes else ""

        start = time.perf_counter()
        response: Response = await call_next(request)
        latency_ms = int((time.perf_counter() - start) * 1000)

        response.headers["X-Request-ID"] = request_id

        # --- audit ---
        if _is_audited(request.url.path):
            try:
                self._write_audit(request, request_id, audit_body, response.status_code, latency_ms)
            except Exception:
                # Audit failures must never break the response.
                pass

        return response

    def _write_audit(
        self,
        request: Request,
        request_id: str,
        body: str,
        status_code: int,
        latency_ms: int,
    ) -> None:
        """Insert an ApiRequest row. Imported lazily to avoid circular imports."""
        from database import ApiRequest, SessionLocal
        from core.time import now_utc

        # Derive an "api_name" from the path for human-readable grouping.
        path = request.url.path
        if path.startswith("/swift-preval/"):
            api_name = "Pre-validation"
        elif path.startswith("/swiftrefdata/"):
            api_name = "SwiftRef"
        elif path.startswith("/swift-apitracker/"):
            api_name = "GPI Tracker"
        elif path.startswith("/alliancecloud/"):
            api_name = "Messaging"
        elif path.startswith("/oauth2/"):
            api_name = "OAuth2"
        else:
            api_name = "Unknown"

        headers_for_audit = {"authorization": "***", "x-request-id": request_id, "x-bic": request.headers.get("x-bic", "")}

        db = SessionLocal()
        try:
            db.add(
                ApiRequest(
                    api_name=api_name,
                    method=request.method,
                    endpoint=path,
                    request_headers=json.dumps(headers_for_audit, default=str),
                    request_body=body,
                    response_status=status_code,
                    response_body="",  # not captured (see class docstring)
                    latency_ms=latency_ms,  # real measured latency, not hardcoded
                    created_at=now_utc(),
                )
            )
            db.commit()  # single commit — old prototype committed twice (sandbox.py:42-43)
        finally:
            db.close()
