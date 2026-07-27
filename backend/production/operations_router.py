"""Operational and worker route registration."""

from fastapi import APIRouter

from .router import (
    key_operation,
    list_investigation_cases,
    list_outbox,
    operations_summary_route,
    production_health,
    reconciliation_run,
    run_worker,
)

operations_router = APIRouter(prefix="/production/v1")
operations_router.add_api_route("/health", production_health, methods=["GET"])
operations_router.add_api_route("/investigation-cases", list_investigation_cases, methods=["GET"])
operations_router.add_api_route("/outbox", list_outbox, methods=["GET"])
operations_router.add_api_route("/worker/run", run_worker, methods=["POST"])
operations_router.add_api_route("/operations/summary", operations_summary_route, methods=["GET"])
operations_router.add_api_route("/reconciliation/runs", reconciliation_run, methods=["POST"])
operations_router.add_api_route("/key-operations", key_operation, methods=["POST"])
