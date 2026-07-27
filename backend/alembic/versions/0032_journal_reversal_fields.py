"""B5 journal reversal linkage and evidence fields."""

import sqlalchemy as sa
from alembic import op

revision = "0032_journal_reversal_fields"
down_revision = "0031_ledger_accounting_boundary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prod_journals", sa.Column("reverses_journal_id", sa.String(80), nullable=True))
    op.add_column("prod_journals", sa.Column("reversal_reason", sa.String(240), nullable=True))
    op.add_column("prod_journals", sa.Column("approval_ref", sa.String(120), nullable=True))
    op.add_column("prod_journals", sa.Column("evidence_ref", sa.String(120), nullable=True))


def downgrade() -> None:
    for column in ("evidence_ref", "approval_ref", "reversal_reason", "reverses_journal_id"):
        op.drop_column("prod_journals", column)
