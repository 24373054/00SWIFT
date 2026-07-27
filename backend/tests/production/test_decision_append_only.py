import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from production.models import ProductionAuthorizationDecision, ProductionComplianceDecision


def test_authorization_and_compliance_decisions_cannot_update_or_delete(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'decisions.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    auth = ProductionAuthorizationDecision(decision_id="a1", order_id="missing", outcome="PENDING", payment_hash="0" * 64, input_hash="0" * 64, rule_version="v1")
    comp = ProductionComplianceDecision(decision_id="c1", order_id="missing", outcome="PENDING", input_hash="0" * 64, rule_version="v1")
    session.add_all([auth, comp])
    session.commit()
    with pytest.raises(ValueError, match="append-only"):
        auth.outcome = "PASSED"
        session.flush()
    session.rollback()
    with pytest.raises(ValueError, match="append-only"):
        session.delete(comp)
        session.flush()
