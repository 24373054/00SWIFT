"""ISO 20022 / GPI Tracker payment status codes.

Aligned with ``TransactionIndividualStatus5Code`` (the v5 SDK enum, confirmed
in ``research/gpi-v5-demo-app/.../DemoApp.java:114`` which uses ``ACCC``).

Replaces the old ``iso20022.py PAYMENT_STATES`` (which only had PDNG/ACSP/
ACSC/RJCT/CANC). The label/color/icon fields are the **single source of
truth** — the frontend fetches them via ``/api/states`` instead of hardcoding
its own copy (which was duplicated in the old ``app.js``).
"""

from __future__ import annotations

# ---- status code constants (TransactionIndividualStatus5Code) ----

PDNG = "PDNG"  # Pending
ACCP = "ACCP"  # Accepted Customer Credit Pending
ACSP = "ACSP"  # Accepted Settlement in Process
ACSC = "ACSC"  # Accepted Settlement Completed
ACCC = "ACCC"  # Accepted Customer Credit Completed (creditor-side)
RJCT = "RJCT"  # Rejected
CANC = "CANC"  # Cancelled
PART = "PART"  # Partially settled


PAYMENT_STATES: dict[str, dict[str, str]] = {
    PDNG: {"label": "Pending", "color": "#f59e0b", "icon": "clock", "severity": "Logic"},
    ACCP: {
        "label": "Accepted (Customer Credit Pending)",
        "color": "#3b82f6",
        "icon": "refresh-cw",
        "severity": "Logic",
    },
    ACSP: {
        "label": "Accepted (Settlement in Process)",
        "color": "#3b82f6",
        "icon": "refresh-cw",
        "severity": "Logic",
    },
    ACSC: {
        "label": "Accepted (Settlement Completed)",
        "color": "#10b981",
        "icon": "check-circle",
        "severity": "Logic",
    },
    ACCC: {
        "label": "Accepted (Customer Credit Completed)",
        "color": "#10b981",
        "icon": "check-circle",
        "severity": "Logic",
    },
    RJCT: {"label": "Rejected", "color": "#ef4444", "icon": "x-circle", "severity": "Fatal"},
    CANC: {"label": "Cancelled", "color": "#6b7280", "icon": "slash", "severity": "Fatal"},
    PART: {"label": "Partially Settled", "color": "#a855f7", "icon": "divide", "severity": "Logic"},
}


# ---- state machine (valid transitions) ----
# Extended from the old prototype (which only had PDNG/ACSP -> {ACSC,RJCT,CANC}).
# Now models the full creditor-side flow including ACCC and PART.

VALID_TRANSITIONS: dict[str, list[str]] = {
    PDNG: [ACCP, ACSP, RJCT, CANC],
    ACCP: [ACSP, ACSC, RJCT, CANC],
    ACSP: [ACSC, ACCC, PART, RJCT, CANC],
    PART: [ACSC, ACCC, RJCT],
    ACSC: [],  # terminal (settled at debtor side)
    ACCC: [],  # terminal (settled at creditor side)
    RJCT: [],  # terminal
    CANC: [],  # terminal
}

TERMINAL_STATES = {ACSC, ACCC, RJCT, CANC}


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """True if ``to_state`` is a valid next state from ``from_state``."""
    return to_state in VALID_TRANSITIONS.get(from_state, [])


def is_terminal(state: str) -> bool:
    """True if ``state`` is a terminal (no further transitions)."""
    return state in TERMINAL_STATES


def all_states() -> list[dict[str, str]]:
    """Return a list of {code, label, color, icon, severity} for the frontend."""
    return [{"code": code, **info} for code, info in PAYMENT_STATES.items()]
