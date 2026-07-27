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


def recover_reserve(query, dispatch, reservation_intent_id: str):
    return query_or_dispatch(query, dispatch, reservation_intent_id)


def recover_fx_accept(query, dispatch, trade_intent_id: str):
    return query_or_dispatch(query, dispatch, trade_intent_id)


def recover_message_send(query, dispatch, message_client_reference: str):
    return query_or_dispatch(query, dispatch, message_client_reference)


def recover_settlement_submit(query, dispatch, settlement_client_reference: str):
    return query_or_dispatch(query, dispatch, settlement_client_reference)


def recover_cancel(query, dispatch, cancellation_request_id: str):
    return query_or_dispatch(query, dispatch, cancellation_request_id)


def recover_return(query, dispatch, return_payment_id: str):
    return query_or_dispatch(query, dispatch, return_payment_id)
