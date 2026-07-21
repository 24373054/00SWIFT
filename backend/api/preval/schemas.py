"""Pre-validation API (v2) schemas.

Aligned with
``research/api-sample-code/dotnet/PreVal/PreVal/SWIFT-API-payment-validation-2.4.1-resolved-2.yaml``.

Key difference from the old prototype: validation results use the
``payment_instruction_validation_result`` enum (ERROR|WARNING|ALL_VALID|
PARTIALLY_VALIDATED|N/A) and typed ``validations[]`` — NEVER booleans or
``PASS``/``FAIL`` (user decision 1).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---- request schemas (subset, the fields the mock validates) ----


class InstructedAmount(BaseModel):
    currency_code: str = Field(..., pattern=r"^[A-Z]{3}$")
    amount: str


class FinancialInstitutionIdentification(BaseModel):
    bicfi: str | None = None
    clearing_system_member_identification: str | None = None


class PartyIdentification(BaseModel):
    name: str | None = None


class PaymentInstruction(BaseModel):
    """Body for POST /payment/payment-instruction."""

    uetr: str | None = None
    instructed_amount: InstructedAmount
    clearing_system_identification: str | None = None
    debtor_agent_country: str = Field(..., pattern=r"^[A-Z]{2}$")
    creditor_agent: FinancialInstitutionIdentification
    creditor_agent_country: str = Field(..., pattern=r"^[A-Z]{2}$")
    creditor_agent_branch_identification: str | None = None
    creditor: PartyIdentification | None = None
    creditor_account: str = Field(..., max_length=34)
    purpose_code: str | None = None
    purpose_description: str | None = None
    category_purpose_code: str | None = None


class AccountFormatRequest(BaseModel):
    account_identification: str
    country_code: str = Field(..., pattern=r"^[A-Z]{2}$")
    financial_institution_identification: str | None = None


class FiIdentityRequest(BaseModel):
    financial_institution_identification: str
    country_code: str | None = Field(None, pattern=r"^[A-Z]{2}$")


class AmountValidationRequest(BaseModel):
    amount: str
    currency_code: str = Field(..., pattern=r"^[A-Z]{3}$")
    clearing_system_identification: str | None = None


class PurposeCodeRequest(BaseModel):
    purpose_code: str
    country_code: str = Field(..., pattern=r"^[A-Z]{2}$")


# ---- response schemas ----


class ValidationReason(BaseModel):
    code: str  # e.g. ICCY_invalid_currency_code, VBIC_valid_bic
    text: str | None = None


class ValidationCheck(BaseModel):
    check_type: str  # Account_Format_Validation | Beneficiary_Account_Verification | ...
    validated_by: str = "SWIFT_CENTRALLY"  # SWIFT_CENTRALLY | CREDITOR_AGENT
    status: str  # FVAL_valid | IVAL_invalid | NAVL_not_available | ...
    reason: list[ValidationReason] = []


class ValidationSummary(BaseModel):
    ERROR_count: int = 0
    WARNING_count: int = 0
    VALID_count: int = 0
    N_A_count: int = 0
    service_error_count: int = 0


class PaymentInstructionValidation(BaseModel):
    """Response for POST /payment/payment-instruction."""

    uetr: str
    payment_instruction_validation_result: str  # ERROR|WARNING|ALL_VALID|PARTIALLY_VALIDATED|N/A
    validation_summary: ValidationSummary
    validations: list[ValidationCheck]
