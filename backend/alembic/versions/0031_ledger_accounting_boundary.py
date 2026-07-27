"""B5 accounting boundary models and explicit migration."""

import sqlalchemy as sa

from alembic import op

revision = "0031_ledger_accounting_boundary"
down_revision = "0030_payment_timers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    def common():
        return [sa.Column("id", sa.Integer, primary_key=True), sa.Column("tenant_id", sa.String(80), nullable=False, index=True), sa.Column("evidence_ref", sa.String(120))]
    op.create_table("prod_legal_entities", *common(), sa.Column("entity_id", sa.String(100), nullable=False, unique=True), sa.Column("legal_name", sa.String(200), nullable=False), sa.Column("jurisdiction", sa.String(12), nullable=False), sa.Column("version", sa.Integer, nullable=False, server_default="1"), sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()))
    op.create_table("prod_ledger_books", *common(), sa.Column("book_id", sa.String(100), nullable=False, unique=True), sa.Column("legal_entity_id", sa.String(100), nullable=False), sa.Column("book_type", sa.String(40), nullable=False), sa.Column("business_date", sa.String(10), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("version", sa.Integer, nullable=False, server_default="1"), sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()))
    op.create_table("prod_holds", *common(), sa.Column("hold_id", sa.String(100), nullable=False, unique=True), sa.Column("legal_entity_id", sa.String(100), nullable=False), sa.Column("book_id", sa.String(100), nullable=False), sa.Column("account_id", sa.String(100), nullable=False), sa.Column("payment_id", sa.String(80)), sa.Column("purpose", sa.String(80), nullable=False), sa.Column("amount_minor", sa.BigInteger, nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("state", sa.String(20), nullable=False), sa.Column("expires_at", sa.DateTime), sa.Column("external_reference", sa.String(160)), sa.Column("version", sa.Integer, nullable=False, server_default="1"), sa.CheckConstraint("amount_minor > 0", name="ck_prod_hold_amount"))
    op.create_table("prod_ledger_periods", *common(), sa.Column("period_id", sa.String(100), nullable=False, unique=True), sa.Column("book_id", sa.String(100), nullable=False), sa.Column("period_start", sa.String(10), nullable=False), sa.Column("period_end", sa.String(10), nullable=False), sa.Column("state", sa.String(20), nullable=False), sa.Column("version", sa.Integer, nullable=False, server_default="1"))
    op.create_table("prod_balance_snapshots", *common(), sa.Column("snapshot_id", sa.String(100), nullable=False, unique=True), sa.Column("book_id", sa.String(100), nullable=False), sa.Column("account_id", sa.String(100), nullable=False), sa.Column("business_date", sa.String(10), nullable=False), sa.Column("balance_minor", sa.BigInteger, nullable=False), sa.Column("source_max_entry_sequence", sa.Integer, nullable=False, server_default="0"), sa.Column("source_hash", sa.String(64), nullable=False))
    op.create_table("prod_fee_tax", *common(), sa.Column("charge_id", sa.String(100), nullable=False, unique=True), sa.Column("payment_id", sa.String(80), nullable=False), sa.Column("charge_type", sa.String(20), nullable=False), sa.Column("amount_minor", sa.BigInteger, nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("rule_version", sa.String(80), nullable=False))
    op.create_table("prod_fx_revaluations", *common(), sa.Column("revaluation_id", sa.String(100), nullable=False, unique=True), sa.Column("payment_id", sa.String(80)), sa.Column("currency", sa.String(3), nullable=False), sa.Column("amount_minor", sa.BigInteger, nullable=False), sa.Column("rate", sa.String(80), nullable=False), sa.Column("rule_version", sa.String(80), nullable=False))
    op.create_table("prod_gl_mappings", *common(), sa.Column("mapping_id", sa.String(100), nullable=False, unique=True), sa.Column("version", sa.String(80), nullable=False), sa.Column("source_account_type", sa.String(50), nullable=False), sa.Column("target_account", sa.String(100), nullable=False), sa.Column("effective_from", sa.DateTime, nullable=False), sa.Column("effective_to", sa.DateTime))
    op.create_table("prod_gl_batches", *common(), sa.Column("batch_id", sa.String(100), nullable=False, unique=True), sa.Column("mapping_version", sa.String(80), nullable=False), sa.Column("journal_scope", sa.Text, nullable=False), sa.Column("debit_total_minor", sa.BigInteger, nullable=False, server_default="0"), sa.Column("credit_total_minor", sa.BigInteger, nullable=False, server_default="0"), sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("state", sa.String(20), nullable=False), sa.Column("receipt_hash", sa.String(64)))
    op.create_table("prod_gl_receipts", *common(), sa.Column("receipt_id", sa.String(100), nullable=False, unique=True), sa.Column("batch_id", sa.String(100), nullable=False), sa.Column("state", sa.String(20), nullable=False), sa.Column("receipt_hash", sa.String(64), nullable=False), sa.Column("received_at", sa.DateTime, nullable=False))


def downgrade() -> None:
    for table in ("prod_gl_receipts", "prod_gl_batches", "prod_gl_mappings", "prod_fx_revaluations", "prod_fee_tax", "prod_balance_snapshots", "prod_ledger_periods", "prod_holds", "prod_ledger_books", "prod_legal_entities"):
        op.drop_table(table)
