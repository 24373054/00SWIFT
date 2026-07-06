"""SQLAlchemy ORM models and DB initialization.

Extends the old prototype's 4 tables (AppCredential, OAuthToken, ApiRequest,
PaymentState) with:
* PKI fields on AppCredential (cert_pem, cert_x5c, cert_subject, allowed_scopes).
* JtiRecord — replay-protection for OAuth assertions and signature JWTs.
* FinMessage + MessageDistribution — Messaging API state.
* SwiftRefBic / SwiftRefIban / SwiftRefCurrency / SwiftRefCountry — seeded
  static reference data for the SwiftRef mock.

PaymentState gains tracker-aligned fields (transaction_status, service_level,
payment_scenario, business_service, from_bic, tracker_informing_party). The
legacy ``history`` JSON column is preserved.

No foreign keys (soft-link by app_id / uetr / distribution_id), matching the
old prototype's convention — kept for simplicity in a single-user sandbox.
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any, Dict, List

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from config import get_settings
from core.time import now_utc

DATABASE_URL = get_settings().db_url

# For in-memory SQLite, use a StaticPool so all connections share the same
# underlying connection (otherwise each connection sees an empty DB, breaking
# tests). For file-based SQLite, the default pool is fine.
if DATABASE_URL.startswith("sqlite") and ":memory:" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


# Replaced the deprecated `datetime.datetime.utcnow` column defaults with
# timezone-aware `now_utc`. These are callables (not invocations) so SQLAlchemy
# calls them per-row at insert time.
def _utcnow() -> datetime.datetime:
    return now_utc()


# =========================================================================
# Auth / credentials
# =========================================================================

class AppCredential(Base):
    """A registered application. Holds consumer key/secret + PKI material.

    The PKI fields (cert_pem, cert_x5c, cert_subject) are populated when the
    credential is created in sandbox mode (a mock CA signs a client cert), or
    uploaded by the user in pilot/live mode.
    """

    __tablename__ = "app_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_name = Column(String(200), nullable=False)
    consumer_key = Column(String(200), unique=True, nullable=False)
    consumer_secret = Column(String(200), nullable=False)
    environment = Column(String(20), default="sandbox")
    created_at = Column(DateTime, default=_utcnow)
    last_used = Column(DateTime, nullable=True)

    # PKI material (new).
    cert_pem = Column(Text, nullable=True)  # PEM-encoded client certificate
    cert_x5c = Column(Text, nullable=True)  # JSON list of base64 DER segments
    cert_subject = Column(String(500), nullable=True)  # RFC4514 lowercased
    allowed_scopes = Column(Text, nullable=True, default="")  # space-separated


class OAuthToken(Base):
    """An issued OAuth2 access token (opaque or JWT)."""

    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(Integer, nullable=False)
    access_token = Column(String(2000), unique=True, nullable=False)
    token_type = Column(String(50), default="Bearer")
    expires_in = Column(Integer, default=3600)
    scope = Column(String(1000), default="")
    issued_at = Column(DateTime, default=_utcnow)
    is_revoked = Column(Boolean, default=False)


class JtiRecord(Base):
    """Replay-protection record for JWT ``jti`` claims.

    One row per assertion/signature JWT verified. TTL is the assertion's
    ``exp`` (plus a small buffer). Cleaned up periodically by jti_store.
    """

    __tablename__ = "jti_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(200), unique=True, nullable=False, index=True)
    app_id = Column(Integer, nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=_utcnow)


# =========================================================================
# Audit
# =========================================================================

class ApiRequest(Base):
    """API call audit log. Latency is now real-measured (middleware.py)."""

    __tablename__ = "api_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    api_name = Column(String(200), nullable=False)
    method = Column(String(10), nullable=False)
    endpoint = Column(String(500), nullable=False)
    request_headers = Column(Text, default="{}")
    request_body = Column(Text, default="")
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, default="")
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)


# =========================================================================
# GPI Tracker payment state
# =========================================================================

class PaymentState(Base):
    """A tracked payment. Aligned with the GPI Tracker v4 transaction model.

    ``transaction_status`` holds a ``TransactionIndividualStatus5Code``
    (PDNG/ACSP/ACSC/RJCT/CANC/ACCC/ACCP/PART). The legacy ``state`` column is
    retained as a compatibility alias populated from ``transaction_status``.
    """

    __tablename__ = "payment_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uetr = Column(String(36), unique=True, nullable=False, index=True)
    instruction_id = Column(String(200), nullable=True)
    end_to_end_id = Column(String(200), nullable=True)
    amount = Column(String(20), default="")
    currency = Column(String(3), default="EUR")
    debtor_agent = Column(String(20), default="")
    creditor_agent = Column(String(20), default="")
    debtor_name = Column(String(200), nullable=True)
    creditor_name = Column(String(200), nullable=True)

    # Tracker-aligned status fields (new).
    transaction_status = Column(String(20), default="PDNG")
    service_level = Column(String(20), nullable=True)  # e.g. G001 (gpi)
    payment_scenario = Column(String(30), nullable=True)  # e.g. CCTN/COVN/FITN/INST
    business_service = Column(String(30), nullable=True)
    from_bic = Column(String(20), nullable=True)  # tracker_informing_party BIC

    # Legacy fields kept for compatibility.
    state = Column(String(20), default="PDNG")
    iso20022_msg = Column(Text, default="")
    history = Column(Text, default="[]")  # JSON: [{state, timestamp, reason}]

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# =========================================================================
# Messaging (FIN/InterAct/FileAct)
# =========================================================================

class FinMessage(Base):
    """A FIN (or InterAct) message sent via the Messaging API."""

    __tablename__ = "fin_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_reference = Column(String(70), nullable=False, index=True)  # UUMID
    message_type = Column(String(40), nullable=False)  # e.g. fin.103, fin.202.COV
    sender = Column(String(12), nullable=False)  # BIC12
    receiver = Column(String(12), nullable=False)  # BIC12
    payload = Column(Text, nullable=False)  # base64 of MT block 4 text
    uetr = Column(String(36), nullable=True)
    network_priority = Column(String(20), default="Normal")
    network_info = Column(Text, default="{}")  # JSON
    distribution_id = Column(String(36), nullable=True, index=True)  # soft-link to MessageDistribution
    created_at = Column(DateTime, default=_utcnow)


class MessageDistribution(Base):
    """A distribution (inbound message envelope) in the Alliance Cloud inbox."""

    __tablename__ = "message_distributions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    distribution_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    service = Column(String(20), default="fin")  # fin/interAct/fileAct
    message_type = Column(String(40), nullable=True)
    sender = Column(String(12), nullable=True)
    receiver = Column(String(12), nullable=True)
    message_cloud_reference = Column(String(36), nullable=True)
    status = Column(String(20), default="available")  # available/distributed/acked/naked/failed
    nak_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# =========================================================================
# SwiftRef static reference data (seeded from data/*.json)
# =========================================================================

class SwiftRefBic(Base):
    __tablename__ = "swiftref_bics"

    bic = Column(String(11), primary_key=True)  # uppercase, 8 or 11
    name = Column(String(200), nullable=True)
    office_type = Column(String(20), nullable=True)  # BIC/FBR/...
    country_code = Column(String(2), nullable=True)
    town_name = Column(String(100), nullable=True)
    post_code = Column(String(20), nullable=True)
    address_line = Column(String(200), nullable=True)
    swift_connectivity = Column(Text, default="{}")  # JSON: {fin, interact, fileact}
    connected_bic = Column(String(11), nullable=True)
    utc_offset = Column(String(10), nullable=True)


class SwiftRefIban(Base):
    __tablename__ = "swiftref_ibans"

    iban = Column(String(34), primary_key=True)  # uppercase, no spaces
    bic = Column(String(11), nullable=True, index=True)
    country_code = Column(String(2), nullable=True)
    bank_code = Column(String(30), nullable=True)
    branch_code = Column(String(30), nullable=True)
    account_number = Column(String(30), nullable=True)
    valid = Column(Boolean, default=True)


class SwiftRefCurrency(Base):
    __tablename__ = "swiftref_currencies"

    code = Column(String(3), primary_key=True)  # ISO 4217 alpha-3, uppercase
    name = Column(String(100), nullable=True)
    iso_3n_code = Column(String(3), nullable=True)
    minor_unit = Column(Integer, nullable=True)  # fractional digits (0-5)
    countries = Column(Text, default="[]")  # JSON list of ISO 3166 alpha-2


class SwiftRefCountry(Base):
    __tablename__ = "swiftref_countries"

    code = Column(String(2), primary_key=True)  # ISO 3166 alpha-2, uppercase
    name = Column(String(100), nullable=True)
    iso_3a_code = Column(String(3), nullable=True)
    iso_3n_code = Column(String(3), nullable=True)
    currency_code = Column(String(3), nullable=True)  # primary currency
    iban_structure = Column(Text, nullable=True)  # JSON: {length, bban_format} or null


# =========================================================================
# e-CNY — wallets & holders
# =========================================================================

class EcnyWallet(Base):
    """A digital yuan wallet. Tier 1/2/3 (DC/EP grading)."""
    __tablename__ = "ecny_wallets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    holder_id = Column(String(36), nullable=True, index=True)  # soft-link to EcnyHolder
    tier = Column(Integer, default=3)  # 1=strong KYC/large, 2=medium, 3=small anonymous
    operator_id = Column(Integer, nullable=True)  # operating institution app_id
    currency = Column(String(3), default="CNY")
    balance = Column(Integer, default=0)  # in fen (分), integer to avoid float error
    status = Column(String(20), default="active")  # active/frozen/closed
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class EcnyHolder(Base):
    """Wallet holder KYC. id_hash only (never store raw ID). Tier 3 may be null (anonymous)."""
    __tablename__ = "ecny_holders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    holder_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    wallet_id = Column(String(36), nullable=True, index=True)
    real_name = Column(String(200), nullable=True)  # may be null for anonymous
    id_type = Column(String(20), nullable=True)  # id_card/passport/...
    id_hash = Column(String(128), nullable=True)  # SHA256 of raw ID, never raw
    kyc_level = Column(Integer, default=0)  # 0=none, 1=weak, 2=medium, 3=strong
    country_code = Column(String(2), nullable=True)
    created_at = Column(DateTime, default=_utcnow)


# =========================================================================
# e-CNY — ledger accounts & double-entry
# =========================================================================

class EcnyAccount(Base):
    """A ledger account. owner_type: central_bank / operator / wallet."""
    __tablename__ = "ecny_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    owner_type = Column(String(20), nullable=False)  # central_bank/operator/wallet
    owner_ref = Column(String(100), nullable=True)  # app_id / wallet_id / "PBOC"
    currency = Column(String(3), default="CNY")
    balance = Column(Integer, default=0)  # fen
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class EcnyTransaction(Base):
    """A ledger transaction. Atomic, double-entry, immutable once settled."""
    __tablename__ = "ecny_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    tx_type = Column(String(30), nullable=False)  # mint/burn/transfer/exchange/cross_border
    status = Column(String(20), default="pending")  # pending/settled/failed
    uetr = Column(String(36), nullable=True, index=True)  # for cross-border
    amount = Column(Integer, nullable=False, default=0)  # fen
    currency = Column(String(3), default="CNY")
    from_account = Column(String(36), nullable=True)
    to_account = Column(String(36), nullable=True)
    memo = Column(Text, default="{}")  # JSON
    created_at = Column(DateTime, default=_utcnow)
    settled_at = Column(DateTime, nullable=True)


class EcnyEntry(Base):
    """Double-entry leg. Two rows per transaction (debit + credit)."""
    __tablename__ = "ecny_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(String(36), unique=True, nullable=False, index=True)
    tx_id = Column(String(36), nullable=False, index=True)
    account_id = Column(String(36), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # debit/credit
    amount = Column(Integer, nullable=False, default=0)  # fen
    created_at = Column(DateTime, default=_utcnow)


# =========================================================================
# e-CNY — bridge (mBridge / CIPS)
# =========================================================================

class EcnyBridgeChannel(Base):
    """A cross-border bridge channel."""
    __tablename__ = "ecny_bridge_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(String(36), unique=True, nullable=False, index=True)
    channel_type = Column(String(20), nullable=False)  # mbridge/cips
    counterparty = Column(String(100), nullable=True)  # counterparty CB/system
    currency_pair = Column(String(20), nullable=True)  # e.g. CNY/HKD
    status = Column(String(20), default="active")  # active/closed
    fx_rate = Column(Text, default="{}")  # JSON {rate, as_of}
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class EcnyBridgeTransaction(Base):
    """A cross-border transaction routed via a bridge channel."""
    __tablename__ = "ecny_bridge_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bridge_tx_id = Column(String(36), unique=True, nullable=False, index=True)
    uetr = Column(String(36), nullable=False, index=True)
    channel_id = Column(String(36), nullable=True, index=True)
    from_currency = Column(String(3), nullable=False)
    from_amount = Column(Integer, nullable=False, default=0)  # fen
    to_currency = Column(String(3), nullable=False)
    to_amount = Column(Integer, nullable=False, default=0)  # fen
    fx_rate = Column(String(50), nullable=True)  # decimal as string
    status = Column(String(20), default="pending")  # pending/settled/failed
    counterparty_ref = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    settled_at = Column(DateTime, nullable=True)


# =========================================================================
# e-CNY — compliance
# =========================================================================

class EcnyComplianceReport(Base):
    """A regulatory compliance report (large cash / suspicious / cross-border)."""
    __tablename__ = "ecny_compliance_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(36), unique=True, nullable=False, index=True)
    tx_id = Column(String(36), nullable=True, index=True)
    report_type = Column(String(30), nullable=False)  # large_cash/suspicious/cross_border
    amount = Column(Integer, nullable=False, default=0)  # fen
    currency = Column(String(3), default="CNY")
    threshold = Column(Integer, nullable=True)  # fen
    details = Column(Text, default="{}")  # JSON
    created_at = Column(DateTime, default=_utcnow)


# =========================================================================
# Initialization + seeding
# =========================================================================

def init_db() -> None:
    """Create all tables (idempotent). Does NOT run migrations."""
    Base.metadata.create_all(bind=engine)


def seed_reference_data() -> None:
    """Seed SwiftRef tables from data/*.json if they are empty.

    Called at startup. Safe to call repeatedly — only seeds when a table is
    empty, so it never overwrites user edits.
    """
    db = SessionLocal()
    try:
        _seed_if_empty(db, SwiftRefBic, "bics.json", _row_for_bic)
        _seed_if_empty(db, SwiftRefIban, "ibans.json", _row_for_iban)
        _seed_if_empty(db, SwiftRefCurrency, "currencies.json", _row_for_currency)
        _seed_if_empty(db, SwiftRefCountry, "countries.json", _row_for_country)
        db.commit()
    finally:
        db.close()


def _data_dir() -> str:
    backend_root = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(backend_root, "data")


def _load_fixture(filename: str) -> List[Dict[str, Any]]:
    path = os.path.join(_data_dir(), filename)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _seed_if_empty(db, model, filename: str, row_fn) -> None:
    if db.query(model).first() is not None:
        return
    for item in _load_fixture(filename):
        db.add(row_fn(item))


def _row_for_bic(item: Dict[str, Any]) -> SwiftRefBic:
    return SwiftRefBic(
        bic=item["bic"].upper(),
        name=item.get("name"),
        office_type=item.get("office_type"),
        country_code=item.get("country_code"),
        town_name=item.get("town_name"),
        post_code=item.get("post_code"),
        address_line=item.get("address_line"),
        swift_connectivity=json.dumps(item.get("swift_connectivity", {})),
        connected_bic=item.get("connected_bic"),
        utc_offset=item.get("utc_offset"),
    )


def _row_for_iban(item: Dict[str, Any]) -> SwiftRefIban:
    return SwiftRefIban(
        iban=item["iban"].upper().replace(" ", ""),
        bic=item.get("bic"),
        country_code=item.get("country_code"),
        bank_code=item.get("bank_code"),
        branch_code=item.get("branch_code"),
        account_number=item.get("account_number"),
        valid=item.get("valid", True),
    )


def _row_for_currency(item: Dict[str, Any]) -> SwiftRefCurrency:
    return SwiftRefCurrency(
        code=item["code"].upper(),
        name=item.get("name"),
        iso_3n_code=item.get("iso_3n_code"),
        minor_unit=item.get("minor_unit"),
        countries=json.dumps(item.get("countries", [])),
    )


def _row_for_country(item: Dict[str, Any]) -> SwiftRefCountry:
    return SwiftRefCountry(
        code=item["code"].upper(),
        name=item.get("name"),
        iso_3a_code=item.get("iso_3a_code"),
        iso_3n_code=item.get("iso_3n_code"),
        currency_code=item.get("currency_code"),
        iban_structure=json.dumps(item.get("iban_structure")) if item.get("iban_structure") is not None else None,
    )


# =========================================================================
# e-CNY — initialization + seeding
# =========================================================================

def seed_ecny_data() -> None:
    """Seed the e-CNY ledger with the central bank issuance account and the
    default mBridge/CIPS bridge channels. Idempotent — only seeds when empty.

    Called at startup. Creates:
    * One central bank account (owner PBOC) — the issuance wellspring.
    * Two default bridge channels: mBridge (multi) and CIPS (bilateral).
    """
    db = SessionLocal()
    try:
        if db.query(EcnyAccount).filter(EcnyAccount.owner_type == "central_bank").first() is None:
            cb = EcnyAccount(
                account_id="acct-pboc-issuance-0001",
                owner_type="central_bank",
                owner_ref="PBOC",
                currency="CNY",
                balance=0,  # issuance wellspring; mint credits here conceptually
            )
            db.add(cb)

        if db.query(EcnyBridgeChannel).first() is None:
            db.add(EcnyBridgeChannel(
                channel_id="ch-mbridge-0001",
                channel_type="mbridge",
                counterparty="mBridge multi-CBDC platform",
                currency_pair="CNY/MULTI",
                status="active",
                fx_rate=json.dumps({"rate": "1.000000", "as_of": "2026-01-01"}),
            ))
            db.add(EcnyBridgeChannel(
                channel_id="ch-cips-0001",
                channel_type="cips",
                counterparty="CIPS (Cross-Border Interbank Payment System)",
                currency_pair="CNY/CNY",
                status="active",
                fx_rate=json.dumps({"rate": "1.000000", "as_of": "2026-01-01"}),
            ))
        db.commit()
    finally:
        db.close()


def get_db():
    """FastAPI dependency: yield a DB session, close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
