"""Versioned reporting projection; it emits facts, never mutates payments."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy.orm import Session

from .models import ProductionPaymentFact, ProductionPaymentOrder
from .runtime import digest


def build_regulatory_report(db: Session, report_type: str, business_date: str | None = None) -> dict[str, Any]:
    date = business_date or dt.date.today().isoformat()
    orders = db.query(ProductionPaymentOrder).filter(ProductionPaymentOrder.created_at >= dt.datetime.fromisoformat(f"{date}T00:00:00+00:00")).all()
    rows = []
    for order in orders:
        facts = db.query(ProductionPaymentFact).filter_by(order_id=order.order_id).all()
        rows.append({
            "uetr": order.uetr,
            "instruction_id": order.instruction_id,
            "corridor": order.corridor,
            "currency": order.currency,
            "settlement_currency": order.settlement_currency,
            "amount_minor": order.amount_minor,
            "orchestration_state": order.orchestration_state,
            "customer_outcome": order.customer_outcome,
            "fact_count": len(facts),
        })
    payload = {"report_type": report_type, "business_date": date, "schema_version": "production-report-v1", "rows": rows}
    return {**payload, "row_count": len(rows), "report_hash": digest(payload)}
