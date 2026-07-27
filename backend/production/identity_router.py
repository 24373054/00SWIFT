"""Participant, entitlement, service identity and approval route registration."""

from fastapi import APIRouter

from .router import (
    create_approval,
    create_entitlement,
    create_limit_profile,
    create_participant,
    create_service_identity,
)

identity_router = APIRouter(prefix="/production/v1")
identity_router.add_api_route("/participants", create_participant, methods=["POST"])
identity_router.add_api_route("/participants/{participant_id}/entitlements", create_entitlement, methods=["POST"])
identity_router.add_api_route("/service-identities", create_service_identity, methods=["POST"])
identity_router.add_api_route("/participants/{participant_id}/limit-profiles", create_limit_profile, methods=["POST"])
identity_router.add_api_route("/approvals", create_approval, methods=["POST"])
