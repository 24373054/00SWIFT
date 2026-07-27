"""Run upgrade -> one-revision downgrade -> upgrade and compare schema snapshots."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parents[2]


def snapshot(url: str) -> dict[str, object]:
    inspector = inspect(create_engine(url))
    tables = {}
    for table in sorted(inspector.get_table_names()):
        if not table.startswith("prod_"):
            continue
        tables[table] = {
            "columns": sorted(column["name"] for column in inspector.get_columns(table)),
            "unique": sorted(item["name"] for item in inspector.get_unique_constraints(table) if item.get("name")),
            "checks": sorted(item["name"] for item in inspector.get_check_constraints(table) if item.get("name")),
            "foreign_keys": sorted(item["name"] for item in inspector.get_foreign_keys(table) if item.get("name")),
        }
    return tables


def _alembic(url: str, *arguments: str) -> None:
    environment = {**os.environ, "DB_URL": url, "PYTHONPATH": str(ROOT)}
    subprocess.run([sys.executable, "-m", "alembic", *arguments], cwd=ROOT, env=environment, check=True)


def roundtrip(url: str | None = None) -> dict[str, object]:
    database_url = url or os.environ.get("DB_URL", "sqlite:///swift_dev.db")
    _alembic(database_url, "upgrade", "head")
    before = snapshot(database_url)
    _alembic(database_url, "downgrade", "-1")
    _alembic(database_url, "upgrade", "head")
    after = snapshot(database_url)
    result = {"tables": len(after), "equal": before == after, "before": before, "after": after}
    if not result["equal"]:
        raise RuntimeError(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    print(json.dumps(roundtrip(), ensure_ascii=False, sort_keys=True))
