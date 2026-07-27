"""Two-tenant RLS integration test; requires an explicitly provisioned PostgreSQL URL."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

POSTGRES_URL = os.getenv("PRODUCTION_TEST_POSTGRES_URL")
if not POSTGRES_URL:
    pytest.skip("[EXT-BLOCKED] PRODUCTION_TEST_POSTGRES_URL is not configured", allow_module_level=True)


def _set_context(connection, tenant: str, participant: str) -> None:
    connection.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": tenant})
    connection.execute(text("SELECT set_config('app.participant_id', :participant, true)"), {"participant": participant})
    connection.execute(text("SELECT set_config('app.service_identity', 'rls-test', true)"))


def test_two_tenant_payment_read_write_and_pool_reset():
    engine = create_engine(POSTGRES_URL, pool_size=1, max_overflow=0)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            # The fixture must provide the migrated production schema and two tenants.
            _set_context(connection, "tenant-a", "participant-a")
            count_a = connection.execute(text("SELECT COUNT(*) FROM prod_payment_orders WHERE tenant_id='tenant-a'")).scalar_one()
            _set_context(connection, "tenant-b", "participant-b")
            count_b = connection.execute(text("SELECT COUNT(*) FROM prod_payment_orders WHERE tenant_id='tenant-b'")).scalar_one()
            assert count_a > 0 and count_b > 0, "fixture must contain one payment per tenant"
            _set_context(connection, "tenant-a", "participant-a")
            leaked = connection.execute(text("SELECT COUNT(*) FROM prod_payment_orders WHERE tenant_id='tenant-b'")).scalar_one()
            assert leaked == 0
            leaked_outbox = connection.execute(text("SELECT COUNT(*) FROM prod_outbox_events e JOIN prod_payment_orders o ON o.order_id=e.aggregate_id WHERE o.tenant_id='tenant-b'")).scalar_one()
            leaked_evidence = connection.execute(text("SELECT COUNT(*) FROM prod_evidence_manifests e JOIN prod_payment_orders o ON o.order_id=e.aggregate_id WHERE o.tenant_id='tenant-b'")).scalar_one()
            assert leaked_outbox == 0
            assert leaked_evidence == 0
        finally:
            transaction.rollback()
    with engine.connect() as reused:
        assert reused.execute(text("SELECT current_setting('app.tenant_id', true)")).scalar_one() in ("", None)
    engine.dispose()
