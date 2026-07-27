import inspect

from production.payment_aggregate import PaymentAggregate
from production.service import set_order_state


def test_all_command_paths_require_aggregate_version():
    signature = inspect.signature(set_order_state)
    assert signature.parameters["expected_version"].default is None
    for name in ("authorize", "screen", "reserve", "accept_fx", "deliver_message", "settle", "credit", "cancel", "return_payment", "suspend", "resume", "close"):
        assert "expected_version" in inspect.signature(getattr(PaymentAggregate, name)).parameters
