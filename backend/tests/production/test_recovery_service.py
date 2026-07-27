from production.connectors import ConnectorResult
from production.recovery_service import RecoveryService


def test_unknown_external_outcome_opens_case_without_guessing(db):
    result = ConnectorResult("x", "qualified", "UNKNOWN", "client-1", {"query_required": True})
    response = RecoveryService(db).recover("missing-order", "client-1", lambda _ref: result, lambda _ref: result)
    assert response["state"] == "CASE_OPENED" and response["dispatched"] is False
