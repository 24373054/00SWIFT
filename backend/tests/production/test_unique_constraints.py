from production.models import (
    ProductionApproval,
    ProductionFxTradeIntent,
    ProductionJournal,
    ProductionOutboxEvent,
    ProductionPaymentOrder,
    ProductionReturnPayment,
)


def _constraint_names(model):
    return {constraint.name for constraint in model.__table__.constraints}


def test_business_unique_constraints_are_declared_with_scopes():
    assert "uq_prod_instruction_participant" in _constraint_names(ProductionPaymentOrder)
    assert "uq_prod_approval_decision" in _constraint_names(ProductionApproval)
    assert "uq_prod_quote_accept" in _constraint_names(ProductionFxTradeIntent)
    assert "uq_prod_return_sequence" in _constraint_names(ProductionReturnPayment)
    assert "uq_prod_event_aggregate_sequence" in _constraint_names(ProductionOutboxEvent)
    assert "uq_prod_gl_batch_reference" in _constraint_names(ProductionJournal)


def test_sequence_columns_are_non_nullable_and_monotonic_units():
    assert ProductionReturnPayment.__table__.c.return_sequence.nullable is False
    assert ProductionOutboxEvent.__table__.c.aggregate_sequence.nullable is False
    assert ProductionJournal.__table__.c.gl_batch_reference.nullable is False
