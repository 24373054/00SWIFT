from __future__ import annotations

import pytest

from production.state_constraints import STATE_VERSION, assert_state


def test_state_vocabulary_is_shared_and_rejects_arbitrary_strings():
    assert STATE_VERSION == "state-v1"
    assert assert_state("prod_payment_orders", "CONTROL_CHECKS") == "CONTROL_CHECKS"
    with pytest.raises(ValueError, match="invalid state"):
        assert_state("prod_payment_orders", "MADE_UP_SUCCESS")
