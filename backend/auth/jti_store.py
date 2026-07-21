"""JTI replay-protection store.

Records the ``jti`` claim of every verified JWT (OAuth assertion or signature
JWT) so the same token cannot be replayed. Two tiers:

* In-process LRU cache (fast path, default 10000 entries).
* ``JtiRecord`` DB table (durable, survives restarts).

A ``jti`` is accepted only if it is not already present. After insertion it
is kept until ``expires_at`` (the source JWT's ``exp``); a periodic cleanup
deletes expired rows.

In sandbox mode the DB tier can be skipped for speed, but it is always used
by default to match real SWIFT replay-protection semantics.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import datetime

from sqlalchemy.orm import Session

from core.time import now_utc
from database import JtiRecord


class _LruJtiCache:
    """Thread-safe LRU set of recently-seen JTIs."""

    def __init__(self, capacity: int = 10000):
        self._capacity = capacity
        self._lock = threading.Lock()
        self._data: OrderedDict[str, datetime] = OrderedDict()

    def seen(self, jti: str, expires_at: datetime) -> bool:
        """Return True if ``jti`` was already recorded; else record it and return False."""
        with self._lock:
            if jti in self._data:
                # Refresh expiry on re-touch (harmless; the DB is authoritative).
                return True
            self._data[jti] = expires_at
            self._data.move_to_end(jti)
            while len(self._data) > self._capacity:
                self._data.popitem(last=False)
            return False


_cache = _LruJtiCache()


def check_and_record(
    db: Session, jti: str, expires_at: datetime, app_id: int | None = None
) -> bool:
    """Return True if ``jti`` is a replay (already seen), else record it.

    Checks the LRU cache first, then the DB. On first sight, inserts into both.
    """
    if not jti:
        # A missing jti is itself a replay risk; treat as seen-but-allow so the
        # caller can decide. Real SWIFT requires jti, so the OAuth/signature
        # verifiers reject missing jti before reaching here.
        return False

    if _cache.seen(jti, expires_at):
        return True

    # DB check (authoritative).
    existing = db.query(JtiRecord).filter(JtiRecord.jti == jti).first()
    if existing is not None:
        return True

    db.add(JtiRecord(jti=jti, app_id=app_id, expires_at=expires_at, created_at=now_utc()))
    db.commit()
    return False


def cleanup_expired(db: Session) -> int:
    """Delete expired JTI records. Returns the number deleted."""
    now = now_utc()
    deleted = (
        db.query(JtiRecord).filter(JtiRecord.expires_at < now).delete(synchronize_session=False)
    )
    db.commit()
    # Also prune the in-memory cache.
    with _cache._lock:
        stale = [jti for jti, exp in _cache._data.items() if exp < now]
        for jti in stale:
            _cache._data.pop(jti, None)
    return deleted
