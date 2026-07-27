from __future__ import annotations

from .connectors import ConnectorResult


def require_query_on_timeout(result: ConnectorResult) -> ConnectorResult:
    """Convert connector timeout/indeterminate outcomes to QUERY_REQUIRED."""

    if result.state.upper() not in {"TIMEOUT", "UNKNOWN", "UNAVAILABLE"}:
        return result
    return ConnectorResult(result.connector, result.mode, "UNKNOWN", result.external_reference, {**result.evidence, "query_required": True})
