from production.connectors import ConnectorResult
from production.timeout_policy import require_query_on_timeout


def test_external_timeout_becomes_unknown_query_required():
    result = require_query_on_timeout(ConnectorResult("x", "qualified", "TIMEOUT", "client-1", {}))
    assert result.state == "UNKNOWN" and result.evidence["query_required"] is True
