"""ISO 20022 e-CNY message tests — generation + injection safety."""
from iso20022.ecny_messages import (build_ecny_cross_border_msg,
                                     build_ecny_issuance_msg, build_pacs002_ecny,
                                     build_pacs008_ecny)


def test_pacs008_ecny_has_wallet_and_purpose():
    xml = build_pacs008_ecny(debtor_wallet="w1", creditor_wallet="w2",
                             amount_fen=10000, debtor_name="Alice")
    assert "DigitalCurrencyTransfer" in xml
    assert "w1" in xml and "w2" in xml
    assert "pacs.008" in xml


def test_pacs008_ecny_escapes_injection():
    xml = build_pacs008_ecny(debtor_wallet="w1", creditor_wallet="w2",
                             amount_fen=10000,
                             debtor_name="Alice</Nm><Id>evil</Id>")
    assert "evil</Id>" not in xml
    assert "&lt;/Nm&gt;" in xml


def test_pacs002_ecny_status():
    xml = build_pacs002_ecny(uetr="u1", tx_status="ACSC", amount_fen=10000)
    assert "ACSC" in xml and "pacs.002" in xml


def test_issuance_msg():
    xml = build_ecny_issuance_msg(operator="ICBC", amount_fen=1000000, action="mint")
    assert "EcnyIssuance" in xml and "mint" in xml


def test_cross_border_msg():
    xml = build_ecny_cross_border_msg(uetr="u1", channel="mbridge",
                                      from_currency="CNY", from_amount_fen=10000,
                                      to_currency="HKD", to_amount_fen=10800,
                                      fx_rate="1.08", counterparty="HKMA")
    assert "EcnyCrossBorder" in xml and "HKD" in xml and "mbridge" in xml


def test_amount_must_be_positive():
    import pytest
    with pytest.raises(ValueError):
        build_pacs008_ecny(debtor_wallet="w1", creditor_wallet="w2", amount_fen=0)
