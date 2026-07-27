from production.connector_recovery import query_or_dispatch
from production.connectors import ConnectorResult


def test_connector_recovery_queries_before_dispatch():
    calls = []
    result = ConnectorResult("test", "sandbox", "FINAL", "ext-1", {})

    recovered, dispatched = query_or_dispatch(lambda ref: result if ref == "client-1" else None, lambda ref: calls.append(ref) or result, "client-1")
    assert recovered is result and not dispatched and calls == []

    fresh, dispatched = query_or_dispatch(lambda _ref: None, lambda ref: calls.append(ref) or result, "client-2")
    assert fresh is result and dispatched and calls == ["client-2"]
