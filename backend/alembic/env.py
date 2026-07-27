"""Alembic environment for SQLite sandbox and PostgreSQL deployments."""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, inspect, pool, text

from alembic import context
from database import Base
from nextgen import models as nextgen_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url",
    os.getenv("DB_URL", config.get_main_option("sqlalchemy.url")),
)

def _load_production_models(*, baseline: bool) -> None:
    if baseline:
        os.environ["_00SWIFT_ALEMBIC_BASELINE"] = "1"
        from production import models as production_models

        for table in production_models.Base.metadata.sorted_tables:
            table.to_metadata(Base.metadata)
    else:
        os.environ.pop("_00SWIFT_ALEMBIC_BASELINE", None)
        from production import models as production_models  # noqa: F401


def _requires_frozen_baseline(connection) -> bool:
    if "alembic_version" not in inspect(connection).get_table_names():
        return True
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    return revision in {None, "0001_nextgen_core", "0002_production_domain"}


def _recover_interrupted_sqlite_batches(connection) -> None:
    """Remove retry-safe Alembic batch leftovers in sandbox SQLite databases.

    SQLite batch migrations use ``_alembic_tmp_*`` tables.  A failed
    non-transactional DDL step can leave one behind and make every retry fail.
    The original table must still exist before a temporary copy is removed;
    otherwise the temporary table may be the only surviving data and recovery
    must be performed manually.
    """

    if connection.dialect.name != "sqlite":
        return
    environment = os.getenv("SWIFT_ENV", "sandbox").strip().lower()
    if environment not in {"sandbox", "test"}:
        raise RuntimeError("SQLite migration recovery is restricted to sandbox/test")

    tables = set(inspect(connection).get_table_names())
    temporary_tables = sorted(name for name in tables if name.startswith("_alembic_tmp_"))
    if not temporary_tables:
        return

    quote = connection.dialect.identifier_preparer.quote
    for temporary_table in temporary_tables:
        original_table = temporary_table.removeprefix("_alembic_tmp_")
        if original_table not in tables:
            raise RuntimeError(
                f"Interrupted SQLite batch requires manual recovery: "
                f"{temporary_table} exists but {original_table} does not"
            )
        connection.exec_driver_sql(f"DROP TABLE {quote(temporary_table)}")
        config.print_stdout(
            f"Recovered interrupted SQLite batch table {temporary_table}; "
            f"preserved authoritative table {original_table}"
        )
    connection.commit()


def run_migrations_offline() -> None:
    _load_production_models(baseline=True)
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _recover_interrupted_sqlite_batches(connection)
        baseline = _requires_frozen_baseline(connection)
        if connection.in_transaction():
            connection.rollback()
        _load_production_models(baseline=baseline)
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
