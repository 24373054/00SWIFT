"""Read-only operational projections and four-way reconciliation."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from .models import (
    ProductionFundingReservation,
    ProductionJournalEntry,
    ProductionPaymentOrder,
    ProductionReconciliationBreak,
    ProductionReconciliationRun,
    ProductionSettlementLeg,
)
from .runtime import ProductionAuditService


def reconciliation_report(db: Session, *, record_audit: bool = True) -> dict[str, Any]:
    breaks: list[dict[str, Any]] = []
    orders = db.query(ProductionPaymentOrder).all()
    for order in orders:
        legs = db.query(ProductionSettlementLeg).filter_by(order_id=order.order_id).all()
        reservations = db.query(ProductionFundingReservation).filter_by(order_id=order.order_id).all()
        if order.customer_outcome == "COMPLETED" and any(leg.state != "FINAL" for leg in legs if leg.leg_role == "PAYMENT_VALUE"):
            breaks.append({"order_id": order.order_id, "reason": "completed order has non-final payment leg"})
        if any(res.state == "RESERVED" for res in reservations) and order.orchestration_state in {
            "OPERATIONALLY_CLOSED",
            "OPERATIONALLY_CLOSED_UNSUCCESSFUL",
        }:
            breaks.append({"order_id": order.order_id, "reason": "closed order retains funding reservation"})
        if len({leg.currency for leg in legs}) > 1 and order.currency == order.settlement_currency:
            breaks.append({"order_id": order.order_id, "reason": "same-currency order has multi-currency legs"})
        if order.customer_outcome == "COMPLETED":
            recon = (
                db.query(ProductionReconciliationRun)
                .filter_by(order_id=order.order_id)
                .order_by(ProductionReconciliationRun.id.desc())
                .first()
            )
            if recon is None or recon.state != "MATCHED":
                breaks.append({"order_id": order.order_id, "reason": "completed order has no matched reconciliation"})
    journals = db.query(ProductionJournalEntry).all()
    journal_debits: dict[str, int] = {}
    journal_credits: dict[str, int] = {}
    for entry in journals:
        target = journal_debits if entry.direction == "DEBIT" else journal_credits
        target[entry.currency] = target.get(entry.currency, 0) + entry.amount_minor
    for currency in set(journal_debits) | set(journal_credits):
        if journal_debits.get(currency, 0) != journal_credits.get(currency, 0):
            breaks.extend(
                [{
                    "currency": currency,
                    "reason": "ledger debit/credit imbalance",
                    "debit": journal_debits.get(currency, 0),
                    "credit": journal_credits.get(currency, 0),
                }]
            )
    report = {
        "run_at": dt.datetime.now(dt.UTC),
        "ok": not breaks,
        "payment_count": len(orders),
        "journal_entry_count": len(journals),
        "breaks": breaks,
        "severity": "SEV-0" if any(item.get("reason") == "ledger debit/credit imbalance" for item in breaks) else "NONE",
    }
    for item in breaks:
        order_id = item.get("order_id")
        if order_id:
            existing = db.query(ProductionReconciliationBreak).filter_by(order_id=order_id, break_type=item["reason"], state="OPEN").first()
            if existing is None:
                db.add(ProductionReconciliationBreak(
                    break_id=f"break_{uuid.uuid4().hex}", order_id=order_id,
                    break_type=item["reason"], severity="SEV-0" if "ledger" in item["reason"] else "P2",
                    details=json.dumps(item, sort_keys=True, default=str),
                ))
    if record_audit:
        ProductionAuditService(db).append("reconciliation.completed", "system", report, "system")
    return report


def operations_summary(db: Session) -> dict[str, Any]:
    orders = db.query(ProductionPaymentOrder).all()
    counts: dict[str, int] = {}
    for order in orders:
        counts[order.orchestration_state] = counts.get(order.orchestration_state, 0) + 1
    reservations = db.query(ProductionFundingReservation).all()
    return {
        "generated_at": dt.datetime.now(dt.UTC),
        "payments": len(orders),
        "payment_states": counts,
        "funding": {
            "reserved": sum(item.amount_minor for item in reservations if item.state == "RESERVED"),
            "consumed": sum(item.amount_minor for item in reservations if item.state == "CONSUMED"),
            "unknown": sum(item.amount_minor for item in reservations if item.state == "UNKNOWN"),
        },
        "reconciliation": reconciliation_report(db, record_audit=False),
    }
