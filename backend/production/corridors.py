"""Default-deny corridor admission checks for payment creation."""

from __future__ import annotations

import datetime as dt
import json

from config import get_settings

from .models import ProductionControlAttestation, ProductionCorridorAdmission, utcnow
from .runtime import ProductionConflict


def _contains(serialized: str, value: str) -> bool:
    try:
        values = json.loads(serialized or "[]")
    except json.JSONDecodeError as exc:
        raise ProductionConflict("Corridor admission contains invalid policy JSON") from exc
    return "*" in values or value in values


def assert_corridor_admitted(
    db,
    *,
    participant_id: str,
    corridor: str,
    scenario: str,
    currency: str,
    amount_minor: int,
    now: dt.datetime | None = None,
):
    settings = get_settings()
    current = (now or utcnow()).astimezone(dt.UTC)
    admissions = db.query(ProductionCorridorAdmission).filter_by(
        environment=settings.swift_env, corridor=corridor, status="ACTIVE"
    ).all()
    for admission in admissions:
        valid_from = admission.valid_from.replace(tzinfo=dt.UTC)
        valid_to = admission.valid_to.replace(tzinfo=dt.UTC)
        if not valid_from <= current <= valid_to:
            continue
        if not settings.is_sandbox and admission.simulation_only:
            continue
        if not _contains(admission.applicable_subjects, participant_id):
            continue
        if not _contains(admission.scenarios, scenario):
            continue
        if not _contains(admission.currencies, currency):
            continue
        if not admission.min_amount_minor <= amount_minor <= admission.max_amount_minor:
            continue
        attestations = db.query(ProductionControlAttestation).filter_by(
            admission_id=admission.admission_id, status="ACTIVE"
        ).all()
        if not any(attestation.valid_from.replace(tzinfo=dt.UTC) <= current <= attestation.valid_to.replace(tzinfo=dt.UTC) for attestation in attestations):
            continue
        return admission
    raise ProductionConflict(
        f"No active corridor admission for environment={settings.swift_env}, corridor={corridor}, scenario={scenario}, currency={currency}"
    )
