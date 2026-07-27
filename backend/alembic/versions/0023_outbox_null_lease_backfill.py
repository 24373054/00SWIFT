"""Release legacy PROCESSING outbox events with null leases."""

import sqlalchemy as sa

from alembic import op

revision = "0023_outbox_null_lease_backfill"
down_revision = "0022_idempotency_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("UPDATE prod_outbox_events SET status='PENDING', lease_owner=NULL, lease_until=NULL WHERE status='PROCESSING' AND lease_until IS NULL")
    )


def downgrade() -> None:
    pass
