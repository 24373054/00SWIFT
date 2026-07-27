from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import production.security as security


def test_role_subject_and_participant_headers_are_rejected_outside_sandbox(monkeypatch):
    monkeypatch.setattr(security, "get_settings", lambda: SimpleNamespace(is_sandbox=False, production_require_auth=False))
    with pytest.raises(HTTPException) as exc:
        security.get_production_principal(
            authorization=None,
            participant_header="attacker",
            user_role_header="admin",
            user_subject_header="attacker-subject",
            credential=None,
            db=None,
        )
    assert exc.value.status_code == 403


def test_sandbox_identity_is_explicitly_labelled():
    principal = security._sandbox_principal("SANDBOX-ORIGIN")
    assert principal.source == "sandbox-explicit-header"
    assert principal.subject == "sandbox-participant"
