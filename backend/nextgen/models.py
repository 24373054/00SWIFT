"""Persistent models for standards, workflows, payment lifecycles, CIPS and CBDC research."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from database import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class StandardProfile(Base):
    __tablename__ = "ng_standard_profiles"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    version = Column(String(40), nullable=False)
    effective_from = Column(DateTime, nullable=False)
    description = Column(Text, default="")
    active = Column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("name", "version", name="uq_ng_profile_version"),)


class StandardRule(Base):
    __tablename__ = "ng_standard_rules"
    id = Column(Integer, primary_key=True)
    profile = Column(String(120), nullable=False, index=True)
    rule_id = Column(String(120), nullable=False)
    message_type = Column(String(40), nullable=False, default="*")
    path = Column(String(250), nullable=False)
    severity = Column(String(20), nullable=False, default="error")
    operator = Column(String(30), nullable=False)
    expected = Column(Text, default="")
    description = Column(Text, default="")
    __table_args__ = (UniqueConstraint("profile", "rule_id", name="uq_ng_profile_rule"),)


class IdempotencyRecord(Base):
    __tablename__ = "ng_idempotency_records"
    id = Column(Integer, primary_key=True)
    key = Column(String(200), nullable=False, unique=True, index=True)
    request_hash = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="started")
    response_status = Column(Integer)
    response_body = Column(Text)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class OutboxEvent(Base):
    __tablename__ = "ng_outbox_events"
    id = Column(Integer, primary_key=True)
    event_id = Column(String(64), nullable=False, unique=True, index=True)
    topic = Column(String(120), nullable=False, index=True)
    aggregate_id = Column(String(120), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)
    attempts = Column(Integer, default=0, nullable=False)
    available_at = Column(DateTime, default=utcnow, nullable=False)
    last_error = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class WorkflowInstance(Base):
    __tablename__ = "ng_workflows"
    id = Column(Integer, primary_key=True)
    workflow_id = Column(String(64), nullable=False, unique=True, index=True)
    kind = Column(String(80), nullable=False)
    state = Column(String(60), nullable=False)
    payload = Column(Text, default="{}", nullable=False)
    version = Column(Integer, default=1, nullable=False)
    locked_until = Column(DateTime)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class TransactionCopy(Base):
    __tablename__ = "ng_transaction_copies"
    id = Column(Integer, primary_key=True)
    uetr = Column(String(36), nullable=False, index=True)
    message_id = Column(String(120), nullable=False, unique=True)
    message_type = Column(String(40), nullable=False)
    payload = Column(Text, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    previous_hash = Column(String(64))
    source_party = Column(String(80), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class FieldLineage(Base):
    __tablename__ = "ng_field_lineage"
    id = Column(Integer, primary_key=True)
    uetr = Column(String(36), nullable=False, index=True)
    message_id = Column(String(120), nullable=False, index=True)
    path = Column(String(250), nullable=False)
    source_party = Column(String(80), nullable=False)
    value_hash = Column(String(64), nullable=False)
    reason = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow, nullable=False)


class PaymentLifecycle(Base):
    __tablename__ = "ng_payment_lifecycles"
    id = Column(Integer, primary_key=True)
    uetr = Column(String(36), nullable=False, unique=True, index=True)
    status = Column(String(30), nullable=False, default="RECEIVED")
    scenario = Column(String(30), nullable=False, default="CCT")
    original_uetr = Column(String(36))
    deadline_at = Column(DateTime)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class PaymentCase(Base):
    __tablename__ = "ng_payment_cases"
    id = Column(Integer, primary_key=True)
    case_id = Column(String(64), nullable=False, unique=True, index=True)
    uetr = Column(String(36), nullable=False, index=True)
    case_type = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False, default="OPEN")
    owner = Column(String(80), nullable=False)
    details = Column(Text, default="{}", nullable=False)
    deadline_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DataQualityMetric(Base):
    __tablename__ = "ng_data_quality_metrics"
    id = Column(Integer, primary_key=True)
    entity_type = Column(String(40), nullable=False)
    entity_id = Column(String(120), nullable=False, index=True)
    profile = Column(String(120), nullable=False)
    completeness = Column(Float, nullable=False)
    validity = Column(Float, nullable=False)
    consistency = Column(Float, nullable=False)
    integrity = Column(Float, nullable=False)
    details = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class CipsParticipant(Base):
    __tablename__ = "ng_cips_participants"
    id = Column(Integer, primary_key=True)
    participant_id = Column(String(40), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    participant_type = Column(String(20), nullable=False)
    bic = Column(String(11), index=True)
    lei = Column(String(20), index=True)
    country = Column(String(2), nullable=False)
    capabilities = Column(Text, default="[]", nullable=False)
    settlement_hours = Column(Text, default="{}", nullable=False)
    active = Column(Boolean, default=True, nullable=False)


class CipsAccount(Base):
    __tablename__ = "ng_cips_accounts"
    id = Column(Integer, primary_key=True)
    account_id = Column(String(64), nullable=False, unique=True)
    participant_id = Column(String(40), nullable=False, index=True)
    balance = Column(Integer, default=0, nullable=False)
    reserved = Column(Integer, default=0, nullable=False)
    currency = Column(String(3), default="CNY", nullable=False)
    version = Column(Integer, default=1, nullable=False)
    __table_args__ = (CheckConstraint("balance >= 0", name="ck_ng_cips_balance"),)


class CipsSettlement(Base):
    __tablename__ = "ng_cips_settlements"
    id = Column(Integer, primary_key=True)
    settlement_id = Column(String(64), nullable=False, unique=True, index=True)
    uetr = Column(String(36), nullable=False, index=True)
    mode = Column(String(10), nullable=False)
    debtor_participant = Column(String(40), nullable=False)
    creditor_participant = Column(String(40), nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String(3), default="CNY", nullable=False)
    priority = Column(Integer, default=5, nullable=False)
    status = Column(String(30), default="QUEUED", nullable=False)
    batch_id = Column(String(64), index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    settled_at = Column(DateTime)
    __table_args__ = (CheckConstraint("amount > 0", name="ck_ng_cips_amount"),)


class PaymentLensEvent(Base):
    __tablename__ = "ng_payment_lens_events"
    id = Column(Integer, primary_key=True)
    uetr = Column(String(36), nullable=False, index=True)
    system = Column(String(30), nullable=False)
    event_type = Column(String(60), nullable=False)
    status = Column(String(40), nullable=False)
    details = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class EcnyOperator(Base):
    __tablename__ = "ng_ecny_operators"
    id = Column(Integer, primary_key=True)
    operator_id = Column(String(40), nullable=False, unique=True)
    name = Column(String(160), nullable=False)
    issuance_limit = Column(Integer, default=0, nullable=False)
    issued_amount = Column(Integer, default=0, nullable=False)
    reserve_amount = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="active", nullable=False)


class OfflineVoucher(Base):
    __tablename__ = "ng_offline_vouchers"
    id = Column(Integer, primary_key=True)
    voucher_id = Column(String(64), nullable=False, unique=True, index=True)
    wallet_id = Column(String(64), nullable=False, index=True)
    device_id = Column(String(120), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    nonce = Column(String(120), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String(20), default="issued", nullable=False)
    redeemed_by = Column(String(120))
    created_at = Column(DateTime, default=utcnow, nullable=False)
    __table_args__ = (CheckConstraint("amount > 0", name="ck_ng_offline_amount"),)


class ProgrammableInstrument(Base):
    __tablename__ = "ng_programmable_instruments"
    id = Column(Integer, primary_key=True)
    instrument_id = Column(String(64), nullable=False, unique=True)
    template = Column(String(40), nullable=False)
    owner_wallet = Column(String(64), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    conditions = Column(Text, nullable=False)
    status = Column(String(20), default="active", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class CbdcJurisdiction(Base):
    __tablename__ = "ng_cbdc_jurisdictions"
    id = Column(Integer, primary_key=True)
    code = Column(String(12), nullable=False, unique=True)
    currency = Column(String(3), nullable=False)
    central_bank = Column(String(160), nullable=False)
    policy = Column(Text, default="{}", nullable=False)
    data_residency = Column(String(80), nullable=False)
    active = Column(Boolean, default=True, nullable=False)


class CbdcNode(Base):
    __tablename__ = "ng_cbdc_nodes"
    id = Column(Integer, primary_key=True)
    node_id = Column(String(64), nullable=False, unique=True)
    jurisdiction = Column(String(12), nullable=False, index=True)
    participant = Column(String(160), nullable=False)
    role = Column(String(30), nullable=False)
    status = Column(String(20), default="active", nullable=False)


class FxQuote(Base):
    __tablename__ = "ng_fx_quotes"
    id = Column(Integer, primary_key=True)
    quote_id = Column(String(64), nullable=False, unique=True)
    provider = Column(String(80), nullable=False)
    base_currency = Column(String(3), nullable=False)
    quote_currency = Column(String(3), nullable=False)
    rate = Column(String(40), nullable=False)
    fee = Column(Integer, default=0, nullable=False)
    max_amount = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String(20), default="active", nullable=False)


class PvpSettlement(Base):
    __tablename__ = "ng_pvp_settlements"
    id = Column(Integer, primary_key=True)
    pvp_id = Column(String(64), nullable=False, unique=True)
    quote_id = Column(String(64), nullable=False, index=True)
    debit_leg = Column(Text, nullable=False)
    credit_leg = Column(Text, nullable=False)
    state = Column(String(30), default="CREATED", nullable=False)
    version = Column(Integer, default=1, nullable=False)
    failure_reason = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class LeaseLock(Base):
    __tablename__ = "ng_lease_locks"
    id = Column(Integer, primary_key=True)
    resource = Column(String(160), nullable=False, unique=True)
    owner = Column(String(120), nullable=False)
    token = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)


class PolicyDecision(Base):
    __tablename__ = "ng_policy_decisions"
    id = Column(Integer, primary_key=True)
    decision_id = Column(String(64), nullable=False, unique=True)
    subject = Column(String(120), nullable=False)
    action = Column(String(120), nullable=False)
    resource = Column(String(160), nullable=False)
    result = Column(String(20), nullable=False)
    reasons = Column(Text, default="[]", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class RuntimeAuditEvent(Base):
    __tablename__ = "ng_runtime_audit_events"
    id = Column(Integer, primary_key=True)
    trace_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(80), nullable=False)
    aggregate_id = Column(String(120), nullable=False, index=True)
    payload_hash = Column(String(64), nullable=False)
    previous_hash = Column(String(64))
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
