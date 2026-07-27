from production.service import ALLOWED_ORDER_TRANSITIONS


def test_shortcut_completion_transitions_are_removed():
    assert "CUSTOMER_COMPLETED" not in ALLOWED_ORDER_TRANSITIONS["CONTROL_CHECKS"]
    assert "CUSTOMER_COMPLETED" not in ALLOWED_ORDER_TRANSITIONS["RESERVATION_PENDING"]
