from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import production.router as production_router
from production.router import ApprovalRequest
from production.security import ProductionPrincipal


def test_trial_balance_is_read_get_and_worker_is_not_public_outside_sandbox(client):
    schema = client.get("/openapi.json").json()
    trial = schema["paths"]["/production/v1/ledger/trial-balance"]
    assert "get" in trial
    assert "post" not in trial
    monkey = pytest.MonkeyPatch()
    monkey.setattr(production_router, "get_settings", lambda: SimpleNamespace(is_sandbox=False))
    try:
        with pytest.raises(HTTPException) as exc:
            production_router.run_worker(ProductionPrincipal("p", "s", frozenset({"production.worker"}), "test"), None)
        assert exc.value.status_code == 404
    finally:
        monkey.undo()


def test_mutation_handlers_have_integrity_dependency_or_are_internal_worker():
    mutation_names = [
        "create_payment", "open_investigation_case", "request_quote", "accept_quote",
        "cancellation_request", "return_request", "create_participant", "create_entitlement",
        "create_service_identity", "create_limit_profile", "create_approval", "reconciliation_run",
        "ledger_account_create", "ledger_journal_create", "evidence_legal_hold", "production_validate_standard_message",
    ]
    for name in mutation_names:
        assert "_integrity" in inspect.signature(getattr(production_router, name)).parameters


def test_approval_cannot_self_approve(db):
    principal = ProductionPrincipal("p", "alice", frozenset({"production.admin"}), "test")
    with pytest.raises(HTTPException) as exc:
        production_router.create_approval(
            ApprovalRequest(aggregate_type="PAYMENT", aggregate_id="p-1", action="APPROVE", maker="alice", checker="alice", reason="self"),
            principal,
            db,
            None,
        )
    assert exc.value.status_code == 409
