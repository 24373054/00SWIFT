"""Timezone-aware UTC time helpers.

Replaces the deprecated ``datetime.datetime.utcnow()`` (Python 3.12+) which
returns a naive datetime and is a latent bug for any timezone-aware comparison
(token expiry, ``iat``/``exp`` JWT claims, ``last_status_update``).
"""

from datetime import UTC, datetime


def now_utc() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


def now_utc_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with ``+00:00`` offset."""
    return now_utc().isoformat()


def epoch_seconds() -> int:
    """Return the current UTC time as a POSIX/epoch integer (for JWT ``iat``/``exp``)."""
    return int(now_utc().timestamp())
