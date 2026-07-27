"""Fail CI when any production table, column or named constraint is missing."""

from __future__ import annotations

import json
import os
import sys

from sqlalchemy import create_engine, inspect

from database import Base
from production import models as _production_models  # noqa: F401


def verify(url: str | None = None) -> dict[str, object]:
    engine = create_engine(url or os.getenv("DB_URL", "sqlite:///swift_dev.db"))
    database = inspect(engine)
    expected_tables = {name: table for name, table in Base.metadata.tables.items() if name.startswith("prod_")}
    actual_tables = set(database.get_table_names())
    missing_tables = sorted(set(expected_tables) - actual_tables)
    missing_columns: dict[str, list[str]] = {}
    missing_constraints: dict[str, list[str]] = {}
    for name, table in expected_tables.items():
        if name not in actual_tables:
            continue
        columns = {column["name"] for column in database.get_columns(name)}
        expected_columns = {column.name for column in table.columns}
        if expected_columns - columns:
            missing_columns[name] = sorted(expected_columns - columns)
        actual_constraints = {
            item.get("name")
            for getter in (database.get_unique_constraints, database.get_check_constraints, database.get_foreign_keys)
            for item in getter(name)
            if item.get("name")
        }
        expected_constraints = {constraint.name for constraint in table.constraints if constraint.name}
        if expected_constraints - actual_constraints:
            missing_constraints[name] = sorted(expected_constraints - actual_constraints)
    result = {
        "tables_scanned": len(expected_tables),
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "missing_constraints": missing_constraints,
        "valid": not (missing_tables or missing_columns or missing_constraints),
    }
    if not result["valid"]:
        raise RuntimeError(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True))
    sys.exit(0)
