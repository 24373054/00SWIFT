"""Cross-Border Payment Infrastructure Lab — FastAPI application assembly.

Assembles the authenticated SWIFT-style sandbox, e-CNY subsystem, versioned
standards and settlement research platform, and the institutional React UI.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading

from fastapi import Depends, FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from admin.credentials import router as credentials_router
from admin.dev_sign import router as dev_sign_router
from admin.ecny_admin import router as ecny_admin_router
from admin.payments import router as admin_payments_router
from api.catalogue import router as catalogue_router
from api.ecny.router import router as ecny_router
from api.gpi.router import router as gpi_router
from api.messaging.router import router as messaging_router
from api.preval.router import router as preval_router
from api.swiftref.router import router as swiftref_router
from auth.jti_store import cleanup_expired
from auth.oauth import router as oauth_router
from config import get_settings
from core.errors import register_exception_handlers
from core.middleware import RequestContextMiddleware
from database import SessionLocal, init_db, seed_ecny_data, seed_reference_data
from nextgen.cbdc_router import router as cbdc_router
from nextgen.router import router as nextgen_router
from nextgen.ui_router import router as institutional_ui_router
from version import __version__

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration, initialize persistence and schedule cleanup."""
    settings = get_settings()
    if settings.is_live:
        settings.validate_for_live()
        logger.warning("SWIFT_ENV=live — production mode active")
    elif settings.swift_env == "pilot":
        settings.validate_for_pilot()
        logger.info("SWIFT_ENV=pilot — real SWIFT sandbox hosts")

    init_db()
    seed_reference_data()
    seed_ecny_data()
    logger.info("00SWIFT platform started", extra={"swift_env": settings.swift_env})

    stop_event = threading.Event()

    def _cleanup_loop():
        while not stop_event.wait(3600):
            db = SessionLocal()
            try:
                cleanup_expired(db)
            except Exception:
                logger.exception("JTI cleanup failed")
            finally:
                db.close()

    thread = threading.Thread(target=_cleanup_loop, daemon=True)
    thread.start()
    yield
    stop_event.set()


app = FastAPI(
    title="Cross-Border Payment Infrastructure Lab",
    description=(
        "Independent research sandbox for SWIFT-style APIs, ISO 20022, CIPS, "
        "e-CNY and multi-CBDC settlement workflows. No official certification "
        "or production connectivity is claimed."
    ),
    version=__version__,
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Request-ID",
        "x-bic",
        "X-SWIFT-Signature",
        "X-API-Minor-Version",
        "X-Admin-Token",
        "X-User-Role",
        "X-User-Subject",
        "Idempotency-Key",
    ],
)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)
app.include_router(oauth_router)

for business_router in (
    swiftref_router,
    preval_router,
    gpi_router,
    messaging_router,
    catalogue_router,
    ecny_router,
    ecny_admin_router,
    nextgen_router,
    cbdc_router,
    institutional_ui_router,
):
    app.include_router(business_router)

app.include_router(credentials_router)
app.include_router(admin_payments_router)
app.include_router(dev_sign_router)


def require_admin_token(x_admin_token: str = Header(None, alias="X-Admin-Token")):
    """Require an admin token for management endpoints."""
    from auth.dependencies import require_admin_token as implementation

    return implementation(x_admin_token)


@app.get("/api/states")
def list_states(_: None = Depends(require_admin_token)):
    """Return the full TransactionIndividualStatus5Code set."""
    from iso20022.states import all_states

    return {"states": all_states()}


@app.get("/api/dashboard/stats")
def dashboard_stats(_: None = Depends(require_admin_token)):
    """Return legacy operational dashboard statistics."""
    from database import ApiRequest, AppCredential, OAuthToken, PaymentState

    db = SessionLocal()
    try:
        total_creds = db.query(AppCredential).count()
        active_tokens = (
            db.query(OAuthToken).filter(OAuthToken.is_revoked == False).count()  # noqa: E712
        )
        total_requests = db.query(ApiRequest).count()
        total_payments = db.query(PaymentState).count()
        payment_by_state = {}
        for payment in db.query(PaymentState).all():
            payment_by_state[payment.transaction_status] = (
                payment_by_state.get(payment.transaction_status, 0) + 1
            )
        recent = db.query(ApiRequest).order_by(ApiRequest.created_at.desc()).limit(20).all()
        return {
            "app_credentials": total_creds,
            "active_tokens": active_tokens,
            "total_api_requests": total_requests,
            "total_payments": total_payments,
            "payments_by_state": payment_by_state,
            "recent_requests": [
                {
                    "id": request.id,
                    "api_name": request.api_name,
                    "method": request.method,
                    "endpoint": request.endpoint,
                    "status": request.response_status,
                    "latency_ms": request.latency_ms,
                    "created_at": request.created_at.isoformat() if request.created_at else "",
                }
                for request in recent
            ],
        }
    finally:
        db.close()


_frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
_frontend_dist = os.path.join(_frontend_dir, "dist")
_frontend_index = os.path.join(_frontend_dist, "index.html")
_legacy_index = os.path.join(_frontend_dir, "legacy", "index.html")
if not os.path.isfile(_legacy_index):
    _legacy_index = os.path.join(_frontend_dir, "index.legacy.html")
if not os.path.isfile(_legacy_index):
    _legacy_index = os.path.join(_frontend_dir, "index.html")

_assets_dir = os.path.join(_frontend_dist, "assets")
if os.path.isdir(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="frontend-assets")


@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the built institutional frontend, with the legacy UI as a dev fallback."""
    return FileResponse(_frontend_index if os.path.isfile(_frontend_index) else _legacy_index)


@app.get("/legacy", include_in_schema=False)
def serve_legacy_frontend():
    """Keep the previous developer console available during the migration window."""
    return FileResponse(_legacy_index)


@app.get("/app.js", include_in_schema=False)
def serve_legacy_app_js():
    return FileResponse(
        os.path.join(_frontend_dir, "app.js"),
        media_type="application/javascript",
    )


@app.get("/style.css", include_in_schema=False)
def serve_legacy_style_css():
    return FileResponse(os.path.join(_frontend_dir, "style.css"), media_type="text/css")


@app.get("/health")
def health():
    """Unauthenticated liveness probe."""
    return {"status": "ok", "env": get_settings().swift_env, "version": __version__}


@app.get("/ready")
def readiness():
    """Readiness probe that verifies database connectivity."""
    from sqlalchemy import text

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()
    return {"status": "ready", "version": __version__}


@app.get("/{path:path}", include_in_schema=False)
def serve_frontend_route(path: str):
    """Return the SPA shell for client-side routes without filesystem path resolution."""
    del path
    return FileResponse(_frontend_index if os.path.isfile(_frontend_index) else _legacy_index)
