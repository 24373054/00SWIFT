"""Add scoped uniqueness for payment, approval, settlement and GL sequencing."""

from __future__ import annotations

from collections import defaultdict

import sqlalchemy as sa

from alembic import op

revision = "0012_production_business_uniques"
down_revision = "0011_production_state_constraints"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def _add_column(bind, table: str, column: sa.Column) -> None:
    if table in sa.inspect(bind).get_table_names() and column.name not in _columns(bind, table):
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.add_column(column)


def _backfill_sequences(bind) -> None:
    if "prod_return_payments" in sa.inspect(bind).get_table_names():
        rows = bind.execute(sa.text("SELECT id, original_order_id FROM prod_return_payments ORDER BY original_order_id, id")).fetchall()
        counters: defaultdict[str, int] = defaultdict(int)
        for row in rows:
            counters[row.original_order_id] += 1
            bind.execute(sa.text("UPDATE prod_return_payments SET return_sequence=:sequence WHERE id=:id"), {"sequence": counters[row.original_order_id], "id": row.id})
    if "prod_outbox_events" in sa.inspect(bind).get_table_names():
        rows = bind.execute(sa.text("SELECT id, topic, aggregate_id FROM prod_outbox_events ORDER BY topic, aggregate_id, id")).fetchall()
        counters: defaultdict[tuple[str, str], int] = defaultdict(int)
        for row in rows:
            key = (row.topic, row.aggregate_id)
            counters[key] += 1
            bind.execute(sa.text("UPDATE prod_outbox_events SET aggregate_sequence=:sequence WHERE id=:id"), {"sequence": counters[key], "id": row.id})
    if "prod_journals" in sa.inspect(bind).get_table_names():
        bind.execute(sa.text("UPDATE prod_journals SET gl_batch_reference = journal_id WHERE gl_batch_reference IS NULL OR gl_batch_reference = ''"))


def upgrade() -> None:
    bind = op.get_bind()
    _add_column(bind, "prod_return_payments", sa.Column("return_sequence", sa.Integer(), nullable=True))
    _add_column(bind, "prod_outbox_events", sa.Column("aggregate_sequence", sa.Integer(), nullable=True))
    _add_column(bind, "prod_journals", sa.Column("gl_batch_reference", sa.String(160), nullable=True))
    _backfill_sequences(bind)

    unique_specs = (
        ("prod_payment_orders", "uq_prod_instruction_participant", ("initiator_participant", "instruction_id")),
        ("prod_approvals", "uq_prod_approval_decision", ("aggregate_type", "aggregate_id", "action")),
        ("prod_fx_trade_intents", "uq_prod_quote_accept", ("quote_id",)),
        ("prod_return_payments", "uq_prod_return_sequence", ("original_order_id", "return_sequence")),
        ("prod_outbox_events", "uq_prod_event_aggregate_sequence", ("topic", "aggregate_id", "aggregate_sequence")),
        ("prod_journals", "uq_prod_gl_batch_reference", ("legal_entity", "book", "business_date", "gl_batch_reference")),
    )
    for table, name, columns in unique_specs:
        if table not in sa.inspect(bind).get_table_names():
            continue
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.create_unique_constraint(name, list(columns))

    for table, column in (("prod_return_payments", "return_sequence"), ("prod_outbox_events", "aggregate_sequence"), ("prod_journals", "gl_batch_reference")):
        if table in sa.inspect(bind).get_table_names():
            with op.batch_alter_table(table, recreate="always") as batch:
                batch.alter_column(column, existing_type=sa.Integer() if column.endswith("sequence") else sa.String(160), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    for table, name in (
        ("prod_journals", "uq_prod_gl_batch_reference"),
        ("prod_outbox_events", "uq_prod_event_aggregate_sequence"),
        ("prod_return_payments", "uq_prod_return_sequence"),
        ("prod_fx_trade_intents", "uq_prod_quote_accept"),
        ("prod_approvals", "uq_prod_approval_decision"),
        ("prod_payment_orders", "uq_prod_instruction_participant"),
    ):
        if table in sa.inspect(bind).get_table_names():
            with op.batch_alter_table(table, recreate="always") as batch:
                batch.drop_constraint(name, type_="unique")
