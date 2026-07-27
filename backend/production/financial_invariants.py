"""Pure, deterministic validators for ledger and approval invariants."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def assert_validity_window(valid_from, valid_to) -> None:
    if valid_to is not None and valid_to <= valid_from:
        raise ValueError("valid_to must be later than valid_from")


def assert_maker_checker_distinct(maker: str, checker: str | None) -> None:
    if checker is not None and maker == checker:
        raise ValueError("maker and checker must be distinct")


def validate_journal_balance(entries: Iterable[Mapping[str, object]]) -> None:
    """Require equal debit/credit totals per currency before posting a journal."""
    totals: dict[str, dict[str, int]] = {}
    for entry in entries:
        currency = str(entry["currency"])
        direction = str(entry["direction"])
        amount = int(entry["amount_minor"])
        if direction not in {"DEBIT", "CREDIT"} or amount <= 0:
            raise ValueError("journal entries require positive DEBIT/CREDIT amounts")
        bucket = totals.setdefault(currency, {"DEBIT": 0, "CREDIT": 0})
        bucket[direction] += amount
    if not totals:
        raise ValueError("journal must contain at least one entry")
    unbalanced = {currency: values for currency, values in totals.items() if values["DEBIT"] != values["CREDIT"]}
    if unbalanced:
        raise ValueError(f"journal is unbalanced by currency: {unbalanced}")
