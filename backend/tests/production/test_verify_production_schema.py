from sqlalchemy import create_engine

from production.models import Base
from scripts.verify_production_schema import verify


def test_schema_verifier_reports_all_production_objects(tmp_path, monkeypatch):
    database = tmp_path / "schema.db"
    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DB_URL", f"sqlite:///{database}")
    result = verify(f"sqlite:///{database}")
    assert result["valid"] is True
    assert result["tables_scanned"] > 30
