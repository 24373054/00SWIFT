import pytest

from production.connector_recovery import (
    recover_cancel,
    recover_fx_accept,
    recover_message_send,
    recover_reserve,
    recover_return,
    recover_settlement_submit,
)
from production.connectors import ConnectorResult


@pytest.mark.parametrize(
    ("recover", "reference"),
    [
        (recover_reserve, "reservation-1"),
        (recover_fx_accept, "trade-1"),
        (recover_message_send, "message-1"),
        (recover_settlement_submit, "settlement-1"),
        (recover_cancel, "cancel-1"),
        (recover_return, "return-1"),
    ],
)
def test_each_external_handler_has_query_then_dispatch(recover, reference):
    result = ConnectorResult("test", "sandbox", "FINAL", reference, {})
    calls = []
    recovered, dispatched = recover(lambda _ref: None, lambda ref: calls.append(ref) or result, reference)
    assert recovered.external_reference == reference and dispatched and calls == [reference]
