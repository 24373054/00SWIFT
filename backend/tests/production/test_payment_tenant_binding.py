from production.security import ProductionPrincipal


def test_production_principal_tenant_is_derived_from_participant():
    principal = ProductionPrincipal("P1", "subject", frozenset({"production.write"}), "test")
    assert principal.tenant_id == "tenant:P1"
