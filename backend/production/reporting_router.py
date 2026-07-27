"""Evidence and regulatory reporting route registration."""

from fastapi import APIRouter

from .router import evidence_get, evidence_legal_hold, regulatory_report

reporting_router = APIRouter(prefix="/production/v1")
reporting_router.add_api_route("/evidence/{evidence_id}", evidence_get, methods=["GET"])
reporting_router.add_api_route("/reporting/reports", regulatory_report, methods=["GET"])
reporting_router.add_api_route("/evidence/{evidence_id}/legal-hold", evidence_legal_hold, methods=["POST"])
