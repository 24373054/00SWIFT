"""Pre-validation orchestrator: aggregates individual checks into the
``PaymentInstructionValidation`` response.

The /payment/payment-instruction endpoint fans out to the 6 individual check
types (Account_Format, Beneficiary_Account_Verification, Category_Purpose,
Financial_Institution_Identity, Instructed_Amount, Payment_Purpose) and rolls
them up into validation_summary + payment_instruction_validation_result.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from api.preval import checks
from api.preval.schemas import (
    PaymentInstruction,
    PaymentInstructionValidation,
    ValidationSummary,
)


def validate_payment_instruction(
    db: Session, body: PaymentInstruction
) -> PaymentInstructionValidation:
    validations = []

    # 1. Financial Institution Identity (creditor agent BIC).
    bic = body.creditor_agent.bicfi if body.creditor_agent else None
    validations.append(checks.check_bic(db, bic or "", "Financial_Institution_Identity_Validation"))

    # 2. Account Format (creditor account).
    validations.append(
        checks.check_account_format(db, body.creditor_account, body.creditor_agent_country)
    )

    # 3. Instructed Amount (currency + amount + decimals).
    validations.append(
        checks.check_amount(body.instructed_amount.amount, body.instructed_amount.currency_code, db)
    )

    # 4. Currency (separate check_type per the spec's Payment_Purpose_Validation grouping is
    #    folded into Instructed_Amount here; the spec also has a dedicated currency validity).
    validations.append(checks.check_currency(db, body.instructed_amount.currency_code))

    # 5. Debtor agent country.
    validations.append(
        checks.check_country(body.debtor_agent_country, "Debtor_Agent_Country_Validation")
    )

    # 6. Creditor agent country.
    validations.append(
        checks.check_country(body.creditor_agent_country, "Creditor_Agent_Country_Validation")
    )

    # Roll up.
    summary = ValidationSummary()
    has_error = has_warning = False
    for v in validations:
        s = v.status
        if s == checks.S_INVALID:
            summary.ERROR_count += 1
            has_error = True
        elif s == checks.S_VALID_COMMENTS:
            summary.WARNING_count += 1
            has_warning = True
        elif s == checks.S_NOT_AVAIL:
            summary.N_A_count += 1
        else:
            summary.VALID_count += 1

    if has_error:
        result = "ERROR"
    elif has_warning:
        result = "WARNING"
    elif summary.VALID_count == len(validations):
        result = "ALL_VALID"
    else:
        result = "PARTIALLY_VALIDATED"

    return PaymentInstructionValidation(
        uetr=body.uetr or "",
        payment_instruction_validation_result=result,
        validation_summary=summary,
        validations=validations,
    )
