from pathlib import Path

import pytest

from scripts.backup_production_db import ExternalDependencyBlocked, backup, build_dump_command


def test_backup_command_is_custom_format_and_no_owner():
    command = build_dump_command("postgresql://db", Path("backup.dump"))
    assert "--format=custom" in command
    assert "--no-owner" in command
    assert "--no-privileges" in command


def test_backup_requires_postgres_client(monkeypatch, tmp_path):
    monkeypatch.setattr("scripts.backup_production_db.shutil.which", lambda _name: None)
    with pytest.raises(ExternalDependencyBlocked, match="EXT-BLOCKED"):
        backup("postgresql://db", tmp_path / "backup.dump")
