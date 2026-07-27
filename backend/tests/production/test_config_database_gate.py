import pytest

from config import Settings


def test_pilot_rejects_sqlite_before_other_external_requirements():
    settings = Settings(swift_env="pilot", db_url="sqlite:///pilot.db")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        settings._validate_production_gate()


def test_live_accepts_postgresql_scheme_for_database_gate(monkeypatch):
    settings = Settings(swift_env="live", db_url="postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.setattr(settings, "production_key_provider", "qualified")
    monkeypatch.setattr(settings, "production_hsm_provider", "qualified")
    with pytest.raises(RuntimeError, match="PRODUCTION_TRUST_DOMAIN"):
        settings._validate_production_gate()
