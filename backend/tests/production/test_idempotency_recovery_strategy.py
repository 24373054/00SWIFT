import datetime as dt

from production.runtime import ProductionIdempotencyService


def test_expired_started_queries_effect_before_takeover(db):
    service = ProductionIdempotencyService(db)
    record, _ = service.begin("payments", "recover-1", {"amount": 1})
    record.locked_until = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
    db.flush()
    status, result = service.recover_started(record, lambda _scope, _key: {"order_id": "p1"})
    assert status == "COMPLETED" and result["order_id"] == "p1"


def test_expired_started_only_allows_explicit_takeover_when_no_effect(db):
    service = ProductionIdempotencyService(db)
    record, _ = service.begin("payments", "recover-2", {"amount": 1})
    record.locked_until = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
    db.flush()
    status, result = service.recover_started(record, lambda _scope, _key: None)
    assert status == "TAKEOVER_REQUIRED" and result is None
