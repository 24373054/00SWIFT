"""Create append-only approval decision evidence."""

import sqlalchemy as sa

from alembic import op

revision = "0019_approval_decisions"
down_revision = "0018_payment_limit_reservation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prod_approval_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("decision_id", sa.String(100), nullable=False),
        sa.Column("approval_id", sa.String(100), sa.ForeignKey("prod_approvals.approval_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("checker", sa.String(200), nullable=False),
        sa.Column("signature", sa.String(512), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("evidence_ref", sa.String(120), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("decision_id", name="uq_prod_approval_decision_id"),
    )


def downgrade() -> None:
    op.drop_table("prod_approval_decisions")
