from __future__ import annotations

from sqlalchemy import create_engine, text

from scripts.audit_production_data import audit


def test_audit_is_read_only_and_reports_machine_readable_findings(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE prod_payment_orders (order_id TEXT, tenant_id TEXT, payload_hash TEXT, amount_minor INTEGER)"))
        connection.execute(text("INSERT INTO prod_payment_orders VALUES ('order-1', NULL, '', -1)"))
    report = audit(engine)
    assert report["finding_count"] >= 2
    assert any(item["type"] == "null_or_empty" for item in report["findings"])
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM prod_payment_orders")).scalar_one() == 1
