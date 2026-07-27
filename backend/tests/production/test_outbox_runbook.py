from pathlib import Path


def test_outbox_recovery_runbook_contains_safe_recovery_controls():
    text = Path("docs/runbooks/OUTBOX_RECOVERY.md").read_text(encoding="utf-8")
    assert "payload_hash" in text and "stable client reference" in text and "distinct checker" in text
