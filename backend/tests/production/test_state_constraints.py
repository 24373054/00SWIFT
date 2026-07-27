from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from database import Base
from production import models as _production_models  # noqa: F401
from production.state_constraints import ALLOWED_STATES, STATE_VERSION, assert_state


def test_state_vocabulary_is_shared_and_rejects_arbitrary_strings():
    assert STATE_VERSION == "state-v2"
    assert (
        assert_state("prod_payment_orders", "orchestration_state", "CONTROL_CHECKS")
        == "CONTROL_CHECKS"
    )
    assert assert_state("prod_payment_facts", "state", "FINAL") == "FINAL"
    assert assert_state("prod_outbox_events", "status", "PUBLISHED") == "PUBLISHED"
    with pytest.raises(ValueError, match="invalid state"):
        assert_state("prod_payment_orders", "orchestration_state", "MADE_UP_SUCCESS")


def test_state_vocabulary_covers_models_and_matches_head_migration():
    model_columns = {
        (table.name, column.name)
        for table in Base.metadata.sorted_tables
        if table.name.startswith("prod_")
        for column in table.columns
        if column.name in {"state", "status", "contract_state"} or column.name.endswith("_state")
    }
    assert set(ALLOWED_STATES) == model_columns

    migration = runpy.run_path(
        str(
            Path(__file__).parents[2]
            / "alembic"
            / "versions"
            / "0034_production_state_constraints_v2.py"
        )
    )
    migration_vocabulary = {
        key: frozenset(values) for key, values in migration["V2_CONSTRAINTS"].items()
    }
    assert migration_vocabulary == ALLOWED_STATES
