"""Create the versioned standards and settlement research schema.

Revision ID: 0001_nextgen_core
Revises:
Create Date: 2026-07-21
"""
from __future__ import annotations

from alembic import op

from database import Base
from nextgen import models as nextgen_models  # noqa: F401

revision = "0001_nextgen_core"
down_revision = None
branch_labels = None
depends_on = None


def _nextgen_tables():
    return [
        table
        for table in Base.metadata.sorted_tables
        if table.name.startswith("ng_")
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for table in _nextgen_tables():
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(_nextgen_tables()):
        table.drop(bind, checkfirst=True)
