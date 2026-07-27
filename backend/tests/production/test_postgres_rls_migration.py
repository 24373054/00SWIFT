import importlib.util
from pathlib import Path

from sqlalchemy import create_engine


def test_rls_migration_is_explicit_and_sqlite_safe():
    path = Path(__file__).parents[2] / "alembic" / "versions" / "0014_production_rls.py"
    spec = importlib.util.spec_from_file_location("rls_migration", path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    assert migration.POLICIES["prod_payment_orders"]
    assert "current_setting('app.tenant_id', true)" in migration.POLICIES["prod_payment_orders"]
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        assert migration._is_postgres(connection) is False
