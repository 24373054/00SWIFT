"""100-way limit contention test; requires a dedicated PostgreSQL fixture."""

from __future__ import annotations

import datetime as dt
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from production.limit_reservation import LimitReservationError, LimitReservationService

POSTGRES_URL = os.getenv("PRODUCTION_TEST_POSTGRES_URL")
if not POSTGRES_URL:
    pytest.skip("[EXT-BLOCKED] PRODUCTION_TEST_POSTGRES_URL is not configured", allow_module_level=True)


def test_one_hundred_requests_never_exceed_daily_limit():
    scope = f"concurrency-{uuid.uuid4().hex}"

    def reserve(_index: int) -> bool:
        engine = create_engine(POSTGRES_URL)
        with Session(engine) as db:
            try:
                LimitReservationService(db).reserve(tenant_id=scope, participant_id="p", service="payment.create", corridor="CN-HK", currency="CNY", business_date=dt.date.today(), amount_minor=2, daily_limit_minor=100, exposure_limit_minor=None)
                db.commit()
                return True
            except LimitReservationError:
                db.rollback()
                return False
            finally:
                engine.dispose()

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(reserve, range(100)))
    assert sum(results) <= 50
