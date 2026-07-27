"""Observability contract with a dependency-free fallback.

Deployments may install OpenTelemetry exporters around these hooks. The
fallback keeps trace/correlation fields deterministic and never turns a
payment failure into an observability failure.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import time
import uuid
from collections.abc import Iterator

from config import get_settings

_worker_heartbeat_at: dt.datetime | None = None


@contextlib.contextmanager
def span(name: str, **attributes) -> Iterator[dict[str, object]]:
    started = time.perf_counter()
    state: dict[str, object] = {"name": name, "trace_id": f"trace_{uuid.uuid4().hex}", **attributes}
    try:
        yield state
    finally:
        state["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)


def health_snapshot() -> dict[str, object]:
    return {"telemetry": "contract-fallback", "tracing": "not-configured", "metrics": "not-configured", "logs": "structured"}


def record_worker_heartbeat(now: dt.datetime | None = None) -> None:
    global _worker_heartbeat_at
    _worker_heartbeat_at = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)


def dependency_snapshot(db=None) -> dict[str, object]:
    """Return explicit dependency state; simulation is never production-ready."""
    settings = get_settings()
    checks: dict[str, dict[str, object]] = {}
    if db is None:
        checks["database"] = {"available": False, "status": "unavailable", "detail": "database session missing"}
    else:
        try:
            from sqlalchemy import text

            db.execute(text("SELECT 1"))
            checks["database"] = {"available": True, "status": "ok"}
        except Exception as exc:  # noqa: BLE001 - health must report dependency failure
            checks["database"] = {"available": False, "status": "unavailable", "detail": str(exc)}

    checks["broker"] = {
        "available": bool(settings.production_broker_url),
        "status": "configured" if settings.production_broker_url else "unconfigured",
    }
    checks["hsm"] = {
        "available": settings.production_hsm_provider == "qualified",
        "status": settings.production_hsm_provider,
    }
    checks["signature_verifier"] = {
        "available": settings.production_signature_verifier == "qualified",
        "status": settings.production_signature_verifier,
    }

    from .connectors import connector_capabilities

    capabilities = connector_capabilities()
    checks["connector"] = {
        "available": bool(capabilities.get("qualified")),
        "status": "qualified" if capabilities.get("qualified") else capabilities.get("mode"),
        "detail": capabilities,
    }

    if db is None:
        checks["standards_artifact"] = {"available": False, "status": "unavailable"}
    else:
        try:
            from .models import ProductionStandardArtifact

            artifact = db.query(ProductionStandardArtifact).filter_by(status="ACTIVE").order_by(ProductionStandardArtifact.id.desc()).first()
            available = artifact is not None and not (not settings.is_sandbox and artifact.simulation_only)
            checks["standards_artifact"] = {
                "available": available,
                "status": "ok" if available else "missing_or_simulation",
                "artifact_id": artifact.artifact_id if artifact else None,
            }
        except Exception as exc:  # noqa: BLE001 - health must report dependency failure
            checks["standards_artifact"] = {"available": False, "status": "unavailable", "detail": str(exc)}

    if db is None:
        checks["corridor_admission"] = {"available": False, "status": "unavailable"}
    else:
        try:
            from .models import ProductionControlAttestation, ProductionCorridorAdmission

            admission = db.query(ProductionCorridorAdmission).filter_by(
                environment=settings.swift_env, status="ACTIVE"
            ).order_by(ProductionCorridorAdmission.id.desc()).first()
            now = dt.datetime.now(dt.UTC)
            valid = bool(admission and admission.valid_from.replace(tzinfo=dt.UTC) <= now <= admission.valid_to.replace(tzinfo=dt.UTC))
            production_eligible = bool(admission and (settings.is_sandbox or not admission.simulation_only))
            attested = bool(admission and db.query(ProductionControlAttestation).filter_by(admission_id=admission.admission_id, status="ACTIVE").first())
            available = bool(admission and valid and production_eligible and attested)
            checks["corridor_admission"] = {
                "available": available,
                "status": "ok" if available else "missing_or_expired",
                "admission_id": admission.admission_id if admission else None,
                "rulebook_version": admission.rulebook_version if admission else None,
                "valid_to": admission.valid_to.isoformat() if admission else None,
            }
        except Exception as exc:  # noqa: BLE001 - health must report dependency failure
            checks["corridor_admission"] = {"available": False, "status": "unavailable", "detail": str(exc)}

    now = dt.datetime.now(dt.UTC)
    age = None if _worker_heartbeat_at is None else (now - _worker_heartbeat_at).total_seconds()
    heartbeat_ok = age is not None and age <= settings.production_worker_heartbeat_timeout_seconds
    checks["worker_heartbeat"] = {
        "available": heartbeat_ok,
        "status": "ok" if heartbeat_ok else "stale_or_missing",
        "age_seconds": age,
    }
    required = ("database", "broker", "hsm", "signature_verifier", "connector", "standards_artifact", "corridor_admission", "worker_heartbeat")
    ready = settings.swift_env != "sandbox" and all(bool(checks[key]["available"]) for key in required)
    return {"ready": ready, "environment": settings.swift_env, "checks": checks}
