"""Crash-recoverable production outbox worker.

The worker only executes the explicitly qualified connector mode.  The
default sandbox connector returns evidence marked ``simulation``; pilot/live
without a qualified connector fail closed into the outbox dead-letter path.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from config import get_settings

from .authorization_service import AuthorizationError, AuthorizationService
from .cancellation_service import CancellationService
from .compliance import ProductionComplianceService
from .connectors import (
    connector_registry,
)
from .models import (
    ProductionApproval,
    ProductionAuthorizationDecision,
    ProductionBeneficiaryCredit,
    ProductionCancellationRequest,
    ProductionComplianceDecision,
    ProductionFundingReservation,
    ProductionFxQuote,
    ProductionFxTrade,
    ProductionFxTradeIntent,
    ProductionInboxMessage,
    ProductionOutboxEvent,
    ProductionPaymentOrder,
    ProductionReconciliationRun,
    ProductionReturnPayment,
    ProductionSettlementLeg,
    utcnow,
)
from .runtime import (
    ProductionAuditService,
    ProductionEvidenceService,
    ProductionOutboxService,
    canonical_json,
    digest,
)
from .service import ProductionPaymentService, set_order_state
from .telemetry import record_worker_heartbeat


def _payload(event: ProductionOutboxEvent) -> dict[str, Any]:
    return json.loads(event.payload)


class ProductionWorker:
    consumer = "production-worker-v1"

    def __init__(self, db: Session):
        self.db = db
        self.owner = f"{self.consumer}:{uuid.uuid4().hex}"
        self.payments = ProductionPaymentService(db)
        registry = connector_registry()
        self.funding = registry["funding"]
        self.fx = registry["fx"]
        self.messages = registry["messages"]
        self.value = registry["value"]

    def _transition(self, order: ProductionPaymentOrder, state: str, outcome: str | None = None) -> None:
        set_order_state(self.db, order.order_id, state, outcome, expected_version=order.version)
        self.db.refresh(order)

    def run_once(self, limit: int = 50) -> dict[str, int]:
        record_worker_heartbeat()
        outbox = ProductionOutboxService(self.db)
        events = outbox.claim(limit, owner=self.owner)
        self.db.commit()
        processed = 0
        failed = 0
        for event in events:
            try:
                if not self._register_inbox(event):
                    fresh = self.db.query(ProductionOutboxEvent).filter_by(id=event.id).one()
                    outbox.complete(fresh, owner=self.owner)
                    self.db.commit()
                    processed += 1
                    continue
                self._handle(event)
                fresh = self.db.query(ProductionOutboxEvent).filter_by(id=event.id).one()
                outbox.complete(fresh, owner=self.owner)
                self.db.commit()
                processed += 1
            except Exception as exc:  # noqa: BLE001 - persisted to DLQ for operations
                self.db.rollback()
                fresh = self.db.query(ProductionOutboxEvent).filter_by(id=event.id).one_or_none()
                if fresh is not None:
                    outbox.fail(fresh, str(exc))
                    self.db.commit()
                failed += 1
        return {"claimed": len(events), "processed": processed, "failed": failed}

    def _register_inbox(self, event: ProductionOutboxEvent) -> bool:
        """Persist consumer/event receipt before side effects.

        A retry after a crash can therefore be recognised by the unique
        consumer/event key.  The receipt is part of the same transaction as
        the handler; failures roll it back and remain safely retryable.
        """
        existing = (
            self.db.query(ProductionInboxMessage)
            .filter_by(consumer=self.consumer, event_id=event.event_id)
            .first()
        )
        if existing is not None:
            return False
        self.db.add(
            ProductionInboxMessage(
                consumer=self.consumer,
                event_id=event.event_id,
                payload_hash=hashlib.sha256(event.payload.encode("utf-8")).hexdigest(),
            )
        )
        self.db.flush()
        return True

    def _handle(self, event: ProductionOutboxEvent) -> None:
        payload = _payload(event)
        handlers = {
            "payment.created": self._payment_created,
            "funding.reserve.requested": self._funding_reserve,
            "fx.accept.requested": self._fx_accept,
            "settlement.submit.requested": self._settlement_submit,
            "payment.message.requested": self._message_send,
            "payment.value.requested": self._payment_value,
            "payment.cancellation.requested": self._cancel,
            "payment.return.requested": self._return,
        }
        handler = handlers.get(event.topic)
        if handler is None:
            raise ValueError(f"Unsupported production outbox topic: {event.topic}")
        handler(payload)

    def _payment_created(self, payload: dict[str, Any]) -> None:
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=payload["order_id"]).one()
        settings = get_settings()
        auth_decision = self.db.query(ProductionAuthorizationDecision).filter_by(order_id=order.order_id).order_by(ProductionAuthorizationDecision.id.desc()).first()
        authorization_ok = settings.is_sandbox or (auth_decision is not None and auth_decision.outcome == "PASSED")
        if not settings.is_sandbox and auth_decision is not None and auth_decision.outcome != "PASSED":
            approval = self.db.query(ProductionApproval).filter_by(approval_id=auth_decision.approval_ref, state="APPROVED").one_or_none() if auth_decision.approval_ref else None
            try:
                AuthorizationService(self.db).authorize_payment(order, mandate_id=auth_decision.mandate_ref, approval_id=auth_decision.approval_ref, checker=approval.checker if approval else None)
                authorization_ok = True
            except AuthorizationError:
                authorization_ok = False
        if auth_decision is not None and auth_decision.outcome != "PASSED":
            outcome = "PASSED" if authorization_ok else "REJECTED"
            self.payments.append_fact(order.order_id, "AUTHORIZATION", outcome, auth_decision.decision_id, {"rule_version": auth_decision.rule_version})
            self.db.add(ProductionAuthorizationDecision(decision_id=f"authz_{uuid.uuid4().hex}", order_id=order.order_id, outcome=outcome, payment_hash=auth_decision.payment_hash, mandate_ref=auth_decision.mandate_ref, approval_ref=auth_decision.approval_ref, input_hash=auth_decision.input_hash, rule_version=auth_decision.rule_version, evidence_ref=auth_decision.evidence_ref))
        if not authorization_ok:
            self._transition(order, "SUSPENDED", "REJECTED")
            return
        decision = self.db.query(ProductionComplianceDecision).filter_by(order_id=order.order_id).order_by(ProductionComplianceDecision.id.desc()).first()
        if decision is not None and decision.outcome != "PASSED":
            outcome = ProductionComplianceService(self.db).evaluate(order)
            evidence_ref = ProductionEvidenceService(self.db).record("compliance.screening", order.order_id, {"outcome": outcome, "rule_version": ProductionComplianceService.rule_version}).evidence_id
            if outcome != "PASSED":
                self.payments.append_fact(order.order_id, "COMPLIANCE", outcome, decision.decision_id, {"rule_version": decision.rule_version, "evidence_id": evidence_ref})
                self.db.add(ProductionComplianceDecision(decision_id=f"comp_{uuid.uuid4().hex}", order_id=order.order_id, outcome=outcome, input_hash=decision.input_hash, rule_version=ProductionComplianceService.rule_version, list_version="sandbox-list-2026-01", case_id=decision.case_id, evidence_ref=evidence_ref))
                self._transition(order, "COMPLIANCE_REJECTED", "REJECTED")
                self._transition(order, "OPERATIONALLY_CLOSED_UNSUCCESSFUL", "REJECTED")
                return
            self.payments.append_fact(order.order_id, "COMPLIANCE", "PASSED", decision.decision_id, {"rule_version": ProductionComplianceService.rule_version, "evidence_id": evidence_ref})
            self.db.add(ProductionComplianceDecision(decision_id=f"comp_{uuid.uuid4().hex}", order_id=order.order_id, outcome="PASSED", input_hash=decision.input_hash, rule_version=ProductionComplianceService.rule_version, list_version="sandbox-list-2026-01", case_id=decision.case_id, evidence_ref=evidence_ref))
        existing_intent = self.db.query(ProductionFxTradeIntent).filter_by(order_id=order.order_id).first()
        if existing_intent:
            return
        if order.currency != order.settlement_currency:
            # Cross-currency orders must cross the explicit FX acceptance
            # barrier before any funding reservation is created here.
            self._transition(order, "FX_ACCEPTANCE_PENDING")
            return
        self._transition(order, "RESERVATION_PENDING")
        reservation = (
            self.db.query(ProductionFundingReservation)
            .filter_by(order_id=order.order_id, funding_reference=f"{order.initiator_participant}:{order.currency}")
            .first()
        )
        if reservation is None:
            reservation = ProductionFundingReservation(
                reservation_id=f"res_{uuid.uuid4().hex}",
                reservation_intent_id=f"payment-{order.order_id}",
                order_id=order.order_id,
                funding_reference=f"{order.initiator_participant}:{order.currency}",
                currency=order.currency,
                amount_minor=order.amount_minor,
            )
            self.db.add(reservation)
            self.db.flush()
            ProductionOutboxService(self.db).enqueue(
                "funding.reserve.requested",
                reservation.reservation_id,
                {
                    "reservation_id": reservation.reservation_id,
                    "reservation_intent_id": reservation.reservation_intent_id,
                    "order_id": order.order_id,
                    "funding_reference": reservation.funding_reference,
                    "currency": reservation.currency,
                    "amount_minor": reservation.amount_minor,
                },
            )

    def _funding_reserve(self, payload: dict[str, Any]) -> None:
        reservation = self.db.query(ProductionFundingReservation).filter_by(reservation_id=payload["reservation_id"]).one()
        if reservation.state == "RESERVED":
            return
        result = self.funding.reserve_funds(
            payload,
            utcnow(),
            payload["reservation_intent_id"],
            f"reserve-{reservation.reservation_id}",
        )
        reservation.state = result.state
        reservation.external_reference = result.external_reference
        reservation.evidence_ref = ProductionEvidenceService(self.db).record(
            "funding.reservation", reservation.reservation_id, result.evidence
        ).evidence_id
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=reservation.order_id).one()
        self.payments.append_fact(order.order_id, "FUNDING", result.state, reservation.reservation_id, result.evidence)
        reservations = self.db.query(ProductionFundingReservation).filter_by(reservation_intent_id=reservation.reservation_intent_id).all()
        if not reservations or not all(item.state == "RESERVED" for item in reservations):
            return
        intent = self.db.query(ProductionFxTradeIntent).filter_by(trade_intent_id=reservation.reservation_intent_id).first()
        if intent is not None:
            if intent.state == "PREPARING":
                intent.state = "READY_TO_ACCEPT"
                ProductionOutboxService(self.db).enqueue(
                    "fx.accept.requested",
                    intent.trade_intent_id,
                    {"trade_intent_id": intent.trade_intent_id, "quote_id": intent.quote_id, "order_id": order.order_id},
                )
                self._transition(order, "FX_ACCEPTANCE_PENDING")
        elif not self._has_event("payment.message.requested", order.order_id):
            ProductionOutboxService(self.db).enqueue("payment.message.requested", order.order_id, {"order_id": order.order_id})

    def _fx_accept(self, payload: dict[str, Any]) -> None:
        intent = self.db.query(ProductionFxTradeIntent).filter_by(trade_intent_id=payload["trade_intent_id"]).one()
        if intent.state == "TRADE_ACCEPTED":
            return
        quote = self.db.query(ProductionFxQuote).filter_by(quote_id=intent.quote_id).one()
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=intent.order_id).one()
        result = self.fx.accept_quote(quote.quote_id, intent.trade_intent_id, intent.idempotency_context)
        intent.state = result.state
        quote.status = "ACCEPTED"
        self._transition(order, "FX_ACCEPTED")
        intent.trade_reference = result.external_reference
        intent.provider_reference = intent.idempotency_context
        intent.evidence_ref = ProductionEvidenceService(self.db).record(
            "fx.trade.acceptance", intent.trade_intent_id, result.evidence
        ).evidence_id
        self.payments.append_fact(order.order_id, "FX", result.state, intent.trade_intent_id, result.evidence)
        trade = ProductionFxTrade(
            trade_id=f"trade_{uuid.uuid4().hex}",
            trade_intent_id=intent.trade_intent_id,
            order_id=order.order_id,
            contract_state=result.state,
            trade_reference=result.external_reference,
            payload=canonical_json(result.evidence),
            evidence_ref=intent.evidence_ref,
        )
        self.db.add(trade)
        payment_leg = self.db.query(ProductionSettlementLeg).filter_by(order_id=order.order_id, leg_role="PAYMENT_VALUE").one_or_none()
        if payment_leg is not None:
            payment_leg.amount_minor = quote.quote_amount_minor
            payment_leg.currency = quote.quote_currency
        for role, currency, amount in (
            ("FX_SELL", quote.base_currency, quote.base_amount_minor),
            ("FX_BUY", quote.quote_currency, quote.quote_amount_minor),
        ):
            leg = ProductionSettlementLeg(
                leg_id=f"leg_{uuid.uuid4().hex}",
                order_id=order.order_id,
                leg_role=role,
                connector="sandbox-value-settlement",
                currency=currency,
                amount_minor=amount,
                finality_profile_id="sandbox-finality-v1",
            )
            self.db.add(leg)
            ProductionOutboxService(self.db).enqueue(
                "settlement.submit.requested",
                leg.leg_id,
                {"order_id": order.order_id, "leg_id": leg.leg_id},
            )

    def _settlement_submit(self, payload: dict[str, Any]) -> None:
        leg = self.db.query(ProductionSettlementLeg).filter_by(leg_id=payload["leg_id"]).one()
        if leg.state == "FINAL":
            return
        result = self.value.submit(
            {
                "amount_minor": leg.amount_minor,
                "currency": leg.currency,
                "finality_profile_id": leg.finality_profile_id,
            },
            f"settlement-{leg.leg_id}",
        )
        leg.state = result.state
        leg.external_reference = result.external_reference
        leg.evidence_ref = ProductionEvidenceService(self.db).record(
            "settlement.finality", leg.leg_id, result.evidence
        ).evidence_id
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=leg.order_id).one()
        self.payments.append_fact(order.order_id, "SETTLEMENT", result.state, leg.leg_role, result.evidence)
        if leg.leg_role in {"FX_SELL", "FX_BUY"}:
            fx_legs = (
                self.db.query(ProductionSettlementLeg)
                .filter(
                    ProductionSettlementLeg.order_id == order.order_id,
                    ProductionSettlementLeg.leg_role.in_(["FX_SELL", "FX_BUY"]),
                )
                .all()
            )
            if all(item.state == "FINAL" for item in fx_legs) and not self._has_event("payment.message.requested", order.order_id):
                ProductionOutboxService(self.db).enqueue("payment.message.requested", order.order_id, {"order_id": order.order_id})

    def _message_send(self, payload: dict[str, Any]) -> None:
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=payload["order_id"]).one()
        result = self.messages.send_message({"payload_hash": order.payload_hash}, f"message-{order.order_id}")
        message_evidence = ProductionEvidenceService(self.db).record(
            "message.delivery", order.order_id, result.evidence
        ).evidence_id
        self.payments.append_fact(order.order_id, "MESSAGE", result.state, "payment-message", {"evidence_id": message_evidence, **result.evidence})
        if result.state in {"DELIVERED", "NETWORK_ACKED"}:
            self._transition(order, "MESSAGE_DELIVERED")
            if not self._has_event("payment.value.requested", order.order_id):
                ProductionOutboxService(self.db).enqueue("payment.value.requested", order.order_id, {"order_id": order.order_id})
        else:
            self._transition(order, "SUSPENDED")

    def _payment_value(self, payload: dict[str, Any]) -> None:
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=payload["order_id"]).one()
        leg = self.db.query(ProductionSettlementLeg).filter_by(order_id=order.order_id, leg_role="PAYMENT_VALUE").one()
        if leg.state == "FINAL":
            return
        result = self.value.submit(
            {"amount_minor": leg.amount_minor, "currency": leg.currency, "finality_profile_id": leg.finality_profile_id},
            f"payment-value-{order.order_id}",
        )
        leg.state = result.state
        leg.external_reference = result.external_reference
        leg.evidence_ref = ProductionEvidenceService(self.db).record("settlement.finality", leg.leg_id, result.evidence).evidence_id
        self.payments.append_fact(order.order_id, "SETTLEMENT", result.state, leg.leg_role, result.evidence)
        if result.state == "FINAL":
            self._transition(order, "VALUE_SETTLEMENT")
            self._complete_payment(order)

    def _complete_payment(self, order: ProductionPaymentOrder) -> None:
        for reservation in self.db.query(ProductionFundingReservation).filter_by(order_id=order.order_id, state="RESERVED").all():
            result = self.funding.consume_reservation(
                reservation.external_reference or reservation.reservation_id,
                f"payment-value-{order.order_id}",
                f"consume-{reservation.reservation_id}",
            )
            reservation.state = result.state
            reservation.external_reference = result.external_reference
            reservation.evidence_ref = ProductionEvidenceService(self.db).record(
                "funding.consumption", reservation.reservation_id, result.evidence
            ).evidence_id
            self.payments.append_fact(order.order_id, "FUNDING", result.state, reservation.reservation_id, {"evidence_id": reservation.evidence_ref, **result.evidence})
        credit = self.db.query(ProductionBeneficiaryCredit).filter_by(order_id=order.order_id).first()
        if credit is None:
            credit = ProductionBeneficiaryCredit(
                credit_id=f"credit_{uuid.uuid4().hex}",
                order_id=order.order_id,
                state="CREDITED",
                external_reference=f"sim-credit-{order.order_id[4:20]}",
            )
            credit.evidence_ref = ProductionEvidenceService(self.db).record(
                "beneficiary.credit", credit.credit_id, {"state": credit.state}
            ).evidence_id
            self.db.add(credit)
        self.payments.append_fact(order.order_id, "BENEFICIARY", "CREDITED", credit.credit_id, {})
        self._transition(order, "CUSTOMER_COMPLETED", "COMPLETED")
        reservations = self.db.query(ProductionFundingReservation).filter_by(order_id=order.order_id).all()
        legs = self.db.query(ProductionSettlementLeg).filter_by(order_id=order.order_id).all()
        recon = ProductionReconciliationRun(
            run_id=f"recon_{uuid.uuid4().hex}",
            order_id=order.order_id,
            state="MATCHED",
            payment_hash=order.payload_hash,
            subledger_hash=digest([{"reservation_id": r.reservation_id, "state": r.state, "amount_minor": r.amount_minor} for r in reservations]),
            external_statement_hash=digest([{"leg_id": leg.leg_id, "state": leg.state, "external_reference": leg.external_reference} for leg in legs]),
            institution_gl_hash=digest({"order_id": order.order_id, "amount_minor": order.amount_minor, "currency": order.currency}),
            break_details="[]",
        )
        self.db.add(recon)
        self.payments.append_fact(order.order_id, "RECONCILIATION", "MATCHED", recon.run_id, {})
        self._transition(order, "OPERATIONALLY_CLOSED", "COMPLETED")
        ProductionAuditService(self.db).append("payment.completed", order.order_id, {"uetr": order.uetr}, "production-worker")

    def _cancel(self, payload: dict[str, Any]) -> None:
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=payload["order_id"]).one()
        leg = self.db.query(ProductionSettlementLeg).filter_by(order_id=order.order_id, leg_role="PAYMENT_VALUE").one()
        request = self.db.query(ProductionCancellationRequest).filter_by(cancellation_request_id=payload["cancellation_request_id"]).one()
        result = self.value.cancel(leg.external_reference or leg.leg_id, request.cancellation_request_id, request.reason, request.idempotency_context)
        request.external_reference = result.external_reference
        request.evidence_ref = ProductionEvidenceService(self.db).record("payment.cancellation", request.cancellation_request_id, result.evidence).evidence_id
        self.payments.append_fact(order.order_id, "CANCELLATION", result.state, request.cancellation_request_id, result.evidence)
        if result.state == "ACCEPTED" and leg.state != "FINAL":
            CancellationService(self.db).accept(request.cancellation_request_id, evidence={"external_reference": result.external_reference, **result.evidence})
        elif result.state in {"REJECTED", "UNKNOWN"}:
            CancellationService(self.db).transition(request.cancellation_request_id, result.state)

    def _return(self, payload: dict[str, Any]) -> None:
        return_payment = self.db.query(ProductionReturnPayment).filter_by(return_payment_id=payload["return_payment_id"]).one()
        result = self.value.submit_return(
            {"original_order_id": return_payment.original_order_id, "amount_minor": return_payment.amount_minor, "currency": return_payment.currency},
            return_payment.return_payment_id,
            return_payment.idempotency_context,
        )
        return_payment.state = result.state
        return_payment.external_reference = result.external_reference
        return_payment.evidence_ref = ProductionEvidenceService(self.db).record("payment.return", return_payment.return_payment_id, result.evidence).evidence_id
        leg = self.db.query(ProductionSettlementLeg).filter_by(leg_id=return_payment.return_leg_id).one()
        leg.state = result.state
        leg.external_reference = result.external_reference
        leg.evidence_ref = return_payment.evidence_ref
        order = self.db.query(ProductionPaymentOrder).filter_by(order_id=return_payment.original_order_id).one()
        self.payments.append_fact(
            order.order_id,
            "RETURN",
            result.state,
            return_payment.return_payment_id,
            {"evidence_id": return_payment.evidence_ref, **result.evidence},
        )

    def _has_event(self, topic: str, aggregate_id: str) -> bool:
        return (
            self.db.query(ProductionOutboxEvent)
            .filter(
                ProductionOutboxEvent.topic == topic,
                ProductionOutboxEvent.aggregate_id == aggregate_id,
                ProductionOutboxEvent.status.in_(["PENDING", "PROCESSING", "PUBLISHED"]),
            )
            .first()
            is not None
        )
