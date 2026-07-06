"""ISO 20022 e-CNY message builders.

Extends the SWIFT pacs.008/pacs.002 framework with e-CNY-specific fields
(wallet id, digital-currency purpose) and adds e-CNY-native messages
(issuance, cross-border bridge). Reuses the escape-safe _esc helper from
iso20022.builder to prevent XML injection from user-controlled fields.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, Optional

from iso20022.builder import _esc, _now_iso  # reuse escape + timestamp helpers
from iso20022.uetr import generate_uetr


def build_pacs008_ecny(*, debtor_wallet: str, creditor_wallet: str,
                       amount_fen: int, currency: str = "CNY",
                       debtor_name: Optional[str] = None,
                       creditor_name: Optional[str] = None,
                       uetr: Optional[str] = None,
                       purpose: str = "DigitalCurrencyTransfer") -> str:
    """pacs.008 extended for e-CNY. Adds <Purp> digital-currency tag and
    wallet identifiers in the debtor/creditor agent blocks. Compatible with
    the SWIFT pacs.008 structure (used when bridging to traditional rails).
    """
    if amount_fen <= 0:
        raise ValueError("amount must be positive")
    uetr = uetr or generate_uetr()
    amt = f"{amount_fen / 100:.2f}"  # fen -> yuan, 2 decimals
    now = _now_iso()
    instr_id = f"ECH{uuid.uuid4().hex[:16].upper()}"
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.10">\n'
        f'  <FIToFIPmtCdtTrf>\n'
        f'    <GrpHdr><MsgId>{_esc(instr_id)}</MsgId><CreDtTm>{now}</CreDtTm>'
        f'<NbOfTxs>1</NbOfTxs><SttlmMtd>INDM</SttlmMtd></GrpHdr>\n'
        f'    <CdtTrfTxInf>\n'
        f'      <PmtId><InstrId>{_esc(instr_id)}</InstrId><EndToEndId>{_esc(instr_id)}</EndToEndId>'
        f'<UETR>{_esc(uetr)}</UETR></PmtId>\n'
        f'      <Purp><Prtry>{_esc(purpose)}</Prtry></Purp>\n'
        f'      <IntrBkSttlmAmt Ccy="{_esc(currency)}">{amt}</IntrBkSttlmAmt>\n'
        f'      <Dbtr>{("<Nm>" + _esc(debtor_name) + "</Nm>") if debtor_name else ""}'
        f'<Id><PrtryId><Id>{_esc(debtor_wallet)}</Id></PrtryId></Id></Dbtr>\n'
        f'      <Cdtr>{("<Nm>" + _esc(creditor_name) + "</Nm>") if creditor_name else ""}'
        f'<Id><PrtryId><Id>{_esc(creditor_wallet)}</Id></PrtryId></Id></Cdtr>\n'
        f'    </CdtTrfTxInf>\n'
        f'  </FIToFIPmtCdtTrf>\n'
        f'</Document>'
    )


def build_pacs002_ecny(*, uetr: str, tx_status: str, amount_fen: int,
                       currency: str = "CNY",
                       reason: Optional[str] = None) -> str:
    """pacs.002 status report with ledger settlement confirmation."""
    amt = f"{amount_fen / 100:.2f}"
    now = _now_iso()
    reason_xml = f'<RsnInf><Rsn><Prtry>{_esc(reason)}</Prtry></Rsn></RsnInf>' if reason else ''
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.002.001.12">\n'
        f'  <FIToFIPmtStsRpt>\n'
        f'    <GrpHdr><MsgId>{_esc("STS" + uuid.uuid4().hex[:16].upper())}</MsgId>'
        f'<CreDtTm>{now}</CreDtTm></GrpHdr>\n'
        f'    <TxInfAndSts><OrgnlUETR>{_esc(uetr)}</OrgnlUETR>'
        f'<TxSts>{_esc(tx_status)}</TxSts>'
        f'<OrgnlIntrBkSttlmAmt Ccy="{_esc(currency)}">{amt}</OrgnlIntrBkSttlmAmt>'
        f'{reason_xml}</TxInfAndSts>\n'
        f'  </FIToFIPmtStsRpt>\n'
        f'</Document>'
    )


def build_ecny_issuance_msg(*, operator: str, amount_fen: int,
                            currency: str = "CNY", action: str = "mint") -> str:
    """e-CNY-native issuance message (non-ISO, XML structure)."""
    amt = f"{amount_fen / 100:.2f}"
    now = _now_iso()
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<EcnyIssuance xmlns="urn:cny:ecny:issuance:1">\n'
        f'  <Action>{_esc(action)}</Action><Operator>{_esc(operator)}</Operator>\n'
        f'  <Amount Ccy="{_esc(currency)}">{amt}</Amount><CreDtTm>{now}</CreDtTm>\n'
        f'</EcnyIssuance>'
    )


def build_ecny_cross_border_msg(*, uetr: str, channel: str, from_currency: str,
                                from_amount_fen: int, to_currency: str,
                                to_amount_fen: int, fx_rate: str,
                                counterparty: Optional[str] = None) -> str:
    """e-CNY cross-border bridge message."""
    fa = f"{from_amount_fen / 100:.2f}"
    ta = f"{to_amount_fen / 100:.2f}"
    now = _now_iso()
    cp = f'<Counterparty>{_esc(counterparty)}</Counterparty>' if counterparty else ''
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<EcnyCrossBorder xmlns="urn:cny:ecny:crossborder:1">\n'
        f'  <UETR>{_esc(uetr)}</UETR><Channel>{_esc(channel)}</Channel>\n'
        f'  <FromAmt Ccy="{_esc(from_currency)}">{fa}</FromAmt>\n'
        f'  <ToAmt Ccy="{_esc(to_currency)}">{ta}</ToAmt>\n'
        f'  <FxRate>{_esc(fx_rate)}</FxRate>{cp}<CreDtTm>{now}</CreDtTm>\n'
        f'</EcnyCrossBorder>'
    )
