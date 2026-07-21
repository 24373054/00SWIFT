"""Pre-validation individual check functions.

Each check returns a ``ValidationCheck`` (status + reason codes). Checks call
the SwiftRef repository to validate BIC/IBAN/currency/country against the
reference directory.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from api.preval.schemas import ValidationCheck, ValidationReason
from api.swiftref import repository as swiftref
from core.bic import validate_bic
from core.errors import SwiftRefException
from core.iban import validate_iban

# Status codes (from the swagger).
S_VALID = "FVAL_valid"
S_INVALID = "IVAL_invalid"
S_NOT_AVAIL = "NAVL_not_available"
S_VALID_COMMENTS = "CVAL_valid_with_comments"

# Reason codes.
R_VALID_BIC = "VBIC_valid_bic"
R_INVALID_BIC = "IBIC_invalid_bic"
R_VALID_IBAN = "VIBN_valid_iban"
R_INVALID_IBAN = "IIBN_invalid_iban"
R_VALID_CCY = "VCUC_valid_currency_code"
R_INVALID_CCY = "ICCY_invalid_currency_code"
R_VALID_COUNTRY = "VCNT_valid_country"
R_INVALID_COUNTRY = "ICTY_invalid_country"
R_VALID_AMOUNT = "VAMT_valid_amount"
R_INVALID_AMOUNT = "IAMT_invalid_amount"
R_DECIMALS_MATCH = "DBCD_amount_decimals_match_currency_decimals"
R_DECIMALS_MISMATCH = "DACD_amount_decimals_do_not_match_currency_decimals"


def check_bic(db: Session, bic: str, check_type: str) -> ValidationCheck:
    """Validate a BICFI against the SwiftRef directory."""
    if not bic or not validate_bic(bic, mode="data"):
        return ValidationCheck(
            check_type=check_type,
            validated_by="SWIFT_CENTRALLY",
            status=S_INVALID,
            reason=[ValidationReason(code=R_INVALID_BIC)],
        )
    try:
        swiftref.lookup_bic_validity(db, bic)
        return ValidationCheck(
            check_type=check_type,
            validated_by="SWIFT_CENTRALLY",
            status=S_VALID,
            reason=[ValidationReason(code=R_VALID_BIC)],
        )
    except SwiftRefException:
        return ValidationCheck(
            check_type=check_type,
            validated_by="SWIFT_CENTRALLY",
            status=S_INVALID,
            reason=[ValidationReason(code=R_INVALID_BIC)],
        )


def check_account_format(db: Session, account: str, country: str) -> ValidationCheck:
    """Validate the creditor account (treated as IBAN if it looks like one)."""
    acct = account.upper().replace(" ", "")
    if len(acct) >= 4 and acct[:2].isalpha() and acct[2:4].isdigit():
        # Looks like an IBAN — validate structurally.
        if validate_iban(acct):
            return ValidationCheck(
                check_type="Account_Format_Validation",
                validated_by="SWIFT_CENTRALLY",
                status=S_VALID,
                reason=[ValidationReason(code=R_VALID_IBAN)],
            )
        return ValidationCheck(
            check_type="Account_Format_Validation",
            validated_by="SWIFT_CENTRALLY",
            status=S_INVALID,
            reason=[ValidationReason(code=R_INVALID_IBAN)],
        )
    # Domestic account number — mark not available (no domestic directory).
    return ValidationCheck(
        check_type="Account_Format_Validation",
        validated_by="SWIFT_CENTRALLY",
        status=S_NOT_AVAIL,
        reason=[ValidationReason(code="NAVL_not_available")],
    )


def check_currency(db: Session, currency: str) -> ValidationCheck:
    try:
        swiftref.lookup_currency_validity(db, currency)
        return ValidationCheck(
            check_type="Instructed_Amount_Validation",
            validated_by="SWIFT_CENTRALLY",
            status=S_VALID,
            reason=[ValidationReason(code=R_VALID_CCY)],
        )
    except SwiftRefException:
        return ValidationCheck(
            check_type="Instructed_Amount_Validation",
            validated_by="SWIFT_CENTRALLY",
            status=S_INVALID,
            reason=[ValidationReason(code=R_INVALID_CCY)],
        )


def check_amount(amount: str, currency: str, db: Session) -> ValidationCheck:
    """Validate amount format + decimal places match the currency's minor_unit."""
    reasons: list[ValidationReason] = []
    status = S_VALID
    try:
        amt = Decimal(str(amount))
        if not amt.is_finite() or amt <= 0:
            reasons.append(ValidationReason(code=R_INVALID_AMOUNT))
            status = S_INVALID
    except (InvalidOperation, ValueError, TypeError):
        reasons.append(ValidationReason(code=R_INVALID_AMOUNT))
        return ValidationCheck(
            check_type="Instructed_Amount_Validation",
            validated_by="SWIFT_CENTRALLY",
            status=S_INVALID,
            reason=reasons,
        )
    # Check decimals against currency minor_unit.
    try:
        details = swiftref.lookup_currency_details(db, currency)
        minor = details.get("minor_unit")
        if minor is not None:
            decimals = len(amount.split(".")[-1]) if "." in amount else 0
            if decimals == minor:
                reasons.append(ValidationReason(code=R_DECIMALS_MATCH))
            else:
                reasons.append(ValidationReason(code=R_DECIMALS_MISMATCH))
                if status == S_VALID:
                    status = S_VALID_COMMENTS
    except SwiftRefException:
        # Currency validity is reported by ``check_currency``; keep this check focused on amount.
        return ValidationCheck(
            check_type="Instructed_Amount_Validation",
            validated_by="SWIFT_CENTRALLY",
            status=status,
            reason=reasons,
        )
    return ValidationCheck(
        check_type="Instructed_Amount_Validation",
        validated_by="SWIFT_CENTRALLY",
        status=status,
        reason=reasons,
    )


def check_country(country: str, check_type: str) -> ValidationCheck:
    """Validate an ISO 3166 country code (structural — 2 uppercase letters)."""
    if country and len(country) == 2 and country.isalpha() and country.isupper():
        return ValidationCheck(
            check_type=check_type,
            validated_by="SWIFT_CENTRALLY",
            status=S_VALID,
            reason=[ValidationReason(code=R_VALID_COUNTRY)],
        )
    return ValidationCheck(
        check_type=check_type,
        validated_by="SWIFT_CENTRALLY",
        status=S_INVALID,
        reason=[ValidationReason(code=R_INVALID_COUNTRY)],
    )
