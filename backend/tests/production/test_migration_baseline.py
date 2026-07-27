from __future__ import annotations

from pathlib import Path

from scripts.verify_migration_baseline import EXPECTED, verify


def test_historical_migration_baseline_hashes_are_immutable():
    verify(Path(__file__).parents[2] / "alembic" / "versions")
    assert set(EXPECTED) == {
        "0001_nextgen_core.py", "0002_production_domain.py", "0003_production_hardening.py"
    }
