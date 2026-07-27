import pytest

from production.financial_invariants import (
    assert_maker_checker_distinct,
    assert_validity_window,
    validate_journal_balance,
)


def test_balances_debit_and_credit_per_currency():
    validate_journal_balance([
        {"currency": "CNY", "direction": "DEBIT", "amount_minor": 100},
        {"currency": "CNY", "direction": "CREDIT", "amount_minor": 100},
    ])


def test_unbalanced_or_invalid_entries_are_rejected():
    with pytest.raises(ValueError, match="unbalanced"):
        validate_journal_balance([
            {"currency": "CNY", "direction": "DEBIT", "amount_minor": 100},
            {"currency": "CNY", "direction": "CREDIT", "amount_minor": 99},
        ])
    with pytest.raises(ValueError, match="positive"):
        validate_journal_balance([{ "currency": "CNY", "direction": "DEBIT", "amount_minor": 0 }])


def test_window_and_dual_control_invariants():
    assert_validity_window(1, 2)
    assert_maker_checker_distinct("maker", "checker")
    with pytest.raises(ValueError):
        assert_validity_window(2, 2)
    with pytest.raises(ValueError):
        assert_maker_checker_distinct("same", "same")
