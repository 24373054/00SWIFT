"""Pytest fixtures for the e-CNY test suite."""
import os
os.environ.setdefault("SWIFT_ENV", "sandbox")
os.environ.setdefault("DB_URL", "sqlite:///:memory:")

import importlib
import pytest

import config
import database
importlib.reload(config)
importlib.reload(database)


@pytest.fixture
def db():
    """Fresh in-memory DB per test, with seeds."""
    from database import init_db, seed_ecny_data, SessionLocal
    init_db()
    seed_ecny_data()
    session = SessionLocal()
    yield session
    session.close()
