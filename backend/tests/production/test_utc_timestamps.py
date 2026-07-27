from __future__ import annotations

from sqlalchemy import DateTime

from production import models


def test_production_datetime_columns_are_timezone_aware():
    checked = 0
    for table in models.Base.metadata.tables.values():
        if not table.name.startswith("prod_"):
            continue
        for column in table.columns:
            if isinstance(column.type, DateTime):
                checked += 1
                assert column.type.timezone is True, f"{table.name}.{column.name}"
    assert checked >= 50
