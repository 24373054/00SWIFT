import pytest

from production.faults import FaultInjector, InjectedCrash


def test_all_worker_crash_points_are_explicit_and_test_only(monkeypatch):
    monkeypatch.setenv("SWIFT_ENV", "test")
    for point in ("after_claim", "after_inbox", "before_external", "after_external_before_commit", "after_commit_before_ack"):
        with pytest.raises(InjectedCrash, match=point):
            FaultInjector(point).check(point)


def test_fault_injection_is_rejected_outside_test(monkeypatch):
    monkeypatch.setenv("SWIFT_ENV", "pilot")
    with pytest.raises(ValueError, match="test environment"):
        FaultInjector("after_claim")
