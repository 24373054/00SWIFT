from __future__ import annotations

from sqlalchemy.orm import Session

from .models import (
    ProductionCancellationRequest,
    ProductionFxTrade,
    ProductionInvestigationCase,
    ProductionJournal,
    ProductionPaymentOrder,
    ProductionReconciliationRun,
    ProductionReportBatch,
    ProductionReturnPayment,
    ProductionSettlementLeg,
)


def load_payment_graph(db: Session, order_id: str) -> dict[str, list[object] | object | None]:
    order = db.query(ProductionPaymentOrder).filter_by(order_id=order_id).one()
    return {
        "original": order,
        "cancellations": db.query(ProductionCancellationRequest).filter_by(order_id=order_id).all(),
        "returns": db.query(ProductionReturnPayment).filter_by(original_order_id=order_id).all(),
        "investigations": db.query(ProductionInvestigationCase).filter_by(order_id=order_id).all(),
        "fx_trades": db.query(ProductionFxTrade).filter_by(order_id=order_id).all(),
        "settlement_legs": db.query(ProductionSettlementLeg).filter_by(order_id=order_id).all(),
        "journals": db.query(ProductionJournal).filter_by(order_id=order_id).all(),
        "reconciliations": db.query(ProductionReconciliationRun).filter_by(order_id=order_id).all(),
        "reports": db.query(ProductionReportBatch).filter_by(order_id=order_id).all(),
    }
