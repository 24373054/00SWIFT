"""Add signer and effective-window fields to rulebook acceptance."""

import sqlalchemy as sa

from alembic import op

revision = "0015_rulebook_acceptance_window"
down_revision = "0014_production_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "prod_rulebook_acceptances" not in sa.inspect(bind).get_table_names():
        return
    columns = {item["name"] for item in sa.inspect(bind).get_columns("prod_rulebook_acceptances")}
    with op.batch_alter_table("prod_rulebook_acceptances", recreate="always") as batch:
        if "signer_subject" not in columns:
            batch.add_column(sa.Column("signer_subject", sa.String(200), nullable=True))
        if "effective_from" not in columns:
            batch.add_column(sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True))
        if "effective_to" not in columns:
            batch.add_column(sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True))
    bind.execute(sa.text("UPDATE prod_rulebook_acceptances SET signer_subject = COALESCE(signer_subject, accepted_by), effective_from = COALESCE(effective_from, accepted_at)"))
    with op.batch_alter_table("prod_rulebook_acceptances", recreate="always") as batch:
        batch.alter_column("signer_subject", existing_type=sa.String(200), nullable=False)
        batch.alter_column("effective_from", existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    if "prod_rulebook_acceptances" not in sa.inspect(op.get_bind()).get_table_names():
        return
    with op.batch_alter_table("prod_rulebook_acceptances", recreate="always") as batch:
        batch.drop_column("effective_to")
        batch.drop_column("effective_from")
        batch.drop_column("signer_subject")
