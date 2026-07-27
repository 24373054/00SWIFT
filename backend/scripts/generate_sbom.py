"""Generate a minimal CycloneDX-like dependency inventory without network access."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"], check=True, capture_output=True, text=True)
    packages = json.loads(result.stdout)
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "components": [{"type": "library", "name": item["name"], "version": item["version"], "purl": f"pkg:pypi/{item['name'].lower()}@{item['version']}"} for item in packages],
    }
    output = Path(__file__).resolve().parents[2] / "docs" / "sbom-python.json"
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
