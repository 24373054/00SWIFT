"""Persist corridor admission and control attestations."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_corridor_admission"
down_revision = "0006_key_operation_audit"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("prod_corridor_admissions"):
        op.create_table(
            "prod_corridor_admissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("admission_id", sa.String(100), nullable=False),
            sa.Column("environment", sa.String(20), nullable=False),
            sa.Column("corridor", sa.String(40), nullable=False),
            sa.Column("applicable_subjects", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("scenarios", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("currencies", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("min_amount_minor", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("max_amount_minor", sa.Integer(), nullable=False),
            sa.Column("valid_from", sa.DateTime(), nullable=False),
            sa.Column("valid_to", sa.DateTime(), nullable=False),
            sa.Column("funding_flow_version", sa.String(80), nullable=False),
            sa.Column("finality_definition", sa.String(240), nullable=False),
            sa.Column("data_flow_version", sa.String(80), nullable=False),
            sa.Column("rulebook_version", sa.String(80), nullable=False),
            sa.Column("signed_roles", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("simulation_only", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("evidence_ref", sa.String(120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("admission_id", name="uq_prod_corridor_admission_id"),
            sa.UniqueConstraint("environment", "corridor", "rulebook_version", name="uq_prod_corridor_environment_version"),
            sa.CheckConstraint("min_amount_minor > 0 AND max_amount_minor >= min_amount_minor", name="ck_prod_corridor_amount_window"),
            sa.CheckConstraint("status IN ('PENDING', 'ACTIVE', 'EXPIRED', 'REVOKED')", name="ck_prod_corridor_status"),
        )
        op.create_index("ix_prod_corridor_admissions_environment", "prod_corridor_admissions", ["environment"])
        op.create_index("ix_prod_corridor_admissions_corridor", "prod_corridor_admissions", ["corridor"])
    if not _has_table("prod_control_attestations"):
        op.create_table(
            "prod_control_attestations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("attestation_id", sa.String(100), nullable=False),
            sa.Column("admission_id", sa.String(100), nullable=False),
            sa.Column("signer_role", sa.String(100), nullable=False),
            sa.Column("signer_subject", sa.String(160), nullable=False),
            sa.Column("statement_digest", sa.String(64), nullable=False),
            sa.Column("valid_from", sa.DateTime(), nullable=False),
            sa.Column("valid_to", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("evidence_ref", sa.String(120), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("attestation_id", name="uq_prod_control_attestation_id"),
        )
        op.create_index("ix_prod_control_attestations_admission_id", "prod_control_attestations", ["admission_id"])


def downgrade() -> None:
    if _has_table("prod_control_attestations"):
        op.drop_table("prod_control_attestations")
    if _has_table("prod_corridor_admissions"):
        op.drop_table("prod_corridor_admissions")
