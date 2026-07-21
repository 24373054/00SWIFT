"""Messaging service: FIN send, distributions, ack/nak.

Mock tier writes ``FinMessage`` + ``MessageDistribution`` rows. On send, it
also synthesizes an inbound ``Distribution`` so ``GET /distributions`` lists it
(matching the real Alliance Cloud inbox model).
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from core.errors import resource_not_found
from core.time import now_utc
from database import FinMessage, MessageDistribution


def send_fin_message(db: Session, body: dict) -> dict:
    """Persist a FIN message + synthesize a distribution. Returns the cloud ref."""
    distribution_id = str(uuid.uuid4())
    message_cloud_reference = str(uuid.uuid4())
    network_info = body.get("network_info") or {}

    msg = FinMessage(
        sender_reference=body["sender_reference"],
        message_type=body["message_type"],
        sender=body["sender"],
        receiver=body["receiver"],
        payload=body["payload"],
        uetr=network_info.get("uetr"),
        network_priority=network_info.get("network_priority", "Normal"),
        network_info=json.dumps(network_info),
        distribution_id=distribution_id,
        created_at=now_utc(),
    )
    db.add(msg)

    dist = MessageDistribution(
        distribution_id=distribution_id,
        service="fin",
        message_type=body["message_type"],
        sender=body["sender"],
        receiver=body["receiver"],
        message_cloud_reference=message_cloud_reference,
        status="available",
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(dist)
    db.commit()
    return {"message_cloud_reference": message_cloud_reference, "distribution_id": distribution_id}


def list_distributions(db: Session, limit: int = 50) -> list[dict]:
    rows = (
        db.query(MessageDistribution)
        .order_by(MessageDistribution.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "distribution_id": r.distribution_id,
            "service": r.service,
            "message_type": r.message_type,
            "sender": r.sender,
            "receiver": r.receiver,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


def ack_distribution(db: Session, distribution_id: str) -> None:
    r = (
        db.query(MessageDistribution)
        .filter(MessageDistribution.distribution_id == distribution_id)
        .first()
    )
    if not r:
        raise resource_not_found(f"Distribution {distribution_id} not found")
    r.status = "acked"
    r.updated_at = now_utc()
    db.commit()


def nak_distribution(db: Session, distribution_id: str, reason: str | None) -> None:
    r = (
        db.query(MessageDistribution)
        .filter(MessageDistribution.distribution_id == distribution_id)
        .first()
    )
    if not r:
        raise resource_not_found(f"Distribution {distribution_id} not found")
    r.status = "naked"
    r.nak_reason = reason
    r.updated_at = now_utc()
    db.commit()
