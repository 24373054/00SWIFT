"""Tenant/participant/service identity/certificate lifecycle routes."""

from fastapi import APIRouter

from .identity_api import (
    create_certificate,
    create_participant,
    create_service_identity,
    create_tenant,
    get_participant,
    get_service_identity,
    get_tenant,
    transition_certificate,
    transition_participant,
    transition_service_identity,
    transition_tenant,
)

identity_router = APIRouter(prefix="/production/v1")
identity_router.add_api_route("/tenants", create_tenant, methods=["POST"])
identity_router.add_api_route("/tenants/{tenant_id}", get_tenant, methods=["GET"])
identity_router.add_api_route("/tenants/{tenant_id}/transition", transition_tenant, methods=["POST"])
identity_router.add_api_route("/participants", create_participant, methods=["POST"])
identity_router.add_api_route("/participants/{participant_id}", get_participant, methods=["GET"])
identity_router.add_api_route("/participants/{participant_id}/transition", transition_participant, methods=["POST"])
identity_router.add_api_route("/service-identities", create_service_identity, methods=["POST"])
identity_router.add_api_route("/service-identities/{identity_id}", get_service_identity, methods=["GET"])
identity_router.add_api_route("/service-identities/{identity_id}/transition", transition_service_identity, methods=["POST"])
identity_router.add_api_route("/certificates", create_certificate, methods=["POST"])
identity_router.add_api_route("/certificates/{certificate_id}/transition", transition_certificate, methods=["POST"])
