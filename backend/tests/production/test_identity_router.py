from production.identity_router import identity_router


def test_identity_router_exposes_pending_create_and_transition_endpoints():
    paths = {route.path for route in identity_router.routes}
    assert "/production/v1/tenants" in paths
    assert "/production/v1/participants/{participant_id}/transition" in paths
    assert "/production/v1/service-identities/{identity_id}/transition" in paths
    assert "/production/v1/certificates/{certificate_id}/transition" in paths
