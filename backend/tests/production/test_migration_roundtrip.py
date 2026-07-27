from scripts.migration_roundtrip import roundtrip


def test_sqlite_upgrade_downgrade_reupgrade_schema_snapshot(tmp_path):
    result = roundtrip(f"sqlite:///{tmp_path / 'roundtrip.db'}")
    assert result["equal"] is True
    assert result["tables"] > 30
