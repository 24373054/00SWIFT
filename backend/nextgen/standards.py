"""Versioned ISO 20022, CBPR+ and CIPS profile validation."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable
from xml.etree import ElementTree

SUPPORTED_MESSAGE_TYPES = {
    "pacs.008",
    "pacs.009",
    "pacs.002",
    "pacs.004",
    "camt.056",
    "camt.029",
    "camt.110",
    "camt.111",
    "admi.024",
}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    message_type: str
    path: str
    operator: str
    expected: Any = None
    severity: str = "error"
    description: str = ""


@dataclass(frozen=True)
class Profile:
    name: str
    version: str
    effective_from: str
    description: str
    rules: tuple[Rule, ...]

    @property
    def key(self) -> str:
        return f"{self.name}:{self.version}"


@dataclass(frozen=True)
class Finding:
    profile: str
    rule_id: str
    message_type: str
    path: str
    severity: str
    text: str


BASE_RULES = (
    Rule("ISO-MSG-001", "*", "message_type", "in", sorted(SUPPORTED_MESSAGE_TYPES)),
    Rule("ISO-ID-001", "*", "header.biz_msg_id", "required"),
    Rule("ISO-ID-002", "*", "document.message_id", "required"),
    Rule("ISO-BAH-001", "*", "header.message_definition", "matches_message_type"),
    Rule("ISO-BAH-002", "*", "header.sender", "required"),
    Rule("ISO-BAH-003", "*", "header.receiver", "required"),
    Rule("ISO-UETR-001", "pacs.008", "document.uetr", "uuid4"),
    Rule("ISO-UETR-002", "pacs.009", "document.uetr", "uuid4"),
    Rule("ISO-AMT-001", "pacs.008", "document.amount", "positive_decimal"),
    Rule("ISO-AMT-002", "pacs.009", "document.amount", "positive_decimal"),
    Rule("ISO-CCY-001", "pacs.008", "document.currency", "currency"),
    Rule("ISO-CCY-002", "pacs.009", "document.currency", "currency"),
)
CBPR_2025_RULES = BASE_RULES + (
    Rule("CBPR-ADDR-2025", "pacs.008", "document.creditor.address", "address_any", severity="warning"),
)
CBPR_2026_RULES = BASE_RULES + (
    Rule("CBPR-ADDR-2026-D", "pacs.008", "document.debtor.address", "structured_or_hybrid"),
    Rule("CBPR-ADDR-2026-C", "pacs.008", "document.creditor.address", "structured_or_hybrid"),
    Rule("CBPR-BAH-2026", "*", "header.business_service", "required"),
)
CIPS_2026_RULES = BASE_RULES + (
    Rule("CIPS-PART-001", "*", "header.sender", "bic_or_cips"),
    Rule("CIPS-PART-002", "*", "header.receiver", "bic_or_cips"),
    Rule("CIPS-CNY-001", "pacs.008", "document.currency", "equals", "CNY"),
    Rule("CIPS-CNY-002", "pacs.009", "document.currency", "equals", "CNY"),
)
PROFILES = {
    "iso20022-base:2026": Profile("iso20022-base", "2026", "2026-01-01", "Base behavioral subset", BASE_RULES),
    "cbpr-plus:2025": Profile("cbpr-plus", "2025", "2025-01-01", "Pre-SR2026 sandbox profile", CBPR_2025_RULES),
    "cbpr-plus:sr2026": Profile("cbpr-plus", "sr2026", "2026-11-14", "SR2026 structured/hybrid address profile", CBPR_2026_RULES),
    "cips:2026": Profile("cips", "2026", "2026-01-01", "CIPS research profile; not an official implementation guide", CIPS_2026_RULES),
}
_UUID4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_BIC = re.compile(r"^[A-Z0-9]{8}([A-Z0-9]{3})?$")
_CIPS = re.compile(r"^CIPS-[A-Z0-9]{4,24}$")


def list_profiles(as_of: dt.date | None = None) -> list[dict[str, Any]]:
    cutoff = as_of or dt.date.max
    return [
        {
            "key": profile.key,
            "name": profile.name,
            "version": profile.version,
            "effective_from": profile.effective_from,
            "description": profile.description,
            "rule_count": len(profile.rules),
        }
        for profile in PROFILES.values()
        if dt.date.fromisoformat(profile.effective_from) <= cutoff
    ]


def get_profile(key: str) -> Profile:
    try:
        return PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown standards profile: {key}") from exc


def _get(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def classify_address(value: Any) -> str:
    if not isinstance(value, dict):
        return "missing"
    lines = value.get("address_lines") or []
    structured = any(value.get(key) for key in ("town", "country", "post_code", "street", "building_number"))
    if structured and lines:
        return "hybrid"
    if structured:
        return "structured"
    if lines:
        return "unstructured"
    return "missing"


def _passes(operator: str, value: Any, expected: Any, message_type: str) -> bool:
    if operator == "required":
        return value not in (None, "", [], {})
    if operator == "in":
        return value in expected
    if operator == "equals":
        return value == expected
    if operator == "matches_message_type":
        return value == message_type
    if operator == "uuid4":
        return isinstance(value, str) and bool(_UUID4.fullmatch(value))
    if operator == "positive_decimal":
        try:
            number = float(value)
            return number > 0 and number not in {float("inf"), float("-inf")}
        except (TypeError, ValueError):
            return False
    if operator == "currency":
        return isinstance(value, str) and bool(_CURRENCY.fullmatch(value))
    if operator == "address_any":
        return classify_address(value) != "missing"
    if operator == "structured_or_hybrid":
        return classify_address(value) in {"structured", "hybrid"}
    if operator == "bic_or_cips":
        return isinstance(value, str) and bool(_BIC.fullmatch(value) or _CIPS.fullmatch(value))
    raise ValueError(f"Unsupported validation operator: {operator}")


def validate_message(profile_key: str, message_type: str, payload: dict[str, Any]) -> list[Finding]:
    profile = get_profile(profile_key)
    envelope = copy.deepcopy(payload)
    envelope.setdefault("message_type", message_type)
    findings: list[Finding] = []
    for rule in profile.rules:
        if rule.message_type not in {"*", message_type}:
            continue
        if not _passes(rule.operator, _get(envelope, rule.path), rule.expected, message_type):
            findings.append(
                Finding(
                    profile.key,
                    rule.rule_id,
                    message_type,
                    rule.path,
                    rule.severity,
                    rule.description or f"Rule {rule.rule_id} failed",
                )
            )
    return findings


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_iso20022_xml(xml_text: str) -> dict[str, Any]:
    if "<!DOCTYPE" in xml_text.upper() or "<!ENTITY" in xml_text.upper():
        raise ValueError("DTD and entity declarations are forbidden")
    root = ElementTree.fromstring(xml_text)
    values: dict[str, list[str]] = {}
    for element in root.iter():
        text = (element.text or "").strip()
        if text:
            values.setdefault(_local_name(element.tag), []).append(text)
    message_type = root.attrib.get("messageType") or values.get("MsgDefIdr", [""])[0]
    return {
        "message_type": message_type,
        "header": {
            "biz_msg_id": values.get("BizMsgIdr", [None])[0],
            "message_definition": values.get("MsgDefIdr", [message_type])[0],
            "business_service": values.get("BizSvc", [None])[0],
            "sender": values.get("Fr", [None])[0],
            "receiver": values.get("To", [None])[0],
        },
        "document": {
            "message_id": values.get("MsgId", [None])[0],
            "uetr": values.get("UETR", [None])[0],
            "amount": values.get("IntrBkSttlmAmt", values.get("InstdAmt", [None]))[0],
            "currency": values.get("Ccy", [None])[0],
        },
    }


def build_iso20022_xml(message_type: str, payload: dict[str, Any]) -> str:
    if message_type not in SUPPORTED_MESSAGE_TYPES:
        raise ValueError(f"Unsupported message type: {message_type}")
    root = ElementTree.Element("ISO20022Envelope", {"messageType": message_type})
    app = ElementTree.SubElement(root, "AppHdr")
    header = payload.get("header", {})
    for tag, key in (("BizMsgIdr", "biz_msg_id"), ("MsgDefIdr", "message_definition"), ("BizSvc", "business_service"), ("Fr", "sender"), ("To", "receiver")):
        if header.get(key) is not None:
            ElementTree.SubElement(app, tag).text = str(header[key])
    document_element = ElementTree.SubElement(root, "Document")
    document = payload.get("document", {})
    for tag, key in (("MsgId", "message_id"), ("UETR", "uetr"), ("IntrBkSttlmAmt", "amount"), ("Ccy", "currency")):
        if document.get(key) is not None:
            ElementTree.SubElement(document_element, tag).text = str(document[key])
    return ElementTree.tostring(root, encoding="unicode")


def conformance_digest(vector: dict[str, Any]) -> str:
    encoded = json.dumps(vector, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def run_conformance(vectors: Iterable[dict[str, Any]]) -> dict[str, Any]:
    results = []
    passed = 0
    for vector in vectors:
        findings = validate_message(vector["profile"], vector["message_type"], vector["payload"])
        actual_valid = not any(item.severity == "error" for item in findings)
        expected_valid = bool(vector["expected_valid"])
        ok = actual_valid == expected_valid
        passed += int(ok)
        results.append(
            {
                "name": vector["name"],
                "passed": ok,
                "actual_valid": actual_valid,
                "finding_ids": [item.rule_id for item in findings],
                "digest": conformance_digest(vector),
            }
        )
    total = len(results)
    return {"total": total, "passed": passed, "failed": total - passed, "results": results}


def finding_dicts(findings: Iterable[Finding]) -> list[dict[str, Any]]:
    return [asdict(item) for item in findings]
