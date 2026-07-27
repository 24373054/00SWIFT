"""Persist dual-control key operation audit facts."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_key_operation_audit"
down_revision = "0005_production_replay_store"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("prod_key_operation_audits"):
        return
    op.create_table(
        "prod_key_operation_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation_id", sa.String(100), nullable=False),
        sa.Column("operation", sa.String(30), nullable=False),
        sa.Column("key_id", sa.String(160), nullable=False),
        sa.Column("trust_domain", sa.String(80), nullable=False),
        sa.Column("maker", sa.String(160), nullable=False),
        sa.Column("checker", sa.String(160), nullable=False),
        sa.Column("approval_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result_digest", sa.String(64), nullable=True),
        sa.Column("evidence_ref", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("operation_id", name="uq_prod_key_operation_id"),
    )
    op.create_index("ix_prod_key_operation_audits_key_id", "prod_key_operation_audits", ["key_id"])
    op.create_index("ix_prod_key_operation_audits_approval_id", "prod_key_operation_audits", ["approval_id"])


def downgrade() -> None:
    if _has_table("prod_key_operation_audits"):
        op.drop_table("prod_key_operation_audits")
