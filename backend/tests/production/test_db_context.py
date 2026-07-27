import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from production.db_context import (
    DatabaseContext,
    clear_local_context,
    context_from_event_envelope,
    set_local_context,
    tenant_transaction,
)


def test_sqlite_context_is_set_and_cleared_on_connection():
    engine = create_engine("sqlite://")
    context = DatabaseContext("tenant-a", "participant-a", "worker-a")
    with engine.begin() as connection:
        set_local_context(connection, context)
        assert connection.info["production_db_context"] == context
        clear_local_context(connection)
        assert "production_db_context" not in connection.info


def test_worker_context_requires_event_envelope_identity():
    context = context_from_event_envelope({"context": {"tenant_id": "t", "participant_id": "p", "service_identity": "s"}})
    assert context.tenant_id == "t"
    with pytest.raises(ValueError, match="context"):
        context_from_event_envelope({})


def test_tenant_transaction_clears_connection_context():
    engine = create_engine("sqlite://")
    with Session(engine) as session:
        with tenant_transaction(session, DatabaseContext("t", "p", "s")):
            assert session.connection().info["production_db_context"].tenant_id == "t"
        assert "production_db_context" not in session.connection().info
