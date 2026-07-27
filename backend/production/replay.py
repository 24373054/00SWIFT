"""Atomic persistence boundary for HTTP nonce replay protection."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.exc import IntegrityError

from .models import ProductionRequestNonce, utcnow


class NonceReplayError(ValueError):
    """Raised when a nonce is expired, reused, or has a different digest."""


class NonceReplayStore:
    def __init__(self, db):
        self.db = db

    def consume(
        self,
        *,
        trust_domain: str,
        key_id: str,
        nonce: str,
        request_digest: str,
        expires_at: dt.datetime,
        now: dt.datetime | None = None,
    ) -> ProductionRequestNonce:
        current = (now or utcnow()).astimezone(dt.UTC)
        expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=dt.UTC)
        if expiry.astimezone(dt.UTC) <= current:
            raise NonceReplayError("nonce is expired")
        record = ProductionRequestNonce(
            trust_domain=trust_domain,
            key_id=key_id,
            nonce=nonce,
            request_digest=request_digest,
            expires_at=expiry,
            first_used_at=current,
        )
        try:
            with self.db.begin_nested():
                self.db.add(record)
                self.db.flush()
        except IntegrityError as exc:
            existing = (
                self.db.query(ProductionRequestNonce)
                .filter_by(trust_domain=trust_domain, key_id=key_id, nonce=nonce)
                .one_or_none()
            )
            if existing and existing.request_digest != request_digest:
                raise NonceReplayError("nonce was reused with a different request digest") from exc
            raise NonceReplayError("nonce replay detected") from exc
        return record
