"""Pydantic schemas for the e-CNY API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WalletOpenRequest(BaseModel):
    tier: int = Field(3, ge=1, le=3, description="1=strong KYC/large, 2=medium, 3=small anonymous")
    operator_account_id: str = Field(..., description="Operator ledger account id")
    holder_name: Optional[str] = None
    holder_id_type: Optional[str] = None
    holder_id_hash: Optional[str] = None
    holder_country: str = "CN"


class WalletResponse(BaseModel):
    wallet_id: str
    tier: int
    balance: int
    status: str
    holder_id: Optional[str] = None
    operator_id: Optional[int] = None
    ledger_account_id: str


class TransferRequest(BaseModel):
    from_wallet_id: str
    to_wallet_id: str
    amount_fen: int = Field(..., gt=0, description="Amount in fen (1 CNY = 100 fen)")
    memo: Optional[Dict[str, Any]] = None


class IssuanceRequest(BaseModel):
    operator_account_id: str
    amount_fen: int = Field(..., gt=0)
    action: str = Field("mint", pattern="^(mint|burn|issue_to_wallet|redeem_from_wallet)$")
    wallet_id: Optional[str] = None  # required for issue_to_wallet / redeem_from_wallet


class CrossBorderRequest(BaseModel):
    from_wallet_id: str
    to_account_id: str
    amount_fen: int = Field(..., gt=0)
    target_currency: str
    channel: Optional[str] = Field(None, description="mbridge | cips; auto if omitted")
    counterparty: Optional[str] = None


class BridgeTxResponse(BaseModel):
    uetr: str
    channel_id: str
    from_currency: str
    from_amount: int
    to_currency: str
    to_amount: int
    fx_rate: Optional[str] = None
    status: str
    counterparty_ref: Optional[str] = None


class LedgerTransactionResponse(BaseModel):
    tx_id: str
    tx_type: str
    status: str
    amount: int
    currency: str
    from_account: Optional[str] = None
    to_account: Optional[str] = None
    uetr: Optional[str] = None
    memo: Dict[str, Any] = {}
    created_at: str
    settled_at: Optional[str] = None


class ComplianceReportResponse(BaseModel):
    report_id: str
    tx_id: Optional[str] = None
    report_type: str
    amount: int
    currency: str
    threshold: Optional[int] = None
    details: Dict[str, Any] = {}
    created_at: str
