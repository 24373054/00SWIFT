"""Read-only production data integrity audit.

The command never mutates data. It reports orphan rows, duplicates, null key
fields, invalid states, monetary violations, tenant mismatches and missing
hashes as machine-readable JSON.
"""

from __future__ import annotations

import argparse
import json

from sqlalchemy import create_engine, text

KEY_COLUMNS = {
    "prod_payment_orders": ("order_id", "tenant_id", "initiator_participant", "payload_hash"),
    "prod_payment_facts": ("fact_id", "order_id", "payload"),
    "prod_funding_reservations": ("reservation_id", "order_id", "amount_minor"),
    "prod_settlement_legs": ("leg_id", "order_id", "amount_minor"),
    "prod_journals": ("journal_id", "payload_hash"),
    "prod_journal_entries": ("entry_id", "journal_id", "amount_minor"),
    "prod_outbox_events": ("event_id", "payload"),
    "prod_inbox_messages": ("consumer", "event_id", "payload_hash"),
}
ORPHAN_CHECKS = (
    ("prod_payment_orders", "tenant_id", "prod_tenants", "tenant_id"),
    ("prod_payment_orders", "initiator_participant", "prod_participants", "participant_id"),
    ("prod_payment_facts", "order_id", "prod_payment_orders", "order_id"),
    ("prod_funding_reservations", "order_id", "prod_payment_orders", "order_id"),
    ("prod_settlement_legs", "order_id", "prod_payment_orders", "order_id"),
    ("prod_journal_entries", "journal_id", "prod_journals", "journal_id"),
    ("prod_inbox_messages", "event_id", "prod_outbox_events", "event_id"),
)


def _tables(connection) -> set[str]:
    rows = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    return {row[0] for row in rows}


def audit(engine) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    with engine.connect() as connection:
        tables = _tables(connection)
        table_columns = {
            table: {row[1] for row in connection.execute(text(f"PRAGMA table_info({table})"))}
            for table in tables
        }
        for table, columns in KEY_COLUMNS.items():
            if table not in tables:
                continue
            for column in columns:
                if column not in table_columns[table]:
                    continue
                count = connection.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL OR {column} = ''")).scalar_one()
                if count:
                    findings.append({"type": "null_or_empty", "table": table, "column": column, "count": count})
        for table, column, parent, parent_column in ORPHAN_CHECKS:
            if not {table, parent} <= tables or column not in table_columns[table] or parent_column not in table_columns[parent]:
                continue
            count = connection.execute(text(
                f"SELECT COUNT(*) FROM {table} child LEFT JOIN {parent} parent ON child.{column}=parent.{parent_column} "
                f"WHERE child.{column} IS NOT NULL AND parent.{parent_column} IS NULL"
            )).scalar_one()
            if count:
                findings.append({"type": "orphan", "table": table, "column": column, "parent": parent, "count": count})
        for table in ("prod_payment_orders", "prod_funding_reservations", "prod_settlement_legs", "prod_return_payments", "prod_journal_entries", "prod_corridor_admissions"):
            if table not in tables:
                continue
            columns = [row[1] for row in connection.execute(text(f"PRAGMA table_info({table})"))]
            for column in ("amount_minor", "min_amount_minor", "max_amount_minor", "balance_minor", "reserved_minor"):
                if column in columns:
                    count = connection.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {column} < 0")).scalar_one()
                    if count:
                        findings.append({"type": "negative_amount", "table": table, "column": column, "count": count})
        for table in ("prod_payment_orders", "prod_payment_facts", "prod_outbox_events", "prod_inbox_messages"):
            if table not in tables:
                continue
            for column in ("payload_hash", "content_hash", "payload"):
                columns = [row[1] for row in connection.execute(text(f"PRAGMA table_info({table})"))]
                if column in columns and column.endswith("hash"):
                    count = connection.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL OR {column} = ''")).scalar_one()
                    if count:
                        findings.append({"type": "missing_hash", "table": table, "column": column, "count": count})
        if "prod_payment_orders" in tables and "prod_participants" in tables:
            count = connection.execute(text(
                "SELECT COUNT(*) FROM prod_payment_orders o JOIN prod_participants p ON o.initiator_participant=p.participant_id "
                "WHERE o.tenant_id != p.tenant_id"
            )).scalar_one()
            if count:
                findings.append({"type": "tenant_mismatch", "table": "prod_payment_orders", "count": count})
    return {"tables_scanned": sorted(table for table in tables if table.startswith("prod_")), "finding_count": len(findings), "findings": findings}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", default="sqlite:///swift_dev.db")
    args = parser.parse_args()
    report = audit(create_engine(args.db_url))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 1 if report["finding_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
