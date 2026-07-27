from __future__ import annotations

import re
from pathlib import Path


def test_relational_integrity_migration_is_explicit_and_restrictive():
    source = (Path(__file__).parents[2] / "alembic" / "versions" / "0008_production_relational_integrity.py").read_text(encoding="utf-8")
    assert "Base.metadata.tables" not in source
    assert "batch.create_foreign_key" in source
    assert "ondelete=\"RESTRICT\"" in source
    assert len(re.findall(r'\("prod_', source)) >= 18
