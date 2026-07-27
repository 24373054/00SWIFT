from pathlib import Path


def test_compensation_table_covers_all_external_steps():
    text = Path("docs/domain/COMPENSATION_TABLE.md").read_text(encoding="utf-8")
    for step in ("funding reserve", "FX accept", "message send", "settlement submit", "cancellation", "return"):
        assert step in text
