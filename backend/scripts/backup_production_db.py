"""Create and verify a PostgreSQL custom-format backup with an audit manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path


class ExternalDependencyBlocked(RuntimeError):
    """Raised when PostgreSQL client binaries are unavailable."""


def build_dump_command(db_url: str, output: Path) -> list[str]:
    return ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--dbname", db_url, "--file", str(output)]


def backup(db_url: str, output: Path) -> dict[str, object]:
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise ExternalDependencyBlocked("[EXT-BLOCKED] pg_dump is not installed")
    if not db_url.lower().startswith(("postgresql://", "postgresql+")):
        raise ValueError("production backup requires a PostgreSQL URL")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = build_dump_command(db_url, output)
    command[0] = pg_dump
    subprocess.run(command, check=True)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "database_scheme": "postgresql",
        "backup_path": str(output),
        "sha256": digest,
        "size_bytes": output.stat().st_size,
    }
    output.with_suffix(output.suffix + ".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", default=os.getenv("DB_URL"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.db_url:
        parser.error("--db-url or DB_URL is required")
    print(json.dumps(backup(args.db_url, args.output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
