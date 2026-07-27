"""Tenant context propagation for PostgreSQL transactions and workers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DatabaseContext:
    tenant_id: str
    participant_id: str
    service_identity: str

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.participant_id.strip(), self.service_identity.strip())):
            raise ValueError("tenant_id, participant_id and service_identity are required")


def context_from_event_envelope(envelope: dict[str, object]) -> DatabaseContext:
    """Recover identity from an event; never fall back to a global admin."""
    context = envelope.get("context")
    if not isinstance(context, dict):
        raise ValueError("event envelope context is required")
    return DatabaseContext(
        tenant_id=str(context.get("tenant_id", "")),
        participant_id=str(context.get("participant_id", "")),
        service_identity=str(context.get("service_identity", "")),
    )


def set_local_context(connection, context: DatabaseContext) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT set_config('app.tenant_id', :value, true)"), {"value": context.tenant_id})
        connection.execute(text("SELECT set_config('app.participant_id', :value, true)"), {"value": context.participant_id})
        connection.execute(text("SELECT set_config('app.service_identity', :value, true)"), {"value": context.service_identity})
    else:
        connection.info["production_db_context"] = context


def clear_local_context(connection) -> None:
    connection.info.pop("production_db_context", None)
    if connection.dialect.name == "postgresql":
        connection.execute(text("SELECT set_config('app.tenant_id', '', true)"))
        connection.execute(text("SELECT set_config('app.participant_id', '', true)"))
        connection.execute(text("SELECT set_config('app.service_identity', '', true)"))


@contextmanager
def tenant_transaction(session: Session, context: DatabaseContext) -> Iterator[Session]:
    connection = session.connection()
    set_local_context(connection, context)
    try:
        yield session
    finally:
        clear_local_context(connection)
