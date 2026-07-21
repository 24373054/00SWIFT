"""Tests for retail CBDC, offline value, programmable money, PvP and platform controls."""
from __future__ import annotations

import datetime as dt

import pytest

from database import EcnyAccount
from ecny.ledger.engine import get_or_create_account
from nextgen.cbdc import (
    HkRetailService,
    MultiCbdcService,
    OfflineValueService,
    ProgrammableMoneyService,
    RetailProfileError,
    privacy_digest,
)
from nextgen.cips import EcnyOperatorService
from nextgen.models import RuntimeAuditEvent
from nextgen.platform import (
    AuditChainService,
    LocalKeyProvider,
    PolicyEngine,
    ReconciliationService,
    trace_span,
)


def _operator_and_wallets(db):
    EcnyOperatorService(db).register("HK-OP", "HK Operator", 10_000_00, 10_000_00)
    retail = HkRetailService(db)
    payer = retail.create_wallet("HK-OP", tier=4, phone_hash="payer-hash")
    merchant = retail.create_wallet("HK-OP", tier=2, phone_hash="merchant-hash")
    retail.fps_top_up("HK-OP", payer.wallet_id, 1_000_00)
    return retail, payer, merchant


def test_hk_retail_topup_and_merchant_payment(db):
    retail, payer, merchant = _operator_and_wallets(db)
    tx = retail.merchant_payment(payer.wallet_id, merchant.wallet_id, 100_00, "5411")
    assert tx.status == "settled"
    payer_balance = db.query(EcnyAccount).filter_by(account_id=f"acct-wallet-{payer.wallet_id}").one()
    merchant_balance = db.query(EcnyAccount).filter_by(
        account_id=f"acct-wallet-{merchant.wallet_id}"
    ).one()
    assert payer_balance.balance == 900_00
    assert merchant_balance.balance == 100_00


def test_hk_retail_profile_blocks_cross_border_p2p(db):
    retail, payer, merchant = _operator_and_wallets(db)
    with pytest.raises(RetailProfileError, match="P2P"):
        retail.p2p_transfer(payer.wallet_id, merchant.wallet_id, 10_00)


def test_hk_wallet_tier_limit_is_enforced(db):
    retail, payer, merchant = _operator_and_wallets(db)
    with pytest.raises(RetailProfileError, match="limit"):
        retail.merchant_payment(payer.wallet_id, merchant.wallet_id, 2_001_00, "5411")


def test_offline_voucher_reserves_and_redeems_once(db):
    _, payer, merchant = _operator_and_wallets(db)
    service = OfflineValueService(db)
    voucher = service.issue(payer.wallet_id, "device-1", 50_00)
    db.commit()
    tx = service.redeem(voucher.voucher_id, voucher.nonce, merchant.wallet_id)
    assert tx.status == "settled"
    with pytest.raises(ValueError, match="already"):
        service.redeem(voucher.voucher_id, voucher.nonce, merchant.wallet_id)


def test_offline_voucher_rejects_wrong_nonce(db):
    _, payer, merchant = _operator_and_wallets(db)
    service = OfflineValueService(db)
    voucher = service.issue(payer.wallet_id, "device-1", 50_00)
    with pytest.raises(ValueError, match="nonce"):
        service.redeem(voucher.voucher_id, "wrong", merchant.wallet_id)


def test_programmable_money_uses_allowlisted_templates(db):
    _, payer, merchant = _operator_and_wallets(db)
    service = ProgrammableMoneyService(db)
    instrument = service.create(
        payer.wallet_id,
        80_00,
        "merchant_category",
        {"merchant_categories": ["5411"]},
    )
    with pytest.raises(ValueError, match="conditions"):
        service.execute(
            instrument.instrument_id,
            merchant.wallet_id,
            20_00,
            {"merchant_category": "7995"},
        )
    tx = service.execute(
        instrument.instrument_id,
        merchant.wallet_id,
        80_00,
        {"merchant_category": "5411"},
    )
    assert tx.status == "settled"
    assert instrument.status == "spent"


def test_programmable_money_rejects_arbitrary_template(db):
    _, payer, _ = _operator_and_wallets(db)
    with pytest.raises(ValueError, match="Unsupported"):
        ProgrammableMoneyService(db).create(payer.wallet_id, 10, "python_eval", {"code": "1+1"})


def test_multi_cbdc_policy_is_bilateral(db):
    service = MultiCbdcService(db)
    service.register_jurisdiction(
        "CN",
        "CNY",
        "PBOC-SIM",
        "CN",
        {"max_cross_border_amount": 1_000_00, "allowed_purposes": ["trade"]},
    )
    service.register_jurisdiction(
        "HK",
        "HKD",
        "HKMA-SIM",
        "HK",
        {"max_cross_border_amount": 500_00, "allowed_purposes": ["trade", "retail"]},
    )
    service.register_node("node-cn", "CN", "PBOC-SIM", "central_bank")
    service.register_node("node-hk", "HK", "HKMA-SIM", "central_bank")
    assert service.authorize_cross_border("CN", "HK", 400_00, "trade")["allowed"]
    denied = service.authorize_cross_border("CN", "HK", 600_00, "retail")
    assert not denied["allowed"]
    assert len(denied["reasons"]) == 2


def _pvp_accounts(db):
    accounts = {
        "a-cny": get_or_create_account(db, "a-cny", "operator", "A", "CNY"),
        "b-cny": get_or_create_account(db, "b-cny", "operator", "B", "CNY"),
        "a-hkd": get_or_create_account(db, "a-hkd", "operator", "A", "HKD"),
        "b-hkd": get_or_create_account(db, "b-hkd", "operator", "B", "HKD"),
    }
    accounts["a-cny"].balance = 1_000
    accounts["b-hkd"].balance = 2_000
    return accounts


def test_fx_quote_and_atomic_pvp(db):
    accounts = _pvp_accounts(db)
    service = MultiCbdcService(db)
    quote = service.create_quote("FX-A", "CNY", "HKD", "1.20", 1_000)
    pvp = service.create_pvp(
        quote.quote_id,
        {
            "from_account": "a-cny",
            "to_account": "b-cny",
            "amount": 100,
            "currency": "CNY",
        },
        {
            "from_account": "b-hkd",
            "to_account": "a-hkd",
            "amount": 120,
            "currency": "HKD",
        },
    )
    pvp = service.lock_pvp(pvp.pvp_id, 1)
    assert pvp.state == "LOCKED"
    pvp = service.commit_pvp(pvp.pvp_id, 2)
    assert pvp.state == "COMMITTED"
    assert accounts["a-cny"].balance == 900
    assert accounts["b-cny"].balance == 100
    assert accounts["b-hkd"].balance == 1_880
    assert accounts["a-hkd"].balance == 120


def test_pvp_rejects_quote_mismatch(db):
    _pvp_accounts(db)
    service = MultiCbdcService(db)
    quote = service.create_quote("FX-A", "CNY", "HKD", "1.20", 1_000)
    with pytest.raises(ValueError, match="quote"):
        service.create_pvp(
            quote.quote_id,
            {"from_account": "a-cny", "to_account": "b-cny", "amount": 100, "currency": "CNY"},
            {"from_account": "b-hkd", "to_account": "a-hkd", "amount": 119, "currency": "HKD"},
        )


def test_local_key_provider_authenticates_and_encrypts():
    provider = LocalKeyProvider("test-master-secret")
    payload = b"pacs.008 payload"
    signature = provider.sign("payments", payload)
    assert provider.verify("payments", payload, signature)
    assert not provider.verify("payments", b"tampered", signature)
    ciphertext = provider.encrypt("payments", payload)
    assert provider.decrypt("payments", ciphertext) == payload


def test_explainable_policy_decision_and_audit_chain(db):
    decision = PolicyEngine(db).evaluate(
        "bank-a",
        "settle",
        "pvp-1",
        {"roles": ["settlement"], "amount": 100, "jurisdiction": "CN", "purpose": "trade"},
        {
            "required_roles": ["settlement"],
            "max_amount": 1_000,
            "allowed_jurisdictions": ["CN", "HK"],
            "allowed_purposes": ["trade"],
        },
    )
    assert decision.result == "allow"
    audit = AuditChainService(db)
    audit.append("policy.decision", decision.decision_id, {"result": decision.result})
    audit.append("payment.settled", "pvp-1", {"amount": 100})
    assert audit.verify()
    db.query(RuntimeAuditEvent).order_by(RuntimeAuditEvent.id.desc()).first().payload = "tampered"
    assert not audit.verify()


def test_reconciliation_and_trace_context(db):
    with trace_span("reconciliation", component="nextgen") as span:
        report = ReconciliationService(db).run()
    assert report["ok"]
    assert span["span"].name == "reconciliation"
    assert span["span"].duration_ms >= 0


def test_privacy_digest_is_salted_and_deterministic():
    assert privacy_digest("wallet-1", "salt-a") == privacy_digest("wallet-1", "salt-a")
    assert privacy_digest("wallet-1", "salt-a") != privacy_digest("wallet-1", "salt-b")


def test_expiry_template(db):
    _, payer, merchant = _operator_and_wallets(db)
    service = ProgrammableMoneyService(db)
    instrument = service.create(
        payer.wallet_id,
        10_00,
        "expiry",
        {"expires_at": (dt.datetime.now(dt.UTC) + dt.timedelta(minutes=1)).isoformat()},
    )
    assert service.execute(instrument.instrument_id, merchant.wallet_id, 10_00, {}).status == "settled"
