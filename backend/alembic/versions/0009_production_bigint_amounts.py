"""Widen production monetary columns after overflow/negative-value audit."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009_production_bigint_amounts"
down_revision = "0008_production_relational_integrity"
branch_labels = None
depends_on = None

COLUMNS = (
    ("prod_limit_profiles", "max_amount_minor"), ("prod_limit_profiles", "daily_amount_minor"), ("prod_limit_profiles", "max_exposure_minor"),
    ("prod_payment_orders", "amount_minor"),
    ("prod_funding_reservations", "amount_minor"), ("prod_fx_quotes", "base_amount_minor"),
    ("prod_fx_quotes", "quote_amount_minor"), ("prod_fx_quotes", "fee_minor"),
    ("prod_settlement_legs", "amount_minor"), ("prod_return_payments", "amount_minor"),
    ("prod_ledger_accounts", "balance_minor"), ("prod_ledger_accounts", "reserved_minor"),
    ("prod_journal_entries", "amount_minor"), ("prod_corridor_admissions", "min_amount_minor"),
    ("prod_corridor_admissions", "max_amount_minor"),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables()
    for table, column in COLUMNS:
        if table not in tables:
            continue
        invalid = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE {column} < 0 OR {column} > :max"), {"max": 9223372036854775807}).scalar_one()
        if invalid:
            raise RuntimeError(f"Cannot widen {table}.{column}: {invalid} negative/overflow values")
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.alter_column(column, type_=sa.BigInteger())


def downgrade() -> None:
    tables = _tables()
    for table, column in reversed(COLUMNS):
        if table not in tables:
            continue
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.alter_column(column, type_=sa.Integer())
