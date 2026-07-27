"""Split payment orchestration into independently auditable state dimensions."""

import sqlalchemy as sa

from alembic import op

revision = "0025_payment_state_dimensions"
down_revision = "0024_dlq_replay_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {item["name"] for item in inspector.get_columns("prod_payment_orders")}
    for name, default in (("authorization_state", "PENDING"), ("compliance_state", "PENDING"), ("funding_state", "PENDING"), ("fx_state", "NOT_REQUIRED"), ("message_delivery_state", "PENDING"), ("value_settlement_state", "PENDING"), ("beneficiary_state", "PENDING"), ("reconciliation_state", "PENDING")):
        if name not in existing:
            op.add_column("prod_payment_orders", sa.Column(name, sa.String(40), nullable=False, server_default=default))


def downgrade() -> None:
    for name in ("reconciliation_state", "beneficiary_state", "value_settlement_state", "message_delivery_state", "fx_state", "funding_state", "compliance_state", "authorization_state"):
        op.drop_column("prod_payment_orders", name)
