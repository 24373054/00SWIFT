from production.dlq_router import dlq_router


def test_dlq_list_and_detail_routes_are_registered():
    paths = {route.path for route in dlq_router.routes}
    assert paths == {"/production/v1/dlq", "/production/v1/dlq/{event_id}"}
