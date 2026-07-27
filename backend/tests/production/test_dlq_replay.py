import pytest
from fastapi import HTTPException

from production.dlq_replay import approve_replay, create_replay
from production.models import ProductionOutboxEvent
from production.security import ProductionPrincipal


def _event():
    return ProductionOutboxEvent(
        event_id="dlq-1", topic="payment.created", schema_version="1.0", partition_key="p1",
        aggregate_id="p1", tenant_id="tenant:P1", participant_id="P1", aggregate_sequence=1,
        payload="{}", payload_hash="a" * 64, content_hash="a" * 64, status="DEAD_LETTER", attempts=8,
    )


def _principal(subject):
    return ProductionPrincipal("P1", subject, frozenset({"production.operator"}), "test")


def test_dlq_replay_requires_dual_control_and_preserves_hash(db):
    db.add(_event())
    db.commit()
    request = create_replay(db, _principal("alice"), "dlq-1", "connector outcome query complete")
    with pytest.raises(HTTPException, match="distinct"):
        approve_replay(db, _principal("alice"), request.replay_id)
    approved = approve_replay(db, _principal("bob"), request.replay_id)
    assert approved.state == "APPROVED"
    assert db.query(ProductionOutboxEvent).filter_by(event_id="dlq-1").one().status == "PENDING"
    with pytest.raises(HTTPException, match="pending"):
        approve_replay(db, _principal("carol"), request.replay_id)
