"""Fail-closed hash verification for immutable historical migrations."""

from __future__ import annotations

import hashlib
from pathlib import Path

EXPECTED = {
    "0001_nextgen_core.py": "8C138AD3E5398C65EEC995E6B1D31282FF1091F7406D99ADC569EFB680B16FC6",
    "0002_production_domain.py": "898617045F539A3B876AF5A71D7DA3E77B191DC3DFA7294E3C065B659745E8E5",
    "0003_production_hardening.py": "7CE96D09AE341A263DC82C589F6A68E97275CC12AF548A147A1D987416C708FB",
}


def verify(directory: Path | None = None) -> None:
    root = directory or Path(__file__).resolve().parents[1] / "alembic" / "versions"
    failures: list[str] = []
    for filename, expected in EXPECTED.items():
        path = root / filename
        if not path.is_file():
            failures.append(f"missing baseline: {filename}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        if actual != expected:
            failures.append(f"hash mismatch: {filename} expected={expected} actual={actual}")
    if failures:
        raise SystemExit("; ".join(failures))


if __name__ == "__main__":
    verify()
