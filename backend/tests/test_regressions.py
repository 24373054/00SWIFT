"""Regression tests for defects found during repository audit."""

from api.gpi.service import confirm_status
from api.preval.checks import S_INVALID, check_amount
from database import PaymentState


def test_prevalidation_rejects_nonfinite_amount(db):
    assert check_amount("NaN", "CNY", db).status == S_INVALID
    assert check_amount("Infinity", "CNY", db).status == S_INVALID


def test_gpi_invalid_transition_returns_business_error_not_name_error(db):
    payment = PaymentState(uetr="00000000-0000-4000-8000-000000000001", transaction_status="PDNG")
    db.add(payment)
    db.commit()
    confirm_status(db, payment.uetr, {"transaction_status": "ACCP"})
    assert payment.transaction_status == "ACCP"
