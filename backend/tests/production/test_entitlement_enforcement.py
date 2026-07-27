import pytest
from fastapi import HTTPException

from production.entitlement_service import EntitlementError
from production.security import ProductionPrincipal, assert_entitlement


def test_entitlement_enforcement_is_default_deny_for_non_sandbox(monkeypatch):
    principal = ProductionPrincipal("A", "subject", frozenset({"production.write"}), "credential")
    monkeypatch.setattr("production.security.get_settings", lambda: type("Settings", (), {"is_sandbox": False})())
    monkeypatch.setattr("production.security.ensure_participant", lambda *_args, **_kwargs: type("Participant", (), {"status": "ACTIVE"})())
    monkeypatch.setattr("production.entitlement_service.EntitlementService.match", lambda *_args, **_kwargs: (_ for _ in ()).throw(EntitlementError("bilateral entitlement not found")))
    with pytest.raises(HTTPException) as exc:
        assert_entitlement(object(), principal, service="payment.create", corridor="CN-HK", currency="CNY", counterparty_id="B")
    assert exc.value.status_code == 403
