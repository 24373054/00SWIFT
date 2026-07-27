from __future__ import annotations

import datetime as dt
import hashlib

import pytest

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
