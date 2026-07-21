"""Shared isolated fixtures for unit and API integration tests."""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
from pathlib import Path

import pytest

_TEST_CERTS = Path(tempfile.gettempdir()) / "00swift-test-certs"
os.environ["SWIFT_ENV"] = "sandbox"
os.environ["DB_URL"] = "sqlite:///:memory:"
os.environ["ADMIN_API_TOKEN"] = "test-admin-token"
os.environ["CERTS_DIR"] = str(_TEST_CERTS)
os.environ["CORS_ORIGINS"] = "http://testserver"

import config
import database

importlib.reload(config)
importlib.reload(database)


@pytest.fixture(autouse=True)
def clean_database():
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)
    database.seed_ecny_data()
    yield


@pytest.fixture
def db():
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_certs():
    shutil.rmtree(_TEST_CERTS, ignore_errors=True)
    yield
    shutil.rmtree(_TEST_CERTS, ignore_errors=True)
