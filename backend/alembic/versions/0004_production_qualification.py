"""Persist verified production qualification decisions."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_production_qualification"
down_revision = "0003_production_hardening"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("prod_qualification_artifacts"):
        op.create_table(
            "prod_qualification_artifacts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("artifact_id", sa.String(100), nullable=False),
            sa.Column("artifact_type", sa.String(80), nullable=False),
            sa.Column("environment", sa.String(20), nullable=False),
            sa.Column("subject", sa.String(160), nullable=False),
            sa.Column("issuer", sa.String(200), nullable=False),
            sa.Column("connector", sa.String(120), nullable=False),
            sa.Column("connector_version", sa.String(80), nullable=False),
            sa.Column("artifact_path", sa.String(500), nullable=False),
            sa.Column("artifact_digest", sa.String(64), nullable=False),
            sa.Column("signature_algorithm", sa.String(40), nullable=False),
            sa.Column("valid_from", sa.DateTime(), nullable=False),
            sa.Column("valid_to", sa.DateTime(), nullable=False),
            sa.Column("document_digest", sa.String(64), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="VERIFIED"),
            sa.Column("verified_at", sa.DateTime(), nullable=False),
            sa.Column("verifier_version", sa.String(40), nullable=False, server_default="qualification-v1"),
            sa.UniqueConstraint("artifact_id", name="uq_prod_qualification_artifact_id"),
            sa.UniqueConstraint(
                "environment", "subject", "connector_version",
                name="uq_prod_qualification_environment_subject_version",
            ),
            sa.CheckConstraint(
                "status IN ('VERIFIED', 'ACTIVE', 'EXPIRED', 'REJECTED')",
                name="ck_prod_qualification_artifact_status",
            ),
        )
        op.create_index("ix_prod_qualification_artifacts_artifact_id", "prod_qualification_artifacts", ["artifact_id"], unique=True)
        op.create_index("ix_prod_qualification_artifacts_environment", "prod_qualification_artifacts", ["environment"])
    if not _has_table("prod_qualification_decisions"):
        op.create_table(
            "prod_qualification_decisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("decision_id", sa.String(100), nullable=False),
            sa.Column("artifact_id", sa.String(100), nullable=False),
            sa.Column("environment", sa.String(20), nullable=False),
            sa.Column("outcome", sa.String(20), nullable=False),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("input_digest", sa.String(64), nullable=False),
            sa.Column("verifier_version", sa.String(40), nullable=False),
            sa.Column("decided_at", sa.DateTime(), nullable=False),
            sa.Column("evidence_ref", sa.String(120), nullable=True),
            sa.UniqueConstraint("decision_id", name="uq_prod_qualification_decision_id"),
        )
        op.create_index("ix_prod_qualification_decisions_decision_id", "prod_qualification_decisions", ["decision_id"], unique=True)
        op.create_index("ix_prod_qualification_decisions_artifact_id", "prod_qualification_decisions", ["artifact_id"])


def downgrade() -> None:
    if _has_table("prod_qualification_decisions"):
        op.drop_table("prod_qualification_decisions")
    if _has_table("prod_qualification_artifacts"):
        op.drop_table("prod_qualification_artifacts")
