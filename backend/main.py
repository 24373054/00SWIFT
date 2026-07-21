"""SWIFT Developer Testing System — FastAPI application assembly.

Replaces the old prototype's ``main.py`` (which mounted a single sandbox
router and served the frontend via FileResponse). Now assembles:

* Lifespan: init_db + seed SwiftRef reference data + JTI cleanup scheduling.
* Middleware: X-Request-ID + audit logging (core.middleware).
* Exception handlers: canonical SWIFT error envelope (core.errors).
* Routers:
  - /oauth2/*           (auth.oauth)
  - /swift-preval/*     (api.preval.router)        [mounted in stage C]
  - /swiftrefdata/*     (api.swiftref.router)      [mounted in stage B]
  - /swift-apitracker/* (api.gpi.router)           [mounted in stage D]
  - /alliancecloud/*    (api.messaging.router)     [mounted in stage E]
  - /api/*              (admin.*)                  [internal, admin-token gated]
* Frontend: served from ../frontend (single-file SPA, retained for now).
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading

from fastapi import Depends, FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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
from version import __version__

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Lifespan
# --------------------------------------------------------------------------


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate env, init DB, seed reference data, schedule JTI cleanup."""
    settings = get_settings()
    if settings.is_live:
        settings.validate_for_live()
        # Safety confirmation for live mode (defensive — would be interactive
        # in a real shell; here we just log via print since uvicorn captures it).
        logger.warning("SWIFT_ENV=live — production mode active")
    elif settings.swift_env == "pilot":
        settings.validate_for_pilot()
        logger.info("SWIFT_ENV=pilot — real SWIFT sandbox hosts")

    init_db()
    seed_reference_data()
    seed_ecny_data()
    logger.info("SWIFT sandbox started", extra={"swift_env": settings.swift_env})

    # Schedule periodic JTI cleanup (every hour) on a background thread.
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

    t = threading.Thread(target=_cleanup_loop, daemon=True)
    t.start()

    yield

    stop_event.set()


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------

app = FastAPI(
    title="SWIFT Developer Testing System",
    description="Local sandbox mirroring SWIFT Developer Portal APIs (OAuth2, Pre-validation, SwiftRef, GPI Tracker, Messaging).",
    version=__version__,
    lifespan=lifespan,
)

# CORS: tightened from the old allow_origins=["*"] + allow_credentials=True
# (which is invalid per the CORS spec). Origins come from config; sandbox
# defaults to localhost.
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # credentials=True with wildcard origins is invalid
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
    ],
)

# X-Request-ID + audit logging.
app.add_middleware(RequestContextMiddleware)

# SWIFT error envelope handlers.
register_exception_handlers(app)

# OAuth2 router.
app.include_router(oauth_router)

# Business and admin routers are imported explicitly so packaging failures are visible.
for business_router in (
    swiftref_router,
    preval_router,
    gpi_router,
    messaging_router,
    catalogue_router,
    ecny_router,
    ecny_admin_router,
):
    app.include_router(business_router)

# Internal admin routers.
app.include_router(credentials_router)
app.include_router(admin_payments_router)
app.include_router(dev_sign_router)


# --------------------------------------------------------------------------
# Internal /api/* — admin-token gated (replaces old unauthenticated /api/*).
# --------------------------------------------------------------------------


def require_admin_token(x_admin_token: str = Header(None, alias="X-Admin-Token")):
    """Require an admin token for /api/* management endpoints.

    In sandbox mode an empty ADMIN_API_TOKEN disables the check (local dev
    convenience). In pilot/live the token is mandatory (validated at startup).

    NOTE: also re-exported from auth.dependencies to avoid circular imports.
    """
    from auth.dependencies import require_admin_token as _impl

    return _impl(x_admin_token)


@app.get("/api/states")
def list_states(_: None = Depends(require_admin_token)):
    """Return the full TransactionIndividualStatus5Code set (frontend source of truth)."""
    from iso20022.states import all_states

    return {"states": all_states()}


@app.get("/api/dashboard/stats")
def dashboard_stats(_: None = Depends(require_admin_token)):
    """Dashboard stats. Reuses the old shape but with real latency data."""
    from database import ApiRequest, AppCredential, OAuthToken, PaymentState

    db = SessionLocal()
    try:
        total_creds = db.query(AppCredential).count()
        active_tokens = db.query(OAuthToken).filter(OAuthToken.is_revoked == False).count()  # noqa: E712
        total_requests = db.query(ApiRequest).count()
        total_payments = db.query(PaymentState).count()
        payment_by_state = {}
        for p in db.query(PaymentState).all():
            payment_by_state[p.transaction_status] = (
                payment_by_state.get(p.transaction_status, 0) + 1
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
                    "id": r.id,
                    "api_name": r.api_name,
                    "method": r.method,
                    "endpoint": r.endpoint,
                    "status": r.response_status,
                    "latency_ms": r.latency_ms,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in recent
            ],
        }
    finally:
        db.close()


# --------------------------------------------------------------------------
# Frontend (single-file SPA — retained; will be split in stage H).
# --------------------------------------------------------------------------

_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(_frontend_dir, "index.html"))


@app.get("/app.js")
def serve_app_js():
    return FileResponse(os.path.join(_frontend_dir, "app.js"), media_type="application/javascript")


@app.get("/style.css")
def serve_style_css():
    return FileResponse(os.path.join(_frontend_dir, "style.css"), media_type="text/css")


@app.get("/health")
def health():
    """Liveness probe (unauthenticated)."""
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
