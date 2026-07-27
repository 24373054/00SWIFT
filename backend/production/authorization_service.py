"""Mandate and approval policy validation before payment authorization."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from .models import ProductionApproval, ProductionMandate, ProductionPaymentOrder, utcnow


class AuthorizationError(ValueError):
    pass


class AuthorizationService:
    def __init__(self, db: Session):
        self.db = db

    def validate_mandate(self, *, principal_id: str, tenant_id: str, account_id: str, debtor_ref: str, amount_minor: int, currency: str, purpose_code: str, mandate_id: str | None, payment_hash: str, now: dt.datetime | None = None) -> ProductionMandate | None:
        if mandate_id is None:
            return None
        current = now or utcnow()
        mandate = self.db.query(ProductionMandate).filter_by(mandate_id=mandate_id, participant_id=principal_id, account_id=account_id, status="ACTIVE").one_or_none()
        if mandate is None or mandate.currency != currency or mandate.purpose_code != purpose_code or mandate.max_amount_minor < amount_minor or mandate.valid_from > current or (mandate.valid_to is not None and mandate.valid_to <= current):
            raise AuthorizationError("mandate does not match participant/tenant/account/payment")
        return mandate

    def validate_approval(self, *, approval_id: str | None, aggregate_type: str, aggregate_id: str, action: str, payment_hash: str, amount_minor: int, checker: str | None) -> ProductionApproval | None:
        if approval_id is None:
            return None
        approval = self.db.query(ProductionApproval).filter_by(approval_id=approval_id, aggregate_type=aggregate_type, aggregate_id=aggregate_id, action=action, state="APPROVED").one_or_none()
        if approval is None or not checker or approval.checker != checker:
            raise AuthorizationError("approval is missing, not approved or checker mismatch")
        if approval.maker == approval.checker:
            raise AuthorizationError("maker/checker separation of duties violated")
        return approval

    def authorize_payment(self, order: ProductionPaymentOrder, *, mandate_id: str | None, approval_id: str | None, checker: str | None) -> None:
        self.validate_mandate(principal_id=order.initiator_participant, tenant_id=order.tenant_id, account_id=order.debtor_account_ref, debtor_ref=order.debtor_party_ref, amount_minor=order.amount_minor, currency=order.currency, purpose_code=order.purpose_code, mandate_id=mandate_id, payment_hash=order.payload_hash)
        self.validate_approval(approval_id=approval_id, aggregate_type="PAYMENT", aggregate_id=order.order_id, action="RELEASE", payment_hash=order.payload_hash, amount_minor=order.amount_minor, checker=checker)
