"""Link report batches to an originating payment when applicable."""

import sqlalchemy as sa

from alembic import op

revision = "0029_payment_graph_report_link"
down_revision = "0028_payment_reference_scoping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "order_id" not in {item["name"] for item in sa.inspect(op.get_bind()).get_columns("prod_report_batches")}:
        op.add_column("prod_report_batches", sa.Column("order_id", sa.String(80), nullable=True))


def downgrade() -> None:
    op.drop_column("prod_report_batches", "order_id")
