from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]


def _alembic(url: str, *arguments: str) -> None:
    environment = {**os.environ, "DB_URL": url, "PYTHONPATH": str(ROOT / "backend")}
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_legacy_runtime_states_upgrade_and_v2_constraints_reject_unknown(tmp_path):
    database_path = tmp_path / "state-constraints.db"
    url = f"sqlite:///{database_path}"
    _alembic(url, "upgrade", "0010_production_utc_timestamps")

    now = "2026-07-28 00:00:00"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO prod_tenants
                (tenant_id, name, jurisdiction, data_region, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("tenant:STATE-TEST", "State Test", "CN", "CN", "ACTIVE", now, now),
        )
        connection.execute(
            """
            INSERT INTO prod_participants
                (participant_id, tenant_id, name, participant_type, jurisdiction, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("STATE-TEST", "tenant:STATE-TEST", "State Test", "BANK", "CN", "ACTIVE", now, now),
        )
        connection.execute(
            """
            INSERT INTO prod_payment_orders
                (order_id, uetr, instruction_id, tenant_id, initiator_participant, corridor,
                 debtor_party_ref, debtor_account_ref, creditor_party_ref, creditor_account_ref,
                 amount_minor, currency, settlement_currency, purpose_code, payload, payload_hash,
                 orchestration_state, completion_profile_id, projection_rule_version, version,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "state-order",
                "123e4567-e89b-42d3-a456-426614174000",
                "state-instruction",
                "tenant:STATE-TEST",
                "STATE-TEST",
                "CN-HK",
                "debtor",
                "debtor-account",
                "creditor",
                "creditor-account",
                100,
                "CNY",
                "CNY",
                "TRADE",
                "{}",
                "0" * 64,
                "CONTROL_CHECKS",
                "sandbox-completion-v1",
                "projection-v1",
                1,
                now,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO prod_payment_orders
                (order_id, uetr, instruction_id, tenant_id, initiator_participant, corridor,
                 debtor_party_ref, debtor_account_ref, creditor_party_ref, creditor_account_ref,
                 amount_minor, currency, settlement_currency, purpose_code, payload, payload_hash,
                 orchestration_state, completion_profile_id, projection_rule_version, version,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "state-order-duplicate",
                "223e4567-e89b-42d3-a456-426614174000",
                "state-instruction",
                "tenant:STATE-TEST",
                "STATE-TEST",
                "CN-HK",
                "debtor",
                "debtor-account",
                "creditor",
                "creditor-account",
                100,
                "CNY",
                "CNY",
                "TRADE",
                "{}",
                "0" * 64,
                "CONTROL_CHECKS",
                "sandbox-completion-v1",
                "projection-v1",
                1,
                now,
                now,
            ),
        )
        for sequence, (fact_type, state) in enumerate(
            (
                ("AUTHORIZATION", "PASSED"),
                ("FUNDING", "RESERVED"),
                ("SETTLEMENT", "FINAL"),
                ("MESSAGE", "DELIVERED"),
                ("RECONCILIATION", "MATCHED"),
            ),
            start=1,
        ):
            connection.execute(
                """
                INSERT INTO prod_payment_facts
                    (fact_id, order_id, fact_type, state, reference, payload, occurred_at, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"fact-{sequence}",
                    "state-order",
                    fact_type,
                    state,
                    f"reference-{sequence}",
                    "{}",
                    now,
                    1,
                ),
            )
        connection.execute(
            """
            INSERT INTO prod_outbox_events
                (event_id, topic, aggregate_id, payload, status, attempts, available_at,
                 created_at, schema_version, partition_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "state-event",
                "state.test",
                "state-order",
                "{}",
                "PUBLISHED",
                1,
                now,
                now,
                "1.0",
                "state-order",
            ),
        )
        connection.execute(
            """
            INSERT INTO prod_idempotency_keys
                (scope, key, request_hash, status, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("state-test", "retryable", "1" * 64, "FAILED_RETRYABLE", now, now),
        )
        connection.execute(
            """
            INSERT INTO prod_key_operation_audits
                (operation_id, operation, key_id, trust_domain, maker, checker,
                 approval_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "state-key-operation",
                "ROTATE",
                "key-1",
                "sandbox",
                "maker",
                "checker",
                "approval-1",
                "STARTED",
                now,
            ),
        )
        # Reproduce the retry artifact left by a failed SQLite batch migration.
        # The original table remains authoritative, so env.py may safely remove
        # this empty temporary copy before retrying.
        connection.execute(
            'CREATE TABLE "_alembic_tmp_prod_tenants" AS '
            "SELECT * FROM prod_tenants WHERE 0"
        )
        connection.commit()

    _alembic(url, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='_alembic_tmp_prod_tenants'"
        ).fetchone() is None
        assert connection.execute(
            "SELECT state FROM prod_payment_facts ORDER BY fact_id"
        ).fetchall() == [("PASSED",), ("RESERVED",), ("FINAL",), ("DELIVERED",), ("MATCHED",)]
        assert connection.execute(
            "SELECT status FROM prod_outbox_events WHERE event_id='state-event'"
        ).fetchone() == ("PUBLISHED",)
        instruction_ids = connection.execute(
            """
            SELECT instruction_id
            FROM prod_payment_orders
            WHERE initiator_participant='STATE-TEST'
            ORDER BY id
            """
        ).fetchall()
        assert instruction_ids == [
            ("state-instruction",),
            ("state-instruction~sandbox-state-order-duplicate",),
        ]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE prod_outbox_events SET status='MADE_UP_SUCCESS' WHERE event_id='state-event'"
            )
