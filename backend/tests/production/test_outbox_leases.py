import datetime as dt

import pytest

from production.models import ProductionOutboxEvent
from production.runtime import ProductionConflict, ProductionOutboxService


def _event(event_id: str, *, status: str, lease_until=None):
    return ProductionOutboxEvent(
        event_id=event_id,
        topic="payment.created",
        schema_version="1.0",
        partition_key="p1",
        aggregate_id="p1",
        tenant_id="t1",
        participant_id="p1",
        aggregate_sequence=1,
        payload="{}",
        payload_hash="0" * 64,
        content_hash="0" * 64,
        status=status,
        lease_until=lease_until,
    )


def test_null_lease_is_reclaimable_and_heartbeat_fences_owner(db):
    event = _event("lease-null", status="PROCESSING")
    db.add(event)
    db.commit()
    claimed = ProductionOutboxService(db).claim(owner="worker-a")
    assert claimed and claimed[0].lease_owner == "worker-a"
    service = ProductionOutboxService(db)
    service.heartbeat(claimed[0], owner="worker-a")
    with pytest.raises(ProductionConflict, match="fencing"):
        service.heartbeat(claimed[0], owner="worker-b")


def test_expired_lease_is_reclaimable_and_old_owner_cannot_complete(db):
    event = _event("lease-expired", status="PROCESSING", lease_until=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1))
    db.add(event)
    db.commit()
    claimed = ProductionOutboxService(db).claim(owner="worker-b")
    assert claimed and claimed[0].lease_owner == "worker-b"
    claimed[0].lease_owner = "worker-a"
    with pytest.raises(ProductionConflict, match="fencing"):
        ProductionOutboxService(db).complete(claimed[0], owner="worker-b")
