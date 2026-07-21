"""Request correlation and privacy-preserving API audit middleware."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import get_settings
from core.security import redact_body

logger = logging.getLogger(__name__)

_AUDITED_PREFIXES = (
    "/oauth2/",
    "/swift-preval/",
    "/swiftrefdata/",
    "/swift-apitracker/",
    "/alliancecloud/",
    "/ecny/v1/",
)


def _is_audited(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _AUDITED_PREFIXES)


def _valid_request_id(value: str) -> bool:
    try:
        uuid.UUID(value)
        return bool(value)
    except (ValueError, AttributeError):
        return False


def _api_name(path: str) -> str:
    prefixes = {
        "/swift-preval/": "Pre-validation",
        "/swiftrefdata/": "SwiftRef",
        "/swift-apitracker/": "GPI Tracker",
        "/alliancecloud/": "Messaging",
        "/oauth2/": "OAuth2",
        "/ecny/v1/": "e-CNY",
    }
    return next((name for prefix, name in prefixes.items() if path.startswith(prefix)), "Unknown")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Echo ``X-Request-ID`` and persist a redacted, bounded audit record."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id", "")
        if not _valid_request_id(request_id):
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        body = await request.body()
        request.state._raw_body = body
        settings = get_settings()
        audit_body = redact_body(
            body,
            request.headers.get("content-type"),
            limit=settings.audit_body_limit,
        )

        started = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - started) * 1000)
        response.headers["X-Request-ID"] = request_id

        if _is_audited(request.url.path):
            try:
                self._write_audit(request, request_id, audit_body, response.status_code, latency_ms)
            except Exception:
                logger.exception("audit write failed", extra={"request_id": request_id})
        return response

    @staticmethod
    def _write_audit(
        request: Request,
        request_id: str,
        body: str,
        status_code: int,
        latency_ms: int,
    ) -> None:
        from core.time import now_utc
        from database import ApiRequest, SessionLocal

        headers = {
            "authorization": "***" if request.headers.get("authorization") else "",
            "content-type": request.headers.get("content-type", ""),
            "x-request-id": request_id,
            "x-bic": request.headers.get("x-bic", ""),
            "x-swift-signature": "***" if request.headers.get("x-swift-signature") else "",
        }
        db = SessionLocal()
        try:
            db.add(
                ApiRequest(
                    api_name=_api_name(request.url.path),
                    method=request.method,
                    endpoint=request.url.path,
                    request_headers=json.dumps(headers),
                    request_body=body,
                    response_status=status_code,
                    response_body="",
                    latency_ms=latency_ms,
                    created_at=now_utc(),
                )
            )
            db.commit()
        finally:
            db.close()
