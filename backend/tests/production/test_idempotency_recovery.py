import datetime as dt

import pytest

from production.runtime import ProductionConflict, ProductionIdempotencyService


def test_idempotency_replay_conflict_and_timeout_takeover(db):
    service = ProductionIdempotencyService(db)
    record, replay = service.begin("payments", "k1", {"amount": 1}, owner="w1", trace_id="t1")
    assert not replay and record.status == "STARTED" and record.attempt == 1
    with pytest.raises(ProductionConflict, match="in progress"):
        service.begin("payments", "k1", {"amount": 1}, owner="w2")
    with pytest.raises(ProductionConflict, match="different payload"):
        service.begin("payments", "k1", {"amount": 2})
    record.locked_until = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
    db.flush()
    taken, replay = service.begin("payments", "k1", {"amount": 1}, owner="w2", trace_id="t2")
    assert not replay and taken.owner == "w2" and taken.attempt == 2
    service.complete(taken, 202, {"ok": True})
    replayed, is_replay = service.begin("payments", "k1", {"amount": 1})
    assert is_replay and replayed.response_status == 202


def test_retryable_failure_can_be_retried_but_final_failure_cannot(db):
    service = ProductionIdempotencyService(db)
    record, _ = service.begin("payments", "k2", {"amount": 1})
    service.fail(record, "connector timeout")
    retried, replay = service.begin("payments", "k2", {"amount": 1})
    assert not replay and retried.status == "STARTED"
    service.fail(retried, "invalid request", final=True)
    with pytest.raises(ProductionConflict, match="FAILED_FINAL"):
        service.begin("payments", "k2", {"amount": 1})
