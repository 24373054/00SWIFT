from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from scripts.repair_production_0006 import repair


def _db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'repair.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE prod_participants (participant_id TEXT PRIMARY KEY, tenant_id TEXT)"))
        connection.execute(text("CREATE TABLE prod_payment_orders (order_id TEXT PRIMARY KEY, tenant_id TEXT, initiator_participant TEXT)"))
        connection.execute(text("INSERT INTO prod_participants VALUES ('p-1','tenant:new')"))
        connection.execute(text("INSERT INTO prod_payment_orders VALUES ('o-1','p-1','p-1')"))
    return engine


def test_repair_is_dry_run_by_default_and_execute_requires_dual_control(tmp_path):
    engine = _db(tmp_path)
    dry = repair(engine)
    assert dry["count"] == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT tenant_id FROM prod_payment_orders")).scalar_one() == "p-1"
    with pytest.raises(ValueError, match="operator"):
        repair(engine, execute=True, operator="alice", checker="alice", evidence_id="ev-1")
    done = repair(engine, execute=True, operator="alice", checker="bob", evidence_id="ev-1")
    assert done["executed"] is True
    with engine.connect() as connection:
        assert connection.execute(text("SELECT tenant_id FROM prod_payment_orders")).scalar_one() == "tenant:new"
