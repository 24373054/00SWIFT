"""Persist HTTP request nonces for atomic replay rejection."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_production_replay_store"
down_revision = "0004_production_qualification"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("prod_request_nonces"):
        return
    op.create_table(
        "prod_request_nonces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trust_domain", sa.String(80), nullable=False),
        sa.Column("key_id", sa.String(160), nullable=False),
        sa.Column("nonce", sa.String(240), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("first_used_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("trust_domain", "key_id", "nonce", name="uq_prod_request_nonce_identity"),
    )
    op.create_index("ix_prod_request_nonces_trust_domain", "prod_request_nonces", ["trust_domain"])
    op.create_index("ix_prod_request_nonces_expires_at", "prod_request_nonces", ["expires_at"])


def downgrade() -> None:
    if _has_table("prod_request_nonces"):
        op.drop_table("prod_request_nonces")
