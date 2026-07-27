"""Command-only payment aggregate facade."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .models import ProductionPaymentOrder
from .runtime import ProductionConflict


@dataclass(frozen=True)
class PaymentAggregate:
    db: Session
    order_id: str

    def _command(self, state: str, expected_version: int, outcome: str | None = None) -> ProductionPaymentOrder:
        from .service import set_order_state

        set_order_state(self.db, self.order_id, state, outcome, expected_version=expected_version)
        return self.db.query(ProductionPaymentOrder).filter_by(order_id=self.order_id).one()

    def create(self, expected_version: int = 1):
        return self._command("CONTROL_CHECKS", expected_version)

    def authorize(self, expected_version: int):
        return self._command("RESERVATION_PENDING", expected_version)

    def screen(self, expected_version: int, *, rejected: bool = False):
        return self._command("COMPLIANCE_REJECTED" if rejected else "RESERVATION_PENDING", expected_version, "REJECTED" if rejected else None)

    def reserve(self, expected_version: int):
        return self._command("RESERVATION_PENDING", expected_version)

    def accept_fx(self, expected_version: int):
        return self._command("FX_ACCEPTED", expected_version)

    def deliver_message(self, expected_version: int):
        return self._command("MESSAGE_DELIVERED", expected_version)

    def settle(self, expected_version: int):
        return self._command("VALUE_SETTLEMENT", expected_version)

    def credit(self, expected_version: int):
        return self._command("CUSTOMER_COMPLETED", expected_version, "COMPLETED")

    def cancel(self, expected_version: int):
        return self._command("EXECUTION_CANCELLED", expected_version, "CANCELLED")

    def return_payment(self, expected_version: int):
        return self._command("SUSPENDED", expected_version, "RETURN_REQUESTED")

    def suspend(self, expected_version: int):
        return self._command("SUSPENDED", expected_version)

    def resume(self, expected_version: int):
        return self._command("RESERVATION_PENDING", expected_version)

    def close(self, expected_version: int, *, successful: bool = True):
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=self.order_id).one()
        if successful and order.customer_outcome != "COMPLETED":
            raise ProductionConflict("successful close requires verified customer credit")
        return self._command("OPERATIONALLY_CLOSED" if successful else "OPERATIONALLY_CLOSED_UNSUCCESSFUL", expected_version, order.customer_outcome)
