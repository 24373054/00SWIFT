from production.approval_router import approval_router


def test_approval_routes_split_create_and_decision():
    paths = {route.path for route in approval_router.routes}
    assert "/production/v1/approvals" in paths
    assert "/production/v1/approvals/{approval_id}/decisions" in paths
