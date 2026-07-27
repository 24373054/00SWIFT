from production.models import ProductionOutboxEvent
from production.outbox_metrics import snapshot


def test_outbox_metrics_report_lag_retries_and_dlq(db):
    db.add_all([
        ProductionOutboxEvent(event_id="m1", topic="payment.created", schema_version="1.0", partition_key="p1", aggregate_id="p1", tenant_id="t1", participant_id="p1", aggregate_sequence=1, payload="{}", payload_hash="0" * 64, content_hash="0" * 64, status="PENDING", attempts=2),
        ProductionOutboxEvent(event_id="m2", topic="payment.created", schema_version="1.0", partition_key="p2", aggregate_id="p2", tenant_id="t1", participant_id="p1", aggregate_sequence=1, payload="{}", payload_hash="0" * 64, content_hash="0" * 64, status="DEAD_LETTER", attempts=8),
    ])
    db.commit()
    metrics = snapshot(db)
    assert metrics["pending"] == 1 and metrics["dead_letter"] == 1 and metrics["retry_attempts"] == 10
