"""Upgrade an explicitly provisioned 0003 fixture without losing financial data."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text

LEGACY_URL = os.getenv("PRODUCTION_LEGACY_DB_URL")
if not LEGACY_URL:
    pytest.skip("[EXT-BLOCKED] PRODUCTION_LEGACY_DB_URL is not configured", allow_module_level=True)


def test_0003_fixture_preserves_payment_tenant_amount_and_hash():
    engine = create_engine(LEGACY_URL)
    with engine.connect() as connection:
        before = connection.execute(text("SELECT order_id, tenant_id, amount_minor, payload_hash FROM prod_payment_orders ORDER BY order_id")).mappings().all()
    environment = {**os.environ, "DB_URL": LEGACY_URL, "PYTHONPATH": os.getcwd() + "/backend"}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=environment, check=True)
    with engine.connect() as connection:
        after = connection.execute(text("SELECT order_id, tenant_id, amount_minor, payload_hash FROM prod_payment_orders ORDER BY order_id")).mappings().all()
        assert after == before
        assert "prod_payment_orders" in inspect(connection).get_table_names()
