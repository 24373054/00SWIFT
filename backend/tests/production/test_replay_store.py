from __future__ import annotations

import datetime as dt
import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from production.models import ProductionRequestNonce
from production.replay import NonceReplayError, NonceReplayStore


def test_nonce_store_atomically_rejects_duplicate_and_digest_mismatch(db):
    store = NonceReplayStore(db)
    expiry = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5)
    digest = hashlib.sha256(b"request-a").hexdigest()
    store.consume(trust_domain="cn-hk", key_id="key-1", nonce="n-1", request_digest=digest, expires_at=expiry)
    db.commit()
    with pytest.raises(NonceReplayError, match="replay"):
        store.consume(trust_domain="cn-hk", key_id="key-1", nonce="n-1", request_digest=digest, expires_at=expiry)
    with pytest.raises(NonceReplayError, match="different request digest"):
        store.consume(trust_domain="cn-hk", key_id="key-1", nonce="n-1", request_digest="f" * 64, expires_at=expiry)


def test_nonce_scope_and_expiry_are_enforced(db):
    store = NonceReplayStore(db)
    expiry = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5)
    record = store.consume(trust_domain="cn-hk", key_id="key-1", nonce="n-1", request_digest="a" * 64, expires_at=expiry)
    assert record.trust_domain == "cn-hk"
    other_domain = store.consume(trust_domain="hk-cn", key_id="key-1", nonce="n-1", request_digest="a" * 64, expires_at=expiry)
    assert other_domain.nonce == "n-1"
    with pytest.raises(NonceReplayError, match="expired"):
        store.consume(trust_domain="cn-hk", key_id="key-2", nonce="expired", request_digest="a" * 64, expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1))


def test_concurrent_nonce_use_has_one_winner(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'replay.db'}", connect_args={"check_same_thread": False})
    ProductionRequestNonce.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    barrier = Barrier(2)
    expiry = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5)

    def attempt():
        session = sessions()
        try:
            barrier.wait()
            NonceReplayStore(session).consume(
                trust_domain="cn-hk", key_id="key-1", nonce="concurrent-1", request_digest="a" * 64, expires_at=expiry
            )
            session.commit()
            return "accepted"
        except Exception as exc:  # noqa: BLE001 - loser may surface as integrity/replay error
            session.rollback()
            return type(exc).__name__
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert results.count("accepted") == 1
