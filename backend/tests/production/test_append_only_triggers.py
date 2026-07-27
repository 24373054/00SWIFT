from pathlib import Path


def test_postgres_append_only_trigger_migration_is_present():
    text = Path("backend/alembic/versions/0027_append_only_triggers.py").read_text(encoding="utf-8")
    assert "BEFORE UPDATE OR DELETE" in text
    assert "prod_payment_facts" in text and "prod_compliance_decisions" in text
