"""Explicit payment orchestration transition specification."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transition:
    source: str
    target: str
    command: str
    event: str
    guard: str
    timeout: str
    compensation: str
    terminal: bool = False


TRANSITIONS = (
    Transition("CONTROL_CHECKS", "RESERVATION_PENDING", "authorize", "payment.authorized", "authorization decision PASS", "authorization SLA", "release limits",),
    Transition("RESERVATION_PENDING", "MESSAGE_DELIVERED", "deliver_message", "payment.message.delivered", "funding RESERVED and compliance PASS", "delivery SLA", "release funding",),
    Transition("MESSAGE_DELIVERED", "VALUE_SETTLEMENT", "settle", "payment.settlement.submitted", "message DELIVERED", "settlement SLA", "query connector then return",),
    Transition("VALUE_SETTLEMENT", "CUSTOMER_COMPLETED", "credit", "payment.beneficiary.credited", "verified beneficiary credit", "credit SLA", "manual recovery case",),
    Transition("CUSTOMER_COMPLETED", "OPERATIONALLY_CLOSED", "close", "payment.operationally.closed", "journal+finality+reconciliation and no reservations", "close SLA", "open case", True),
    Transition("EXECUTION_CANCELLED", "OPERATIONALLY_CLOSED_UNSUCCESSFUL", "close", "payment.cancelled.closed", "all reservations released and external status known", "close SLA", "manual case", True),
)


def transition_spec(source: str, target: str) -> Transition:
    for transition in TRANSITIONS:
        if transition.source == source and transition.target == target:
            return transition
    raise ValueError(f"transition is not specified: {source} -> {target}")
