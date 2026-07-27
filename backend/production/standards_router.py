"""Standards route registration."""

from fastapi import APIRouter

from .router import production_standard_profiles, production_validate_standard_message

standards_router = APIRouter(prefix="/production/v1")
standards_router.add_api_route("/standards/profiles", production_standard_profiles, methods=["GET"])
standards_router.add_api_route("/standards/validate", production_validate_standard_message, methods=["POST"])
