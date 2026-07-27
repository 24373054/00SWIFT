"""B5 versioned fee/tax/interest/adjustment journal templates."""

import sqlalchemy as sa

from alembic import op

revision = "0033_journal_templates"
down_revision = "0032_journal_reversal_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("prod_journal_templates", sa.Column("id", sa.Integer, primary_key=True), sa.Column("template_id", sa.String(100), nullable=False, unique=True), sa.Column("tenant_id", sa.String(80), nullable=False, index=True), sa.Column("template_type", sa.String(30), nullable=False), sa.Column("version", sa.String(80), nullable=False), sa.Column("mapping_json", sa.Text, nullable=False), sa.Column("liability_profile_id", sa.String(100)), sa.Column("evidence_ref", sa.String(120)), sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_table("prod_journal_templates")
