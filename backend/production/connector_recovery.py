"""Crash-safe external connector invocation by stable client reference."""

from __future__ import annotations

from collections.abc import Callable

from .connectors import ConnectorResult


def query_or_dispatch(
    query: Callable[[str], ConnectorResult | None],
    dispatch: Callable[[str], ConnectorResult],
    client_reference: str,
) -> tuple[ConnectorResult, bool]:
    """Return an existing external outcome, or dispatch once when absent.

    The boolean indicates whether a new external call was made.  Callers must
    persist the client reference before invoking this helper.
    """

    if not client_reference.strip():
        raise ValueError("stable connector client reference is required")
    existing = query(client_reference)
    if existing is not None:
        return existing, False
    return dispatch(client_reference), True
