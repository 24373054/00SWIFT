from __future__ import annotations

import inspect

from production.dependencies import (
    ProductionDependencyBundle,
    require_admin_action,
    require_operator_action,
    require_production_read,
    require_production_write,
)


def test_dependency_bundle_exports_all_security_dimensions():
    assert set(ProductionDependencyBundle.__dataclass_fields__) == {
        "principal", "db", "tenant_id", "idempotency_key", "integrity", "audit_context"
    }
    assert "idempotency_key" in inspect.signature(require_production_write).parameters
    assert "integrity" in inspect.signature(require_production_write).parameters
    assert "principal" in inspect.signature(require_production_read).parameters
    assert "principal" in inspect.signature(require_operator_action).parameters
    assert "principal" in inspect.signature(require_admin_action).parameters
