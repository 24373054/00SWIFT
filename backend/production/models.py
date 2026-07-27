"""Persistent production-domain aggregates.

The production domain uses immutable facts and explicit child aggregates.  A
payment projection is derived from these rows; it is never the authority for
funds, external finality or participant identity.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy import (
    DateTime as _DateTime,
)
from sqlalchemy.orm import relationship

from database import Base


class DateTime(_DateTime):
    """UTC-aware SQLAlchemy timestamp used by every production model."""

    def __init__(self, *args, **kwargs):
        kwargs["timezone"] = True
        super().__init__(*args, **kwargs)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class ProductionTenant(Base):
    __tablename__ = "prod_tenants"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    jurisdiction = Column(String(12), nullable=False)
    data_region = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    rulebook_version = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class ProductionQualificationArtifact(Base):
    __tablename__ = "prod_qualification_artifacts"
    id = Column(Integer, primary_key=True)
    artifact_id = Column(String(100), nullable=False, unique=True, index=True)
    artifact_type = Column(String(80), nullable=False)
    environment = Column(String(20), nullable=False, index=True)
    subject = Column(String(160), nullable=False)
    issuer = Column(String(200), nullable=False)
    connector = Column(String(120), nullable=False)
    connector_version = Column(String(80), nullable=False)
    artifact_path = Column(String(500), nullable=False)
    artifact_digest = Column(String(64), nullable=False)
    signature_algorithm = Column(String(40), nullable=False)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime, nullable=False)
    document_digest = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="VERIFIED")
    verified_at = Column(DateTime, nullable=False, default=utcnow)
    verifier_version = Column(String(40), nullable=False, default="qualification-v1")
    __table_args__ = (
        UniqueConstraint(
            "environment",
            "subject",
            "connector_version",
            name="uq_prod_qualification_environment_subject_version",
        ),
        CheckConstraint(
            "status IN ('VERIFIED', 'ACTIVE', 'EXPIRED', 'REJECTED')",
            name="ck_prod_qualification_artifact_status",
        ),
    )

    def assert_active(self, now: dt.datetime | None = None) -> None:
        """Reject activation once the attested validity window has elapsed."""
        current = (now or utcnow()).astimezone(dt.UTC)
        valid_to = self.valid_to
        if valid_to.tzinfo is None:
            valid_to = valid_to.replace(tzinfo=dt.UTC)
        if self.status == "ACTIVE" and valid_to.astimezone(dt.UTC) <= current:
            raise ValueError("expired qualification artifact cannot become ACTIVE")


@event.listens_for(ProductionQualificationArtifact, "before_insert")
@event.listens_for(ProductionQualificationArtifact, "before_update")
def _validate_qualification_activation(_mapper, _connection, target) -> None:
    target.assert_active()


class ProductionQualificationDecision(Base):
    __tablename__ = "prod_qualification_decisions"
    id = Column(Integer, primary_key=True)
    decision_id = Column(String(100), nullable=False, unique=True, index=True)
    artifact_id = Column(String(100), nullable=False, index=True)
    environment = Column(String(20), nullable=False)
    outcome = Column(String(20), nullable=False)
    reason = Column(String(500), nullable=False)
    input_digest = Column(String(64), nullable=False)
    verifier_version = Column(String(40), nullable=False)
    decided_at = Column(DateTime, nullable=False, default=utcnow)
    evidence_ref = Column(String(120), nullable=True)


class ProductionParticipant(Base):
    __tablename__ = "prod_participants"
    id = Column(Integer, primary_key=True)
    participant_id = Column(String(80), nullable=False, unique=True, index=True)
    tenant_id = Column(String(80), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    participant_type = Column(String(40), nullable=False)
    jurisdiction = Column(String(12), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    rulebook_version = Column(String(80), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class ProductionEntitlement(Base):
    __tablename__ = "prod_entitlements"
    id = Column(Integer, primary_key=True)
    entitlement_id = Column(String(80), nullable=False, unique=True, index=True)
    participant_id = Column(String(80), nullable=False, index=True)
    counterparty_id = Column(String(80), nullable=False, index=True)
    direction = Column(String(12), nullable=False)
    service = Column(String(80), nullable=False)
    message_type = Column(String(80), nullable=False, default="*")
    corridor = Column(String(40), nullable=False, default="*")
    currency = Column(String(3), nullable=False, default="*")
    min_amount_minor = Column(BigInteger, nullable=False, default=0)
    max_amount_minor = Column(BigInteger, nullable=False, default=9223372036854775807)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="PENDING")
    effective_from = Column(DateTime, nullable=False, default=utcnow)
    effective_to = Column(DateTime, nullable=True)
    approved_by = Column(String(200), nullable=True)
    evidence_ref = Column(String(120), nullable=True)


class ProductionServiceIdentity(Base):
    __tablename__ = "prod_service_identities"
    id = Column(Integer, primary_key=True)
    identity_id = Column(String(80), nullable=False, unique=True, index=True)
    participant_id = Column(String(80), nullable=False, index=True)
    credential_id = Column(Integer, nullable=True, index=True)
    certificate_fingerprint = Column(String(128), nullable=True, unique=True)
    scopes = Column(Text, nullable=False, default="[]")
    environment = Column(String(20), nullable=False, default="sandbox")
    status = Column(String(20), nullable=False, default="PENDING")
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionCertificate(Base):
    __tablename__ = "prod_certificates"
    id = Column(Integer, primary_key=True)
    certificate_id = Column(String(100), nullable=False, unique=True, index=True)
    participant_id = Column(String(80), nullable=False, index=True)
    fingerprint = Column(String(128), nullable=False, unique=True)
    serial_number = Column(String(160), nullable=False, unique=True)
    issuer = Column(String(200), nullable=False)
    trust_domain = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    not_before = Column(DateTime, nullable=False)
    not_after = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionAccount(Base):
    __tablename__ = "prod_accounts"
    id = Column(Integer, primary_key=True)
    account_id = Column(String(120), nullable=False, unique=True, index=True)
    tenant_id = Column(String(80), nullable=False, index=True)
    participant_id = Column(String(80), nullable=False, index=True)
    account_type = Column(String(40), nullable=False)
    currency = Column(String(3), nullable=False)
    owner_ref = Column(String(160), nullable=False)
    external_reference = Column(String(200), nullable=True)
    status = Column(String(20), nullable=False, default="PENDING")
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionAccountOwnership(Base):
    __tablename__ = "prod_account_ownerships"
    id = Column(Integer, primary_key=True)
    ownership_id = Column(String(100), nullable=False, unique=True, index=True)
    account_id = Column(String(120), nullable=False, index=True)
    participant_id = Column(String(80), nullable=False, index=True)
    role = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    effective_from = Column(DateTime, nullable=False, default=utcnow)
    effective_to = Column(DateTime, nullable=True)
    evidence_ref = Column(String(120), nullable=True)


class ProductionLimitProfile(Base):
    __tablename__ = "prod_limit_profiles"
    id = Column(Integer, primary_key=True)
    profile_id = Column(String(100), nullable=False, unique=True, index=True)
    participant_id = Column(String(80), nullable=False, index=True)
    service = Column(String(80), nullable=False)
    corridor = Column(String(40), nullable=False, default="*")
    currency = Column(String(3), nullable=False, default="*")
    max_amount_minor = Column(BigInteger, nullable=True)
    daily_amount_minor = Column(BigInteger, nullable=True)
    max_exposure_minor = Column(BigInteger, nullable=True)
    status = Column(String(20), nullable=False, default="PENDING")
    effective_from = Column(DateTime, nullable=False, default=utcnow)
    effective_to = Column(DateTime, nullable=True)
    approved_by = Column(String(200), nullable=True)


class ProductionLimitCounter(Base):
    __tablename__ = "prod_limit_counters"
    id = Column(Integer, primary_key=True)
    counter_id = Column(String(100), nullable=False, unique=True)
    tenant_id = Column(String(80), nullable=False, index=True)
    participant_id = Column(String(80), nullable=False, index=True)
    service = Column(String(80), nullable=False)
    corridor = Column(String(40), nullable=False)
    currency = Column(String(3), nullable=False)
    business_date = Column(String(10), nullable=False)
    reserved_amount_minor = Column(BigInteger, nullable=False, default=0)
    consumed_amount_minor = Column(BigInteger, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    __table_args__ = (
        UniqueConstraint("tenant_id", "participant_id", "service", "corridor", "currency", "business_date", name="uq_prod_limit_counter_scope"),
        CheckConstraint("reserved_amount_minor >= 0 AND consumed_amount_minor >= 0", name="ck_prod_limit_counter_nonnegative"),
    )


class ProductionExposurePosition(Base):
    __tablename__ = "prod_exposure_positions"
    id = Column(Integer, primary_key=True)
    position_id = Column(String(100), nullable=False, unique=True)
    tenant_id = Column(String(80), nullable=False, index=True)
    participant_id = Column(String(80), nullable=False, index=True)
    corridor = Column(String(40), nullable=False)
    currency = Column(String(3), nullable=False)
    exposure_minor = Column(BigInteger, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    __table_args__ = (
        UniqueConstraint("tenant_id", "participant_id", "corridor", "currency", name="uq_prod_exposure_scope"),
        CheckConstraint("exposure_minor >= 0", name="ck_prod_exposure_nonnegative"),
    )


class ProductionRulebookAcceptance(Base):
    __tablename__ = "prod_rulebook_acceptances"
    id = Column(Integer, primary_key=True)
    acceptance_id = Column(String(100), nullable=False, unique=True, index=True)
    participant_id = Column(String(80), nullable=False, index=True)
    rulebook_version = Column(String(80), nullable=False)
    document_digest = Column(String(64), nullable=False)
    accepted_by = Column(String(200), nullable=False)
    signer_subject = Column(String(200), nullable=False)
    effective_from = Column(DateTime, nullable=False, default=utcnow)
    effective_to = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="PENDING")
    accepted_at = Column(DateTime, nullable=True)
    evidence_ref = Column(String(120), nullable=True)


class ProductionMandate(Base):
    __tablename__ = "prod_mandates"
    id = Column(Integer, primary_key=True)
    mandate_id = Column(String(100), nullable=False, unique=True, index=True)
    participant_id = Column(String(80), nullable=False, index=True)
    account_id = Column(String(120), nullable=False, index=True)
    debtor_ref = Column(String(160), nullable=False)
    max_amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    purpose_code = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    valid_from = Column(DateTime, nullable=False, default=utcnow)
    valid_to = Column(DateTime, nullable=True)
    evidence_ref = Column(String(120), nullable=True)


class ProductionApproval(Base):
    __tablename__ = "prod_approvals"
    id = Column(Integer, primary_key=True)
    approval_id = Column(String(100), nullable=False, unique=True, index=True)
    aggregate_type = Column(String(60), nullable=False)
    aggregate_id = Column(String(120), nullable=False, index=True)
    action = Column(String(60), nullable=False)
    maker = Column(String(200), nullable=False)
    maker_credential_id = Column(Integer, nullable=True, index=True)
    checker = Column(String(200), nullable=True)
    checker_credential_id = Column(Integer, nullable=True, index=True)
    state = Column(String(20), nullable=False, default="PENDING")
    reason = Column(String(500), nullable=False)
    evidence_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    approved_at = Column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("aggregate_type", "aggregate_id", "action", name="uq_prod_approval_decision"),)


class ProductionApprovalDecision(Base):
    __tablename__ = "prod_approval_decisions"
    id = Column(Integer, primary_key=True)
    decision_id = Column(String(100), nullable=False, unique=True)
    approval_id = Column(String(100), ForeignKey("prod_approvals.approval_id", ondelete="RESTRICT"), nullable=False, index=True)
    outcome = Column(String(20), nullable=False)
    checker = Column(String(200), nullable=False)
    checker_credential_id = Column(Integer, nullable=True, index=True)
    signature = Column(String(512), nullable=True)
    reason = Column(String(500), nullable=False)
    policy_version = Column(String(80), nullable=False)
    evidence_ref = Column(String(120), nullable=True)
    decided_at = Column(DateTime, nullable=False, default=utcnow)


@event.listens_for(ProductionApprovalDecision, "before_update")
@event.listens_for(ProductionApprovalDecision, "before_delete")
def _approval_decision_immutable(_mapper, _connection, _target) -> None:
    raise ValueError("approval decisions are append-only")


class ProductionDeliveryProfile(Base):
    __tablename__ = "prod_delivery_profiles"
    id = Column(Integer, primary_key=True)
    profile_id = Column(String(100), nullable=False, unique=True, index=True)
    version = Column(String(40), nullable=False)
    required_network_state = Column(String(40), nullable=False, default="DELIVERED")
    business_response_required = Column(Boolean, nullable=False, default=False)
    non_blocking = Column(Boolean, nullable=False, default=False)
    message_set = Column(Text, nullable=False, default="[]")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionLiabilityProfile(Base):
    __tablename__ = "prod_liability_profiles"
    id = Column(Integer, primary_key=True)
    profile_id = Column(String(100), nullable=False, unique=True, index=True)
    operator_id = Column(String(80), nullable=False, index=True)
    operator_type = Column(String(30), nullable=False)
    liability_type = Column(String(80), nullable=False)
    jurisdiction = Column(String(12), nullable=False)
    interest_bearing = Column(Boolean, nullable=False, default=False)
    deposit_insured = Column(Boolean, nullable=False, default=False)
    reserve_ratio = Column(String(40), nullable=True)
    guarantee_ratio = Column(String(40), nullable=True)
    effective_from = Column(DateTime, nullable=False, default=utcnow)
    active = Column(Boolean, nullable=False, default=True)


class ProductionFinalityProfile(Base):
    __tablename__ = "prod_finality_profiles"
    id = Column(Integer, primary_key=True)
    profile_id = Column(String(100), nullable=False, unique=True, index=True)
    connector = Column(String(100), nullable=False)
    jurisdiction = Column(String(12), nullable=False)
    accepted_event = Column(String(80), nullable=False)
    irrevocable_event = Column(String(80), nullable=False)
    final_event = Column(String(80), nullable=False)
    evidence_schema = Column(String(120), nullable=False)
    rulebook_reference = Column(String(160), nullable=True)
    active = Column(Boolean, nullable=False, default=True)


class ProductionCompletionProfile(Base):
    __tablename__ = "prod_completion_profiles"
    id = Column(Integer, primary_key=True)
    profile_id = Column(String(100), nullable=False, unique=True, index=True)
    corridor = Column(String(40), nullable=False)
    required_messages = Column(Text, nullable=False, default="[]")
    required_funding = Column(Text, nullable=False, default="[]")
    required_fx = Column(Text, nullable=False, default="[]")
    required_settlement = Column(Text, nullable=False, default="[]")
    required_credits = Column(Text, nullable=False, default="[]")
    projection_rule_version = Column(String(80), nullable=False)
    active = Column(Boolean, nullable=False, default=True)


class ProductionPaymentOrder(Base):
    __tablename__ = "prod_payment_orders"
    id = Column(Integer, primary_key=True)
    order_id = Column(String(80), nullable=False, unique=True, index=True)
    uetr = Column(String(36), nullable=False, unique=True, index=True)
    instruction_id = Column(String(200), nullable=False, index=True)
    end_to_end_id = Column(String(200), nullable=False, index=True)
    transaction_id = Column(String(200), nullable=False, index=True)
    tenant_id = Column(String(80), ForeignKey("prod_tenants.tenant_id", ondelete="RESTRICT"), nullable=False, index=True)
    initiator_participant = Column(String(80), ForeignKey("prod_participants.participant_id", ondelete="RESTRICT"), nullable=False, index=True)
    corridor = Column(String(40), nullable=False)
    debtor_party_ref = Column(String(160), nullable=False)
    debtor_account_ref = Column(String(160), nullable=False)
    creditor_party_ref = Column(String(160), nullable=False)
    creditor_account_ref = Column(String(160), nullable=False)
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    settlement_currency = Column(String(3), nullable=False)
    purpose_code = Column(String(40), nullable=False)
    payload = Column(Text, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    orchestration_state = Column(String(60), nullable=False, default="RECEIVED")
    authorization_state = Column(String(40), nullable=False, default="PENDING")
    compliance_state = Column(String(40), nullable=False, default="PENDING")
    funding_state = Column(String(40), nullable=False, default="PENDING")
    fx_state = Column(String(40), nullable=False, default="NOT_REQUIRED")
    message_delivery_state = Column(String(40), nullable=False, default="PENDING")
    value_settlement_state = Column(String(40), nullable=False, default="PENDING")
    beneficiary_state = Column(String(40), nullable=False, default="PENDING")
    reconciliation_state = Column(String(40), nullable=False, default="PENDING")
    customer_outcome = Column(String(40), nullable=True)
    completion_profile_id = Column(String(100), nullable=False)
    projection_rule_version = Column(String(80), nullable=False)
    limit_reservation_id = Column(String(100), nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_prod_payment_amount"),
        UniqueConstraint("initiator_participant", "instruction_id", name="uq_prod_instruction_participant"),
        UniqueConstraint("tenant_id", "end_to_end_id", name="uq_prod_end_to_end_tenant"),
        UniqueConstraint("tenant_id", "transaction_id", name="uq_prod_transaction_tenant"),
    )
    facts = relationship("ProductionPaymentFact", primaryjoin="ProductionPaymentOrder.order_id == foreign(ProductionPaymentFact.order_id)", viewonly=True)


class ProductionPaymentFact(Base):
    __tablename__ = "prod_payment_facts"
    id = Column(Integer, primary_key=True)
    fact_id = Column(String(80), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    fact_type = Column(String(60), nullable=False, index=True)
    state = Column(String(60), nullable=False)
    reference = Column(String(160), nullable=True, index=True)
    supersedes_fact_id = Column(String(80), ForeignKey("prod_payment_facts.fact_id", ondelete="RESTRICT"), nullable=True, index=True)
    payload = Column(Text, nullable=False, default="{}")
    occurred_at = Column(DateTime, nullable=False, default=utcnow)
    version = Column(Integer, nullable=False, default=1)
    fact_sequence = Column(Integer, nullable=False, default=1)
    input_hash = Column(String(64), nullable=False, default="")
    output_hash = Column(String(64), nullable=False, default="")
    rule_version = Column(String(80), nullable=False, default="unspecified")
    evidence_ref = Column(String(120), nullable=True)
    actor = Column(String(160), nullable=False, default="system")
    __table_args__ = (UniqueConstraint("order_id", "fact_type", "reference", "fact_sequence", name="uq_prod_fact_sequence"),)


class ProductionAuthorizationDecision(Base):
    __tablename__ = "prod_authorization_decisions"
    id = Column(Integer, primary_key=True)
    decision_id = Column(String(80), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    outcome = Column(String(30), nullable=False)
    payment_hash = Column(String(64), nullable=False)
    mandate_ref = Column(String(160), nullable=True)
    approval_ref = Column(String(160), nullable=True)
    input_hash = Column(String(64), nullable=False)
    evaluated_at = Column(DateTime, nullable=False, default=utcnow)
    valid_from = Column(DateTime, nullable=False, default=utcnow)
    valid_to = Column(DateTime, nullable=True)
    rule_version = Column(String(80), nullable=False)
    evidence_ref = Column(String(120), nullable=True)


class ProductionComplianceDecision(Base):
    __tablename__ = "prod_compliance_decisions"
    id = Column(Integer, primary_key=True)
    decision_id = Column(String(80), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    outcome = Column(String(30), nullable=False)
    input_hash = Column(String(64), nullable=False)
    rule_version = Column(String(80), nullable=False)
    list_version = Column(String(80), nullable=True)
    case_id = Column(String(80), nullable=True)
    evaluated_at = Column(DateTime, nullable=False, default=utcnow)
    valid_to = Column(DateTime, nullable=True)
    evidence_ref = Column(String(120), nullable=True)


class ProductionFinalityDecision(Base):
    __tablename__ = "prod_finality_decisions"
    id = Column(Integer, primary_key=True)
    decision_id = Column(String(80), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    outcome = Column(String(30), nullable=False)
    input_hash = Column(String(64), nullable=False)
    rule_version = Column(String(80), nullable=False)
    evidence_ref = Column(String(120), nullable=True)
    evaluated_at = Column(DateTime, nullable=False, default=utcnow)


@event.listens_for(ProductionAuthorizationDecision, "before_update")
@event.listens_for(ProductionAuthorizationDecision, "before_delete")
def _authorization_decision_immutable(_mapper, _connection, _target) -> None:
    raise ValueError("authorization decisions are append-only")


@event.listens_for(ProductionComplianceDecision, "before_update")
@event.listens_for(ProductionComplianceDecision, "before_delete")
def _compliance_decision_immutable(_mapper, _connection, _target) -> None:
    raise ValueError("compliance decisions are append-only")


@event.listens_for(ProductionFinalityDecision, "before_update")
@event.listens_for(ProductionFinalityDecision, "before_delete")
def _finality_decision_immutable(_mapper, _connection, _target) -> None:
    raise ValueError("finality decisions are append-only")


class ProductionFundingReservation(Base):
    __tablename__ = "prod_funding_reservations"
    id = Column(Integer, primary_key=True)
    reservation_id = Column(String(80), nullable=False, unique=True, index=True)
    reservation_intent_id = Column(String(80), nullable=False, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    funding_reference = Column(String(160), nullable=False)
    currency = Column(String(3), nullable=False)
    amount_minor = Column(BigInteger, nullable=False)
    state = Column(String(30), nullable=False, default="PENDING")
    external_reference = Column(String(160), nullable=True)
    evidence_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("reservation_intent_id", "funding_reference", name="uq_prod_reservation_intent"),)


class ProductionFxQuote(Base):
    __tablename__ = "prod_fx_quotes"
    id = Column(Integer, primary_key=True)
    quote_id = Column(String(80), nullable=False, unique=True, index=True)
    participant_id = Column(String(80), nullable=False, index=True)
    corridor = Column(String(40), nullable=False)
    provider = Column(String(100), nullable=False)
    base_currency = Column(String(3), nullable=False)
    quote_currency = Column(String(3), nullable=False)
    base_amount_minor = Column(BigInteger, nullable=False)
    quote_amount_minor = Column(BigInteger, nullable=False)
    rate = Column(String(40), nullable=False)
    fee_minor = Column(BigInteger, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String(30), nullable=False, default="QUOTED")
    evidence_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionFxTradeIntent(Base):
    __tablename__ = "prod_fx_trade_intents"
    id = Column(Integer, primary_key=True)
    trade_intent_id = Column(String(80), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    quote_id = Column(String(80), nullable=False, index=True)
    state = Column(String(30), nullable=False, default="PREPARING")
    idempotency_context = Column(String(160), nullable=False, unique=True)
    reservation_ids = Column(Text, nullable=False, default="[]")
    trade_reference = Column(String(160), nullable=True)
    provider_reference = Column(String(160), nullable=True)
    evidence_ref = Column(String(120), nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("quote_id", name="uq_prod_quote_accept"),)


class ProductionFxTrade(Base):
    __tablename__ = "prod_fx_trades"
    id = Column(Integer, primary_key=True)
    trade_id = Column(String(80), nullable=False, unique=True, index=True)
    trade_intent_id = Column(String(80), ForeignKey("prod_fx_trade_intents.trade_intent_id", ondelete="RESTRICT"), nullable=False, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    contract_state = Column(String(30), nullable=False)
    trade_reference = Column(String(160), nullable=True)
    payload = Column(Text, nullable=False, default="{}")
    evidence_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionSettlementLeg(Base):
    __tablename__ = "prod_settlement_legs"
    id = Column(Integer, primary_key=True)
    leg_id = Column(String(80), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    leg_role = Column(String(40), nullable=False)
    connector = Column(String(100), nullable=False)
    currency = Column(String(3), nullable=False)
    amount_minor = Column(BigInteger, nullable=False)
    state = Column(String(30), nullable=False, default="PENDING")
    external_reference = Column(String(160), nullable=True)
    finality_profile_id = Column(String(100), nullable=False)
    evidence_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("order_id", "leg_role", name="uq_prod_settlement_role"),)


class ProductionBeneficiaryCredit(Base):
    __tablename__ = "prod_beneficiary_credits"
    id = Column(Integer, primary_key=True)
    credit_id = Column(String(80), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    state = Column(String(30), nullable=False, default="UNKNOWN")
    external_reference = Column(String(160), nullable=True)
    evidence_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class ProductionReconciliationRun(Base):
    __tablename__ = "prod_reconciliation_runs"
    id = Column(Integer, primary_key=True)
    run_id = Column(String(80), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    state = Column(String(30), nullable=False, default="UNMATCHED")
    payment_hash = Column(String(64), nullable=False)
    subledger_hash = Column(String(64), nullable=True)
    external_statement_hash = Column(String(64), nullable=True)
    institution_gl_hash = Column(String(64), nullable=True)
    break_details = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class ProductionCancellationRequest(Base):
    __tablename__ = "prod_cancellation_requests"
    id = Column(Integer, primary_key=True)
    cancellation_request_id = Column(String(80), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    state = Column(String(30), nullable=False, default="REQUESTED")
    reason = Column(String(120), nullable=False)
    idempotency_context = Column(String(160), nullable=False, unique=True)
    external_reference = Column(String(160), nullable=True)
    evidence_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionInvestigationCase(Base):
    __tablename__ = "prod_investigation_cases"
    id = Column(Integer, primary_key=True)
    case_id = Column(String(80), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    case_type = Column(String(60), nullable=False)
    state = Column(String(30), nullable=False, default="OPEN")
    priority = Column(String(20), nullable=False, default="P2")
    owner = Column(String(120), nullable=True)
    reason = Column(String(500), nullable=False)
    evidence_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class ProductionReturnPayment(Base):
    __tablename__ = "prod_return_payments"
    id = Column(Integer, primary_key=True)
    return_payment_id = Column(String(80), nullable=False, unique=True, index=True)
    original_order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    original_uetr = Column(String(36), nullable=False, index=True)
    return_uetr = Column(String(36), nullable=False, unique=True, index=True)
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    reason = Column(String(120), nullable=False)
    state = Column(String(30), nullable=False, default="REQUESTED")
    return_sequence = Column(Integer, nullable=False, default=1)
    idempotency_context = Column(String(160), nullable=False, unique=True)
    return_leg_id = Column(String(80), nullable=True)
    external_reference = Column(String(160), nullable=True)
    evidence_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("original_order_id", "return_sequence", name="uq_prod_return_sequence"),)


class ProductionLedgerAccount(Base):
    __tablename__ = "prod_ledger_accounts"
    id = Column(Integer, primary_key=True)
    account_id = Column(String(100), nullable=False, unique=True, index=True)
    legal_entity = Column(String(100), nullable=False)
    book = Column(String(100), nullable=False)
    currency = Column(String(3), nullable=False)
    account_type = Column(String(50), nullable=False)
    balance_minor = Column(BigInteger, nullable=False, default=0)
    reserved_minor = Column(BigInteger, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("balance_minor >= 0", name="ck_prod_ledger_balance"),)


class ProductionJournal(Base):
    __tablename__ = "prod_journals"
    id = Column(Integer, primary_key=True)
    journal_id = Column(String(80), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=True, index=True)
    legal_entity = Column(String(100), nullable=False)
    book = Column(String(100), nullable=False)
    business_date = Column(String(10), nullable=False)
    state = Column(String(20), nullable=False, default="POSTED")
    gl_batch_reference = Column(String(160), nullable=False, default="")
    reason_code = Column(String(80), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("legal_entity", "book", "business_date", "gl_batch_reference", name="uq_prod_gl_batch_reference"),)


class ProductionJournalEntry(Base):
    __tablename__ = "prod_journal_entries"
    id = Column(Integer, primary_key=True)
    entry_id = Column(String(80), nullable=False, unique=True, index=True)
    journal_id = Column(String(80), ForeignKey("prod_journals.journal_id", ondelete="RESTRICT"), nullable=False, index=True)
    account_id = Column(String(100), nullable=False, index=True)
    direction = Column(String(10), nullable=False)
    currency = Column(String(3), nullable=False)
    amount_minor = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (
        CheckConstraint("direction IN ('DEBIT','CREDIT')", name="ck_prod_entry_direction"),
        CheckConstraint("amount_minor > 0", name="ck_prod_entry_amount"),
    )


class ProductionIdempotencyKey(Base):
    __tablename__ = "prod_idempotency_keys"
    id = Column(Integer, primary_key=True)
    scope = Column(String(160), nullable=False)
    key = Column(String(200), nullable=False)
    request_hash = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="STARTED")
    owner = Column(String(120), nullable=True)
    locked_until = Column(DateTime, nullable=True)
    attempt = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    trace_id = Column(String(120), nullable=True, index=True)
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_prod_idempotency_scope"),)


class ProductionRequestNonce(Base):
    __tablename__ = "prod_request_nonces"
    id = Column(Integer, primary_key=True)
    trust_domain = Column(String(80), nullable=False)
    key_id = Column(String(160), nullable=False)
    nonce = Column(String(240), nullable=False)
    request_digest = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    first_used_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("trust_domain", "key_id", "nonce", name="uq_prod_request_nonce_identity"),
    )


class ProductionKeyOperationAudit(Base):
    __tablename__ = "prod_key_operation_audits"
    id = Column(Integer, primary_key=True)
    operation_id = Column(String(100), nullable=False, unique=True, index=True)
    operation = Column(String(30), nullable=False)
    key_id = Column(String(160), nullable=False, index=True)
    trust_domain = Column(String(80), nullable=False)
    maker = Column(String(160), nullable=False)
    checker = Column(String(160), nullable=False)
    approval_id = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    result_digest = Column(String(64), nullable=True)
    evidence_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    completed_at = Column(DateTime, nullable=True)


class ProductionCorridorAdmission(Base):
    __tablename__ = "prod_corridor_admissions"
    id = Column(Integer, primary_key=True)
    admission_id = Column(String(100), nullable=False, unique=True, index=True)
    environment = Column(String(20), nullable=False, index=True)
    corridor = Column(String(40), nullable=False, index=True)
    applicable_subjects = Column(Text, nullable=False, default="[]")
    scenarios = Column(Text, nullable=False, default="[]")
    currencies = Column(Text, nullable=False, default="[]")
    min_amount_minor = Column(BigInteger, nullable=False, default=1)
    max_amount_minor = Column(BigInteger, nullable=False)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime, nullable=False)
    funding_flow_version = Column(String(80), nullable=False)
    finality_definition = Column(String(240), nullable=False)
    data_flow_version = Column(String(80), nullable=False)
    rulebook_version = Column(String(80), nullable=False)
    signed_roles = Column(Text, nullable=False, default="[]")
    status = Column(String(20), nullable=False, default="PENDING")
    simulation_only = Column(Boolean, nullable=False, default=True)
    evidence_ref = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (
        UniqueConstraint("environment", "corridor", "rulebook_version", name="uq_prod_corridor_environment_version"),
        CheckConstraint("min_amount_minor > 0 AND max_amount_minor >= min_amount_minor", name="ck_prod_corridor_amount_window"),
        CheckConstraint("status IN ('PENDING', 'ACTIVE', 'EXPIRED', 'REVOKED')", name="ck_prod_corridor_status"),
    )


class ProductionControlAttestation(Base):
    __tablename__ = "prod_control_attestations"
    id = Column(Integer, primary_key=True)
    attestation_id = Column(String(100), nullable=False, unique=True, index=True)
    admission_id = Column(String(100), nullable=False, index=True)
    signer_role = Column(String(100), nullable=False)
    signer_subject = Column(String(160), nullable=False)
    statement_digest = Column(String(64), nullable=False)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    evidence_ref = Column(String(120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionOutboxEvent(Base):
    __tablename__ = "prod_outbox_events"
    id = Column(Integer, primary_key=True)
    event_id = Column(String(80), nullable=False, unique=True, index=True)
    topic = Column(String(160), nullable=False, index=True)
    schema_version = Column(String(40), nullable=False, default="1.0")
    partition_key = Column(String(120), nullable=False, index=True)
    aggregate_id = Column(String(120), nullable=False, index=True)
    tenant_id = Column(String(120), nullable=False, index=True)
    participant_id = Column(String(120), nullable=False, index=True)
    aggregate_sequence = Column(Integer, nullable=False, default=1)
    payload = Column(Text, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    content_hash = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime, nullable=False, default=utcnow)
    lease_owner = Column(String(120), nullable=True, index=True)
    lease_until = Column(DateTime, nullable=True, index=True)
    lease_heartbeat_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    broker_offset = Column(String(200), nullable=True)
    broker_metadata = Column(Text, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("topic", "aggregate_id", "aggregate_sequence", name="uq_prod_event_aggregate_sequence"),)


class ProductionReplayRequest(Base):
    __tablename__ = "prod_replay_requests"
    id = Column(Integer, primary_key=True)
    replay_id = Column(String(100), nullable=False, unique=True, index=True)
    event_id = Column(String(80), ForeignKey("prod_outbox_events.event_id", ondelete="RESTRICT"), nullable=False, index=True)
    tenant_id = Column(String(120), nullable=False, index=True)
    original_hash = Column(String(64), nullable=False)
    maker = Column(String(200), nullable=False)
    checker = Column(String(200), nullable=True)
    state = Column(String(20), nullable=False, default="PENDING")
    reason = Column(String(500), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    approved_at = Column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("event_id", name="uq_prod_replay_event"),)


class ProductionInboxMessage(Base):
    __tablename__ = "prod_inbox_messages"
    id = Column(Integer, primary_key=True)
    consumer = Column(String(100), nullable=False)
    event_id = Column(String(80), ForeignKey("prod_outbox_events.event_id", ondelete="RESTRICT"), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("consumer", "event_id", name="uq_prod_inbox_consumer_event"),)


class ProductionEvidenceManifest(Base):
    __tablename__ = "prod_evidence_manifests"
    id = Column(Integer, primary_key=True)
    evidence_id = Column(String(100), nullable=False, unique=True, index=True)
    evidence_type = Column(String(80), nullable=False)
    aggregate_id = Column(String(120), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False)
    previous_hash = Column(String(64), nullable=True)
    storage_uri = Column(String(500), nullable=False)
    retention_class = Column(String(80), nullable=False)
    legal_hold = Column(Boolean, nullable=False, default=False)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionAuditEvent(Base):
    __tablename__ = "prod_audit_events"
    id = Column(Integer, primary_key=True)
    event_id = Column(String(100), nullable=False, unique=True, index=True)
    trace_id = Column(String(100), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    aggregate_id = Column(String(120), nullable=False, index=True)
    payload_hash = Column(String(64), nullable=False)
    previous_hash = Column(String(64), nullable=True)
    payload = Column(Text, nullable=False)
    actor = Column(String(120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionStandardArtifact(Base):
    __tablename__ = "prod_standard_artifacts"
    id = Column(Integer, primary_key=True)
    artifact_id = Column(String(100), nullable=False, unique=True, index=True)
    profile = Column(String(120), nullable=False, index=True)
    message_type = Column(String(80), nullable=False)
    version = Column(String(40), nullable=False)
    artifact_kind = Column(String(30), nullable=False)
    digest = Column(String(64), nullable=False)
    source_uri = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    simulation_only = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionTransactionCopy(Base):
    __tablename__ = "prod_transaction_copies"
    id = Column(Integer, primary_key=True)
    copy_id = Column(String(100), nullable=False, unique=True, index=True)
    order_id = Column(String(80), nullable=False, index=True)
    copy_type = Column(String(40), nullable=False)
    message_type = Column(String(80), nullable=False)
    version = Column(String(40), nullable=False)
    payload = Column(Text, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    source_artifact_id = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionFieldLineage(Base):
    __tablename__ = "prod_field_lineage"
    id = Column(Integer, primary_key=True)
    lineage_id = Column(String(100), nullable=False, unique=True, index=True)
    order_id = Column(String(80), nullable=False, index=True)
    source_path = Column(String(240), nullable=False)
    target_path = Column(String(240), nullable=False)
    transform = Column(String(120), nullable=False)
    source_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionReconciliationBreak(Base):
    __tablename__ = "prod_reconciliation_breaks"
    id = Column(Integer, primary_key=True)
    break_id = Column(String(100), nullable=False, unique=True, index=True)
    order_id = Column(String(80), ForeignKey("prod_payment_orders.order_id", ondelete="RESTRICT"), nullable=False, index=True)
    break_type = Column(String(80), nullable=False)
    severity = Column(String(20), nullable=False, default="P2")
    state = Column(String(20), nullable=False, default="OPEN")
    details = Column(Text, nullable=False, default="{}")
    case_id = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionReportBatch(Base):
    __tablename__ = "prod_report_batches"
    id = Column(Integer, primary_key=True)
    batch_id = Column(String(100), nullable=False, unique=True, index=True)
    report_type = Column(String(80), nullable=False)
    period_start = Column(String(30), nullable=False)
    period_end = Column(String(30), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    state = Column(String(20), nullable=False, default="CREATED")
    created_at = Column(DateTime, nullable=False, default=utcnow)


class ProductionReportReceipt(Base):
    __tablename__ = "prod_report_receipts"
    id = Column(Integer, primary_key=True)
    receipt_id = Column(String(100), nullable=False, unique=True, index=True)
    batch_id = Column(String(100), ForeignKey("prod_report_batches.batch_id", ondelete="RESTRICT"), nullable=False, index=True)
    receiver = Column(String(120), nullable=False)
    state = Column(String(20), nullable=False, default="PENDING")
    external_reference = Column(String(160), nullable=True)
    receipt_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
