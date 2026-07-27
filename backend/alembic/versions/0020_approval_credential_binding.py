"""Persist maker/checker credential bindings for maker-checker SoD."""

import sqlalchemy as sa

from alembic import op

revision = "0020_approval_credential_binding"
down_revision = "0019_approval_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prod_approvals", sa.Column("maker_credential_id", sa.Integer(), nullable=True))
    op.add_column("prod_approvals", sa.Column("checker_credential_id", sa.Integer(), nullable=True))
    op.add_column("prod_approval_decisions", sa.Column("checker_credential_id", sa.Integer(), nullable=True))
    op.create_index("ix_prod_approvals_maker_credential_id", "prod_approvals", ["maker_credential_id"])
    op.create_index("ix_prod_approvals_checker_credential_id", "prod_approvals", ["checker_credential_id"])
    op.create_index("ix_prod_approval_decisions_checker_credential_id", "prod_approval_decisions", ["checker_credential_id"])


def downgrade() -> None:
    op.drop_index("ix_prod_approval_decisions_checker_credential_id", table_name="prod_approval_decisions")
    op.drop_index("ix_prod_approvals_checker_credential_id", table_name="prod_approvals")
    op.drop_index("ix_prod_approvals_maker_credential_id", table_name="prod_approvals")
    op.drop_column("prod_approval_decisions", "checker_credential_id")
    op.drop_column("prod_approvals", "checker_credential_id")
    op.drop_column("prod_approvals", "maker_credential_id")
