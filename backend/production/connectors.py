"""Contract-first connector interfaces and explicitly labelled simulators."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from config import get_settings


class ConnectorNotConfigured(RuntimeError):
    """Raised when a non-simulation connector has not been qualified."""


class QualifiedConnectorUnavailable(ConnectorNotConfigured):
    """Raised when a live connector adapter has not been installed."""


@dataclass(frozen=True)
class ConnectorResult:
    connector: str
    mode: str
    state: str
    external_reference: str
    evidence: dict[str, Any]


class MessageTransportConnector(Protocol):
    def send_message(self, message: dict[str, Any], idempotency_context: str) -> ConnectorResult: ...

    def query_delivery(self, external_reference: str) -> ConnectorResult: ...


class FundingConnector(Protocol):
    def reserve_funds(
        self,
        instruction: dict[str, Any],
        expiry: dt.datetime,
        reservation_intent_id: str,
        idempotency_context: str,
    ) -> ConnectorResult: ...

    def query_reservation(self, reservation_reference: str) -> ConnectorResult: ...

    def release_reservation(
        self, reservation_reference: str, reason: str, idempotency_context: str
    ) -> ConnectorResult: ...

    def consume_reservation(
        self,
        reservation_reference: str,
        settlement_reference: str,
        idempotency_context: str,
    ) -> ConnectorResult: ...


class FxQuoteProvider(Protocol):
    def request_quote(
        self, base_currency: str, quote_currency: str, amount_minor: int, corridor: str
    ) -> ConnectorResult: ...

    def accept_quote(
        self, quote_reference: str, trade_intent_id: str, idempotency_context: str
    ) -> ConnectorResult: ...

    def query_trade_by_intent(self, trade_intent_id: str, provider_client_reference: str) -> ConnectorResult: ...


class ValueSettlementConnector(Protocol):
    def submit(
        self, instruction: dict[str, Any], idempotency_context: str
    ) -> ConnectorResult: ...

    def query(self, external_reference: str) -> ConnectorResult: ...

    def cancel(
        self, original_reference: str, cancellation_request_id: str, reason: str, idempotency_context: str
    ) -> ConnectorResult: ...

    def submit_return(
        self, instruction: dict[str, Any], return_payment_id: str, idempotency_context: str
    ) -> ConnectorResult: ...


def _mode() -> str:
    return get_settings().production_connector_mode


def _require_simulation() -> None:
    if _mode() != "simulation":
        raise ConnectorNotConfigured(
            "No qualified external connector is configured; simulation is the only safe mode"
        )


class QualifiedConnector:
    """Fail-closed placeholder for an independently qualified adapter.

    A deployment must register an implementation through this seam.  Keeping
    the object callable makes accidental simulation in pilot/live impossible.
    """

    def __getattr__(self, name: str):
        def unavailable(*args: Any, **kwargs: Any) -> ConnectorResult:
            raise QualifiedConnectorUnavailable(f"Qualified connector method is not installed: {name}")
        return unavailable


def connector_registry() -> dict[str, Any]:
    mode = _mode()
    if mode == "simulation":
        return {
            "funding": SandboxFundingConnector(),
            "fx": SandboxFxQuoteProvider(),
            "messages": SandboxMessageTransport(),
            "value": SandboxValueSettlement(),
        }
    connector = QualifiedConnector()
    return {"funding": connector, "fx": connector, "messages": connector, "value": connector}


class SandboxMessageTransport:
    def send_message(self, message: dict[str, Any], idempotency_context: str) -> ConnectorResult:
        _require_simulation()
        reference = f"sim-msg-{idempotency_context[:24]}"
        return ConnectorResult(
            "sandbox-message-transport",
            "simulation",
            "DELIVERED",
            reference,
            {"delivery_profile": "sandbox-delivered-v1", "message_hash": message.get("payload_hash")},
        )

    def query_delivery(self, external_reference: str) -> ConnectorResult:
        _require_simulation()
        return ConnectorResult("sandbox-message-transport", "simulation", "DELIVERED", external_reference, {})


class SandboxFundingConnector:
    def reserve_funds(
        self,
        instruction: dict[str, Any],
        expiry: dt.datetime,
        reservation_intent_id: str,
        idempotency_context: str,
    ) -> ConnectorResult:
        _require_simulation()
        reference = f"sim-res-{reservation_intent_id[:24]}-{instruction['currency']}"
        return ConnectorResult(
            "sandbox-funding",
            "simulation",
            "RESERVED",
            reference,
            {"expires_at": expiry.isoformat(), "idempotency_context": idempotency_context},
        )

    def query_reservation(self, reservation_reference: str) -> ConnectorResult:
        _require_simulation()
        return ConnectorResult("sandbox-funding", "simulation", "RESERVED", reservation_reference, {})

    def release_reservation(
        self, reservation_reference: str, reason: str, idempotency_context: str
    ) -> ConnectorResult:
        _require_simulation()
        return ConnectorResult(
            "sandbox-funding", "simulation", "RELEASED", reservation_reference, {"reason": reason}
        )

    def consume_reservation(
        self,
        reservation_reference: str,
        settlement_reference: str,
        idempotency_context: str,
    ) -> ConnectorResult:
        _require_simulation()
        return ConnectorResult(
            "sandbox-funding", "simulation", "CONSUMED", reservation_reference, {"settlement_reference": settlement_reference}
        )


class SandboxFxQuoteProvider:
    def request_quote(
        self, base_currency: str, quote_currency: str, amount_minor: int, corridor: str
    ) -> ConnectorResult:
        _require_simulation()
        quote_reference = f"sim-quote-{uuid.uuid4().hex}"
        quote_amount = amount_minor if base_currency == quote_currency else int(Decimal(amount_minor) * Decimal("1.08"))
        return ConnectorResult(
            "sandbox-fx-provider",
            "simulation",
            "QUOTED",
            quote_reference,
            {
                "base_currency": base_currency,
                "quote_currency": quote_currency,
                "base_amount_minor": amount_minor,
                "quote_amount_minor": quote_amount,
                "rate": "1.000000" if base_currency == quote_currency else "1.080000",
                "fee_minor": 0,
                "corridor": corridor,
                "expires_at": (dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5)).isoformat(),
            },
        )

    def accept_quote(
        self, quote_reference: str, trade_intent_id: str, idempotency_context: str
    ) -> ConnectorResult:
        _require_simulation()
        reference = f"sim-trade-{trade_intent_id[:28]}"
        return ConnectorResult(
            "sandbox-fx-provider",
            "simulation",
            "TRADE_ACCEPTED",
            reference,
            {"quote_reference": quote_reference, "trade_intent_id": trade_intent_id},
        )

    def query_trade_by_intent(self, trade_intent_id: str, provider_client_reference: str) -> ConnectorResult:
        _require_simulation()
        return ConnectorResult(
            "sandbox-fx-provider",
            "simulation",
            "TRADE_ACCEPTED",
            f"sim-trade-{trade_intent_id[:28]}",
            {"provider_client_reference": provider_client_reference},
        )


class SandboxValueSettlement:
    def submit(self, instruction: dict[str, Any], idempotency_context: str) -> ConnectorResult:
        _require_simulation()
        reference = f"sim-settle-{idempotency_context[:28]}"
        return ConnectorResult(
            "sandbox-value-settlement",
            "simulation",
            "FINAL",
            reference,
            {
                "finality_profile": instruction.get("finality_profile_id", "sandbox-finality-v1"),
                "evidence_type": "simulation-finality-proof",
                "amount_minor": instruction.get("amount_minor"),
                "currency": instruction.get("currency"),
            },
        )

    def query(self, external_reference: str) -> ConnectorResult:
        _require_simulation()
        return ConnectorResult(
            "sandbox-value-settlement", "simulation", "FINAL", external_reference, {}
        )

    def cancel(
        self, original_reference: str, cancellation_request_id: str, reason: str, idempotency_context: str
    ) -> ConnectorResult:
        _require_simulation()
        return ConnectorResult(
            "sandbox-value-settlement",
            "simulation",
            "ACCEPTED",
            f"sim-cancel-{cancellation_request_id[:24]}",
            {"original_reference": original_reference, "reason": reason},
        )

    def submit_return(
        self, instruction: dict[str, Any], return_payment_id: str, idempotency_context: str
    ) -> ConnectorResult:
        _require_simulation()
        return ConnectorResult(
            "sandbox-value-settlement",
            "simulation",
            "FINAL",
            f"sim-return-{return_payment_id[:24]}",
            {"original_order_id": instruction.get("original_order_id"), "evidence_type": "simulation-finality-proof"},
        )


def connector_capabilities() -> dict[str, Any]:
    mode = _mode()
    settings = get_settings()
    return {
        "mode": mode,
        "qualified": False,
        "qualification_configured": bool(settings.production_qualified_attestation_path),
        "simulation": mode == "simulation",
        "attestation": "none",
        "connectors": {
            "message_transport": "sandbox-message-transport",
            "funding": "sandbox-funding",
            "fx": "sandbox-fx-provider",
            "value_settlement": "sandbox-value-settlement",
        },
    }
