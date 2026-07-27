"""Versioned standards/artifact registry and copy/lineage persistence."""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from typing import Any

from config import get_settings

from .models import ProductionFieldLineage, ProductionStandardArtifact, ProductionTransactionCopy
from .runtime import ProductionConflict, ProductionEvidenceService, canonical_json, digest


def list_profiles() -> list[dict[str, str]]:
    return [{"profile": "iso20022-base:2026", "version": "2026.1", "scope": "production"}]


def parse_iso20022_xml(xml: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ProductionConflict("invalid ISO 20022 XML") from exc
    return {"xml_root": root.tag, "raw_xml": xml}


def validate_payload(message_type: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if message_type != "pacs.008":
        findings.append({"severity": "ERROR", "rule_id": "MSG-TYPE", "message": "unsupported production message type"})
    findings.extend(
        {"severity": "ERROR", "rule_id": f"REQ-{section.upper()}", "message": f"{section} is required"}
        for section in ("header", "document")
        if not isinstance(payload.get(section), dict) or not payload[section]
    )
    document = payload.get("document") if isinstance(payload.get("document"), dict) else {}
    findings.extend(
        {"severity": "ERROR", "rule_id": f"REQ-DOCUMENT-{key.upper()}", "message": f"document.{key} is required"}
        for key in ("message_id", "uetr", "amount", "currency")
        if not document.get(key)
    )
    return findings


def ensure_artifact(db, *, profile: str, message_type: str, version: str = "2026.1", simulation_only: bool = True):
    artifact = db.query(ProductionStandardArtifact).filter_by(profile=profile, message_type=message_type, version=version, status="ACTIVE").first()
    if artifact is None:
        artifact = ProductionStandardArtifact(
            artifact_id=f"std_{uuid.uuid4().hex}", profile=profile, message_type=message_type,
            version=version, artifact_kind="SCHEMA_RULESET", digest=digest({"profile": profile, "message_type": message_type, "version": version}),
            source_uri="embedded://sandbox/standards" if simulation_only else "registry://qualified/standards",
            status="ACTIVE", simulation_only=simulation_only,
        )
        db.add(artifact)
        db.flush()
    return artifact


def validate_and_record(db, *, profile: str, message_type: str, payload: dict[str, Any], order_id: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    artifact = db.query(ProductionStandardArtifact).filter_by(profile=profile, message_type=message_type, status="ACTIVE").order_by(ProductionStandardArtifact.id.desc()).first()
    if artifact is None or (not settings.is_sandbox and artifact.simulation_only):
        raise ProductionConflict("Qualified standards artifact is not installed")
    findings = validate_payload(message_type, payload)
    evidence = ProductionEvidenceService(db).record("standards.validation", order_id or f"{profile}:{message_type}", {"artifact_id": artifact.artifact_id, "findings": findings})
    if order_id:
        copy = ProductionTransactionCopy(copy_id=f"copy_{uuid.uuid4().hex}", order_id=order_id, copy_type="ORIGINAL", message_type=message_type, version=artifact.version, payload=canonical_json(payload), payload_hash=digest(payload), source_artifact_id=artifact.artifact_id)
        db.add(copy)
        db.add(ProductionFieldLineage(lineage_id=f"lin_{uuid.uuid4().hex}", order_id=order_id, source_path="document", target_path="ledger.instruction", transform="validated-copy", source_hash=digest(payload)))
    return {"valid": not any(item["severity"].lower() == "error" for item in findings), "findings": findings, "artifact_id": artifact.artifact_id, "evidence_id": evidence.evidence_id}
