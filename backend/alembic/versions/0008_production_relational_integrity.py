"""Add explicit production relational foreign keys after immutable baselines.

The checklist originally reserved ``0006``; this repository already uses that
revision for key-operation audit, so the same migration is appended as 0008
without rewriting history.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_production_relational_integrity"
down_revision = "0007_corridor_admission"
branch_labels = None
depends_on = None

RELATIONS = (
    ("prod_payment_orders", "tenant_id", "prod_tenants", "tenant_id", False),
    ("prod_payment_orders", "initiator_participant", "prod_participants", "participant_id", False),
    ("prod_payment_facts", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_authorization_decisions", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_compliance_decisions", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_funding_reservations", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_fx_trade_intents", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_fx_trades", "trade_intent_id", "prod_fx_trade_intents", "trade_intent_id", False),
    ("prod_fx_trades", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_settlement_legs", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_beneficiary_credits", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_reconciliation_runs", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_cancellation_requests", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_investigation_cases", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_return_payments", "original_order_id", "prod_payment_orders", "order_id", False),
    ("prod_journals", "order_id", "prod_payment_orders", "order_id", True),
    ("prod_journal_entries", "journal_id", "prod_journals", "journal_id", False),
    ("prod_inbox_messages", "event_id", "prod_outbox_events", "event_id", False),
    ("prod_reconciliation_breaks", "order_id", "prod_payment_orders", "order_id", False),
    ("prod_report_receipts", "batch_id", "prod_report_batches", "batch_id", False),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _assert_no_orphans(table: str, column: str, parent: str, parent_column: str) -> None:
    bind = op.get_bind()
    orphan = bind.execute(sa.text(
        f"SELECT COUNT(*) FROM {table} child LEFT JOIN {parent} parent ON child.{column}=parent.{parent_column} "
        f"WHERE child.{column} IS NOT NULL AND parent.{parent_column} IS NULL"
    )).scalar_one()
    if orphan:
        raise RuntimeError(f"Cannot add FK {table}.{column}: {orphan} orphan rows")


def upgrade() -> None:
    tables = _tables()
    for table, column, parent, parent_column, _nullable in RELATIONS:
        if not {table, parent} <= tables:
            continue
        _assert_no_orphans(table, column, parent, parent_column)
        constraint = f"fk_{table}_{column}_{parent}"
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.create_foreign_key(constraint, parent, [column], [parent_column], ondelete="RESTRICT")


def downgrade() -> None:
    tables = _tables()
    for table, column, parent, _parent_column, _nullable in reversed(RELATIONS):
        if table not in tables:
            continue
        constraint = f"fk_{table}_{column}_{parent}"
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.drop_constraint(constraint, type_="foreignkey")
