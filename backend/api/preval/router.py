"""Pre-validation router — mounted at /swift-preval/v2.

All endpoints require:
* ``Authorization: Bearer`` with ``swift.preval`` scope.
* ``x-bic`` header (lowercase, regex-validated) — enforced via require_x_bic.
* ``X-SWIFT-Signature`` on POST (non-repudiation).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.preval import checks, orchestrator
from api.preval.schemas import (
    AccountFormatRequest,
    AmountValidationRequest,
    FiIdentityRequest,
    PaymentInstruction,
    PaymentInstructionValidation,
)
from auth.dependencies import get_cred, require_scopes, require_signature, require_x_bic
from database import get_db

router = APIRouter(
    prefix="/swift-preval/v2",
    tags=["Pre-validation"],
    dependencies=[
        Depends(get_cred),
        Depends(require_scopes("swift.preval")),
        Depends(require_x_bic),
    ],
)


@router.post("/payment/payment-instruction", response_model=PaymentInstructionValidation)
def validate_payment_instruction(
    body: PaymentInstruction,
    _sig=Depends(require_signature),
    db: Session = Depends(get_db),
):
    """Contextual multi-element validation orchestrating the individual checks."""
    return orchestrator.validate_payment_instruction(db, body)


@router.post("/payment/financial-institution-identity")
def validate_fi_identity(
    body: FiIdentityRequest,
    _sig=Depends(require_signature),
    db: Session = Depends(get_db),
):
    bic = body.financial_institution_identification
    return checks.check_bic(db, bic, "Financial_Institution_Identity_Validation")


@router.post("/payment/account-format")
def validate_account_format(
    body: AccountFormatRequest,
    _sig=Depends(require_signature),
    db: Session = Depends(get_db),
):
    return checks.check_account_format(db, body.account_identification, body.country_code)


@router.post("/payment/amount")
def validate_amount(
    body: AmountValidationRequest,
    _sig=Depends(require_signature),
    db: Session = Depends(get_db),
):
    return checks.check_amount(body.amount, body.currency_code, db)
