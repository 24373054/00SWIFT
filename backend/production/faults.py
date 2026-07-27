"""Test-only crash injection points for worker recovery tests."""

from __future__ import annotations

import os

CRASH_POINTS = frozenset({"after_claim", "after_inbox", "before_external", "after_external_before_commit", "after_commit_before_ack"})


class InjectedCrash(RuntimeError):
    pass


class FaultInjector:
    def __init__(self, point: str | None = None) -> None:
        self.point = point
        if point is not None and os.getenv("SWIFT_ENV", "sandbox") != "test":
            raise ValueError("fault injection is only enabled in test environment")

    def check(self, point: str) -> None:
        if self.point == point:
            raise InjectedCrash(point)
