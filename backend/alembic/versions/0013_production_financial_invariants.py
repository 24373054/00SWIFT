"""Enforce amount, balance, validity-window and dual-control invariants."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0013_production_financial_invariants"
down_revision = "0012_production_business_uniques"
branch_labels = None
depends_on = None

CHECKS = {
    "prod_funding_reservations": (("amount_minor", "amount_minor > 0"),),
    "prod_fx_quotes": (("base_amount_minor", "base_amount_minor > 0"), ("quote_amount_minor", "quote_amount_minor > 0"), ("fee_minor", "fee_minor >= 0"), ("expires_at", "expires_at > created_at")),
    "prod_settlement_legs": (("amount_minor", "amount_minor > 0"),),
    "prod_return_payments": (("amount_minor", "amount_minor > 0"),),
    "prod_ledger_accounts": (("reserved_minor", "reserved_minor >= 0"), ("reserved_minor_balance", "reserved_minor <= balance_minor")),
    "prod_limit_profiles": (("max_amount_minor", "max_amount_minor IS NULL OR max_amount_minor >= 0"), ("daily_amount_minor", "daily_amount_minor IS NULL OR daily_amount_minor >= 0"), ("max_exposure_minor", "max_exposure_minor IS NULL OR max_exposure_minor >= 0"), ("effective_window", "effective_to IS NULL OR effective_to > effective_from")),
    "prod_mandates": (("max_amount_minor", "max_amount_minor > 0"), ("validity_window", "valid_to IS NULL OR valid_to > valid_from")),
    "prod_entitlements": (("effective_window", "effective_to IS NULL OR effective_to > effective_from"),),
    "prod_qualification_artifacts": (("validity_window", "valid_to > valid_from"),),
    "prod_authorization_decisions": (("validity_window", "valid_to IS NULL OR valid_to > valid_from"),),
    "prod_corridor_admissions": (("validity_window", "valid_to > valid_from"),),
    "prod_control_attestations": (("validity_window", "valid_to > valid_from"),),
    "prod_approvals": (("maker_checker", "checker IS NULL OR maker <> checker"),),
}
SQL_KEYWORDS = {"IS", "NULL", "OR", "AND", "NOT"}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table, checks in CHECKS.items():
        if table not in tables:
            continue
        columns = {column["name"] for column in inspector.get_columns(table)}
        for suffix, expression in checks:
            referenced = {token for token in expression.replace("(", " ").replace(")", " ").replace(">", " ").replace("<", " ").replace("=", " ").split() if token.isidentifier() and token.upper() not in SQL_KEYWORDS}
            if not referenced.issubset(columns):
                continue
            invalid = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE NOT ({expression})")).scalar_one()
            if invalid:
                raise RuntimeError(f"Cannot constrain {table}: {invalid} rows violate {expression}")
            with op.batch_alter_table(table, recreate="always") as batch:
                batch.create_check_constraint(f"ck_{table}_{suffix}_v1", expression)


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table, checks in reversed(tuple(CHECKS.items())):
        if table not in tables:
            continue
        with op.batch_alter_table(table, recreate="always") as batch:
            for suffix, _expression in reversed(checks):
                batch.drop_constraint(f"ck_{table}_{suffix}_v1", type_="check")
