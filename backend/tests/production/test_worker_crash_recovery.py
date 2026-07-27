import pytest

from production.faults import FaultInjector, InjectedCrash


@pytest.mark.parametrize("point", ["after_claim", "after_inbox", "before_external", "after_external_before_commit", "after_commit_before_ack"])
def test_worker_crash_point_is_recoverable_by_outer_transaction(monkeypatch, point):
    monkeypatch.setenv("SWIFT_ENV", "test")
    injector = FaultInjector(point)
    with pytest.raises(InjectedCrash):
        injector.check(point)
