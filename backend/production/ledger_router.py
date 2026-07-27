"""Ledger route registration."""

from fastapi import APIRouter

from .router import (
    ledger_account_create,
    ledger_accounts,
    ledger_journal_create,
    ledger_trial_balance,
)

ledger_router = APIRouter(prefix="/production/v1")
ledger_router.add_api_route("/ledger/trial-balance", ledger_trial_balance, methods=["POST"])
ledger_router.add_api_route("/ledger/accounts", ledger_accounts, methods=["GET"])
ledger_router.add_api_route("/ledger/accounts", ledger_account_create, methods=["POST"])
ledger_router.add_api_route("/ledger/journals", ledger_journal_create, methods=["POST"])
