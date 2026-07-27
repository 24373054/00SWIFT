import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database import Base
from production.models import ProductionApproval, ProductionApprovalDecision


def test_approval_decision_is_append_only(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'approval.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        approval = ProductionApproval(approval_id="apr-1", aggregate_type="PAYMENT", aggregate_id="pay-1", action="RELEASE", maker="alice", state="PENDING", reason="reason")
        decision = ProductionApprovalDecision(decision_id="dec-1", approval_id="apr-1", outcome="APPROVED", checker="bob", reason="ok", policy_version="v1")
        db.add_all([approval, decision])
        db.commit()
        decision.reason = "tampered"
        with pytest.raises(ValueError, match="append-only"):
            db.commit()
        db.rollback()
        db.delete(decision)
        with pytest.raises(ValueError, match="append-only"):
            db.commit()
