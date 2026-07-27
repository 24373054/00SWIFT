from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

import production.corridors as corridors
from production.models import ProductionControlAttestation, ProductionCorridorAdmission
from production.runtime import ProductionConflict


def _admission(admission_id: str, *, rulebook="cn-hk-v1"):
    now = dt.datetime.now(dt.UTC)
    return ProductionCorridorAdmission(
        admission_id=admission_id,
        environment="sandbox",
        corridor="CN-HK",
        applicable_subjects='["SANDBOX-ORIGIN"]',
        scenarios='["TRADE"]',
        currencies='["CNY"]',
        min_amount_minor=1,
        max_amount_minor=100_000_000,
        valid_from=now - dt.timedelta(minutes=1),
        valid_to=now + dt.timedelta(days=1),
        funding_flow_version="fund-v1",
        finality_definition="sandbox-final",
        data_flow_version="data-v1",
        rulebook_version=rulebook,
        signed_roles='["sandbox-authority"]',
        status="ACTIVE",
        simulation_only=True,
        evidence_ref="evidence://sandbox/admission",
    )


def test_corridor_admission_and_control_attestation_persist(db):
    admission = _admission("adm-1")
    db.add(admission)
    db.add(ProductionControlAttestation(
        attestation_id="att-1", admission_id="adm-1", signer_role="sandbox-authority",
        signer_subject="sandbox", statement_digest="a" * 64,
        valid_from=admission.valid_from, valid_to=admission.valid_to,
        status="ACTIVE", evidence_ref="evidence://sandbox/control",
    ))
    db.commit()
    assert db.query(ProductionCorridorAdmission).filter_by(admission_id="adm-1").one().simulation_only


def test_corridor_environment_corridor_rulebook_is_unique(db):
    db.add(_admission("adm-1"))
    db.commit()
    db.add(_admission("adm-2"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_admission_check_is_default_deny_for_unapproved_scenario(db):
    admission = _admission("adm-1")
    db.add(admission)
    db.add(ProductionControlAttestation(
        attestation_id="att-1", admission_id="adm-1", signer_role="authority", signer_subject="subject",
        statement_digest="a" * 64, valid_from=admission.valid_from, valid_to=admission.valid_to,
        status="ACTIVE", evidence_ref="evidence://test",
    ))
    db.commit()
    with pytest.raises(ProductionConflict, match="No active corridor admission"):
        corridors.assert_corridor_admitted(
            db, participant_id="SANDBOX-ORIGIN", corridor="CN-HK", scenario="SALARY",
            currency="CNY", amount_minor=100,
        )


def test_simulation_admission_cannot_be_reused_in_pilot(db, monkeypatch):
    admission = _admission("adm-1")
    db.add(admission)
    db.add(ProductionControlAttestation(
        attestation_id="att-1", admission_id="adm-1", signer_role="authority", signer_subject="subject",
        statement_digest="a" * 64, valid_from=admission.valid_from, valid_to=admission.valid_to,
        status="ACTIVE", evidence_ref="evidence://test",
    ))
    db.commit()
    monkeypatch.setattr(corridors, "get_settings", lambda: type("Settings", (), {"swift_env": "pilot", "is_sandbox": False})())
    with pytest.raises(ProductionConflict, match="No active corridor admission"):
        corridors.assert_corridor_admitted(
            db, participant_id="SANDBOX-ORIGIN", corridor="CN-HK", scenario="TRADE",
            currency="CNY", amount_minor=100,
        )
