from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from test_production_domain import _headers, _payment

import production.security as security
from production.router import router
from production.security import ProductionPrincipal, require_production_scope


def _production_routes():
    return [route for route in router.routes if isinstance(route, APIRoute)]


def test_all_routes_have_identity_or_are_public_health():
    routes = _production_routes()
    assert len(routes) >= 30
    for route in routes:
        if route.path == "/production/v1/health":
            continue
        parameters = inspect.signature(route.endpoint).parameters
        assert "principal" in parameters, route.path


def test_no_identity_is_rejected_in_pilot(monkeypatch):
    monkeypatch.setattr(security, "get_settings", lambda: SimpleNamespace(is_sandbox=False, production_require_auth=False))
    with pytest.raises(HTTPException) as exc:
        security.get_production_principal(
            authorization=None,
            participant_header=None,
            user_role_header=None,
            user_subject_header=None,
            credential=None,
            db=None,
        )
    assert exc.value.status_code == 401


def test_wrong_scope_is_rejected_and_admin_cannot_impersonate_scope():
    read_only = ProductionPrincipal("tenant-a", "subject-a", frozenset({"production.read"}), "credential")
    dependency = require_production_scope("production.write")
    with pytest.raises(HTTPException) as exc:
        dependency(read_only)
    assert exc.value.status_code == 403
    assert read_only.can("production.admin") is False


def test_wrong_tenant_cannot_read_other_payment(client):
    created = client.post("/production/v1/payments", json=_payment(), headers=_headers("matrix-tenant"))
    assert created.status_code == 202
    response = client.get(
        f"/production/v1/payments/{created.json()['payment_id']}",
        headers={"X-Participant-ID": "SANDBOX-OTHER"},
    )
    assert response.status_code == 409
