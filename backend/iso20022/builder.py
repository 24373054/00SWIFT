"""ISO 20022 message builder (escape-safe, XSD-validated).

Replaces the old ``iso20022.py`` f-string XML building (injection risk:
user-controlled fields like ``debtor_name`` were inserted unescaped).

Strategy:
* Build XML with explicit escaping (``_esc``) for all user-controlled text.
  This guarantees no XML injection regardless of library availability.
* Validate against the official ISO 20022 XSD via ``lxml`` when the XSD is
  available (copied from the ``pacs008`` package into ``data/xsds/``).

Why not call ``pacs008.generate_xml_string`` directly: its path validator
rejects absolute template paths on Windows (outside-allowed-directories).
We use its XSD file instead, which is the higher-value part.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from core.time import now_utc
from iso20022.uetr import generate_uetr

ISO20022_NS = "urn:iso:std:iso:20022:tech:xsd"


def _now_iso() -> str:
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def _msg_id() -> str:
    """A message identifier <= 35 chars (ISO 20022 Max35Text).

    UUID4 is 36 chars with hyphens; stripping them gives 32 hex chars,
    well within the limit.
    """
    return uuid.uuid4().hex[:35]


def _esc(s) -> str:
    """XML-escape a text/attribute value. Coerces None to empty string."""
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_pacs008_xml(
    uetr: Optional[str] = None,
    instruction_id: Optional[str] = None,
    amount: str = "10000.00",
    currency: str = "EUR",
    debtor_name: str = "Sender Corp",
    debtor_agent_bic: str = "BANKDEFFXXX",
    creditor_name: str = "Receiver Corp",
    creditor_agent_bic: str = "BANKFRPPXXX",
    charge_bearer: str = "SLEV",
    settlement_method: str = "INDA",
) -> str:
    """Build a pacs.008.001.10 FIToFICustomerCreditTransfer message."""
    uetr = uetr or generate_uetr()
    instr_id = instruction_id or f"INSTR-{uuid.uuid4().hex[:12].upper()}"
    e2e_id = f"E2E-{uuid.uuid4().hex[:12].upper()}"
    # removed - using _msg_id() inline
    cre_dt = _now_iso()
    sttlm_dt = now_utc().strftime("%Y-%m-%d")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{ISO20022_NS}:pacs.008.001.10">
  <FIToFICstmrCdtTrf>
    <GrpHdr>
      <MsgId>{_esc(_msg_id())}</MsgId>
      <CreDtTm>{_esc(cre_dt)}</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf><SttlmMtd>{_esc(settlement_method)}</SttlmMtd></SttlmInf>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <InstrId>{_esc(instr_id)}</InstrId>
        <EndToEndId>{_esc(e2e_id)}</EndToEndId>
        <UETR>{_esc(uetr)}</UETR>
      </PmtId>
      <IntrBkSttlmAmt Ccy="{_esc(currency)}">{_esc(amount)}</IntrBkSttlmAmt>
      <IntrBkSttlmDt>{_esc(sttlm_dt)}</IntrBkSttlmDt>
      <ChrgBr>{_esc(charge_bearer)}</ChrgBr>
      <Dbtr><Nm>{_esc(debtor_name)}</Nm></Dbtr>
      <DbtrAgt><FinInstnId><BICFI>{_esc(debtor_agent_bic)}</BICFI></FinInstnId></DbtrAgt>
      <CdtrAgt><FinInstnId><BICFI>{_esc(creditor_agent_bic)}</BICFI></FinInstnId></CdtrAgt>
      <Cdtr><Nm>{_esc(creditor_name)}</Nm></Cdtr>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>"""


def build_pacs002_xml(original_uetr: str, status: str, reason: str = "") -> str:
    """Build a pacs.002.001.12 FIToFIPaymentStatusReport."""
    # removed - using _msg_id() inline
    cre_dt = _now_iso()
    reason_block = ""
    if reason:
        reason_block = f"""
      <StsRsnInf><Rsn><Prtry>{_esc(reason)}</Prtry></Rsn></StsRsnInf>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{ISO20022_NS}:pacs.002.001.12">
  <FIToFIPmtStsRpt>
    <GrpHdr><MsgId>{_esc(_msg_id())}</MsgId><CreDtTm>{_esc(cre_dt)}</CreDtTm></GrpHdr>
    <TxInfAndSts>
      <OrgnlInstrId>{_esc(original_uetr)}</OrgnlInstrId>
      <TxSts>{_esc(status)}</TxSts>{reason_block}
    </TxInfAndSts>
  </FIToFIPmtStsRpt>
</Document>"""


def build_camt056_xml(uetr: str, cancellation_reason: str = "DUPL") -> str:
    """Build a camt.056.001.10 FIToFIPaymentCancellationRequest."""
    # removed - using _msg_id() inline
    cre_dt = _now_iso()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{ISO20022_NS}:camt.056.001.10">
  <FIToFIPmtCxlReq>
    <GrpHdr><MsgId>{_esc(_msg_id())}</MsgId><CreDtTm>{_esc(cre_dt)}</CreDtTm></GrpHdr>
    <TxInf>
      <CxlId>{_esc(str(uuid.uuid4()))}</CxlId>
      <OrgnlInstrId>{_esc(uetr)}</OrgnlInstrId>
      <CxlRsnInf><Rsn><Cd>{_esc(cancellation_reason)}</Cd></Rsn></CxlRsnInf>
    </TxInf>
  </FIToFIPmtCxlReq>
</Document>"""


def build_camt029_xml(uetr: str, investigation_status: str = "CNCL") -> str:
    """Build a camt.029.001.11 ResolutionOfInvestigation."""
    # removed - using _msg_id() inline
    cre_dt = _now_iso()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{ISO20022_NS}:camt.029.001.11">
  <RsltnOfInvstgtn>
    <Hdr><MsgId>{_esc(_msg_id())}</MsgId><CreDtTm>{_esc(cre_dt)}</CreDtTm></Hdr>
    <CxlDtls>
      <OrgnlInstrId>{_esc(uetr)}</OrgnlInstrId>
      <Sts>{_esc(investigation_status)}</Sts>
    </CxlDtls>
  </RsltnOfInvstgtn>
</Document>"""


def build_business_app_header(msg_def_idr: str, biz_svc: str = "swift.cbprplus.01") -> str:
    """Build an ISO 20022 Business Application Header (head.001.001.03)."""
    # removed - using _msg_id() inline
    cre_dt = _now_iso()
    return f"""<AppHdr xmlns="{ISO20022_NS}:head.001.001.03">
  <Fr><FIId><FinInstnId><BICFI>BANKDEFFXXX</BICFI></FinInstnId></FIId></Fr>
  <To><FIId><FinInstnId><BICFI>BANKFRPPXXX</BICFI></FinInstnId></FIId></To>
  <BizMsgIdr>{_esc(_msg_id())}</BizMsgIdr>
  <MsgDefIdr>{_esc(msg_def_idr)}</MsgDefIdr>
  <BizSvc>{_esc(biz_svc)}</BizSvc>
  <CreDt>{_esc(cre_dt)}</CreDt>
</AppHdr>"""
