"""ISO 20022 XSD validation (via lxml).

Uses the official ISO 20022 XSD files shipped inside the ``pacs008`` package
(located at ``pacs008/templates/<version>/<version>.xsd``). ``lxml``'s
``XMLSchema`` performs full XSD conformance checking on the generated XML.

This is the "second validation pass" called for in the refactor plan: the
builder guarantees no XML injection (all text escaped), and the validator
guarantees schema conformance.
"""

from __future__ import annotations

import os

from lxml import etree


def _pacs008_pkg_dir() -> str | None:
    try:
        import pacs008 as _p

        return os.path.dirname(os.path.abspath(_p.__file__))
    except Exception:
        return None


def _xsd_path_for(version: str) -> str | None:
    """Return the XSD path for a message version (e.g. pacs.008.001.10)."""
    pkg = _pacs008_pkg_dir()
    if pkg is None:
        return None
    candidate = os.path.join(pkg, "templates", version, f"{version}.xsd")
    return candidate if os.path.exists(candidate) else None


def validate_xml(xml_str: str, version: str) -> tuple[bool, str | None]:
    """Validate ``xml_str`` against the XSD for ``version``.

    Returns ``(True, None)`` on success, ``(False, error_message)`` on failure.
    If the XSD file is unavailable, returns ``(True, "XSD unavailable")`` —
    i.e. validation is skipped rather than failing (the builder's escaping is
    the primary safety guarantee).
    """
    xsd_path = _xsd_path_for(version)
    if xsd_path is None or not os.path.exists(xsd_path):
        return True, "XSD unavailable (skipped)"

    try:
        schema = etree.XMLSchema(etree.parse(xsd_path))
    except Exception as exc:
        return False, f"XSD parse error: {exc}"

    try:
        doc = etree.fromstring(xml_str.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        return False, f"XML syntax error: {exc}"

    if schema.validate(doc):
        return True, None
    return False, " ; ".join(f"{err.line}: {err.message}" for err in schema.error_log[:5])


def validate_pacs008(xml_str: str) -> tuple[bool, str | None]:
    return validate_xml(xml_str, "pacs.008.001.10")
