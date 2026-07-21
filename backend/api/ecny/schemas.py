"""Pydantic schemas for the e-CNY API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class WalletOpenRequest(BaseModel):
    tier: int = Field(3, ge=1, le=3, description="1=strong KYC/large, 2=medium, 3=small anonymous")
    operator_account_id: str = Field(..., description="Operator ledger account id")
    holder_name: str | None = None
    holder_id_type: str | None = None
    holder_id_hash: str | None = None
    holder_country: str = "CN"


class WalletResponse(BaseModel):
    wallet_id: str
    tier: int
    balance: int
    status: str
    holder_id: str | None = None
    operator_id: int | None = None
    ledger_account_id: str


class TransferRequest(BaseModel):
    from_wallet_id: str
    to_wallet_id: str
    amount_fen: int = Field(..., gt=0, description="Amount in fen (1 CNY = 100 fen)")
    memo: dict[str, Any] | None = None


class IssuanceRequest(BaseModel):
    operator_account_id: str
    amount_fen: int = Field(..., gt=0)
    action: str = Field("mint", pattern="^(mint|burn|issue_to_wallet|redeem_from_wallet)$")
    wallet_id: str | None = None  # required for issue_to_wallet / redeem_from_wallet


class CrossBorderRequest(BaseModel):
    from_wallet_id: str
    to_account_id: str
    amount_fen: int = Field(..., gt=0)
    target_currency: str = Field(..., min_length=3, max_length=3)
    channel: str | None = Field(
        None, pattern="^(mbridge|cips)$", description="mbridge | cips; auto if omitted"
    )
    counterparty: str | None = None

    @field_validator("target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("target_currency must be an ISO alphabetic code")
        return value.upper()


class BridgeTxResponse(BaseModel):
    uetr: str
    channel_id: str
    from_currency: str
    from_amount: int
    to_currency: str
    to_amount: int
    fx_rate: str | None = None
    status: str
    counterparty_ref: str | None = None


class LedgerTransactionResponse(BaseModel):
    tx_id: str
    tx_type: str
    status: str
    amount: int
    currency: str
    from_account: str | None = None
    to_account: str | None = None
    uetr: str | None = None
    memo: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    settled_at: str | None = None


class ComplianceReportResponse(BaseModel):
    report_id: str
    tx_id: str | None = None
    report_type: str
    amount: int
    currency: str
    threshold: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str
