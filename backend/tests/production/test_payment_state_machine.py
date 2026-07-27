import pytest

from production.payment_state_machine import transition_spec


def test_state_machine_spec_has_guards_events_timeouts_and_terminal_semantics():
    transition = transition_spec("CUSTOMER_COMPLETED", "OPERATIONALLY_CLOSED")
    assert transition.guard and transition.event and transition.timeout and transition.compensation and transition.terminal
    with pytest.raises(ValueError):
        transition_spec("CONTROL_CHECKS", "CUSTOMER_COMPLETED")
