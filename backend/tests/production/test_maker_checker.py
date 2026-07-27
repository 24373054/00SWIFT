import pytest
from fastapi import HTTPException

from production.approval_api import (
    ApprovalCreateRequest,
    ApprovalDecisionRequest,
    create_pending_approval,
    decide_approval,
)
from production.models import ProductionApproval
from production.security import ProductionPrincipal


class _Query:
    def __init__(self, value):
        self.value = value

    def filter_by(self, **_kwargs):
        if self.value is not None and any(getattr(self.value, key, object()) != value for key, value in _kwargs.items()):
            self.value = None
        return self

    def one_or_none(self):
        return self.value


class _Db:
    def __init__(self, approval):
        self.approval = approval

    def query(self, _model):
        return _Query(self.approval)

    def add(self, _item):
        return None

    def commit(self):
        return None


def _principal(subject: str, credential_id: int | None) -> ProductionPrincipal:
    return ProductionPrincipal("P1", subject, frozenset({"production.admin"}), "oauth-service-identity", credential_id)


def test_maker_cannot_decide_and_expired_or_duplicate_is_not_pending():
    approval = ProductionApproval(approval_id="apr-1", aggregate_type="PAYMENT", aggregate_id="p", action="RELEASE", maker="alice", maker_credential_id=10, state="PENDING", reason="r")
    with pytest.raises(HTTPException, match="distinct"):
        decide_approval("apr-1", ApprovalDecisionRequest(reason="self"), _principal("alice", 10), _Db(approval))
    approval.maker = "alice-human"
    with pytest.raises(HTTPException, match="credentials"):
        decide_approval("apr-1", ApprovalDecisionRequest(reason="credential swap"), _principal("alice-service", 10), _Db(approval))
    approval.state = "EXPIRED"
    with pytest.raises(HTTPException) as exc:
        decide_approval("apr-1", ApprovalDecisionRequest(reason="late"), _principal("bob", 11), _Db(approval))
    assert exc.value.status_code == 404


def test_create_ignores_forged_maker_and_duplicate_decision_is_not_pending():
    request = ApprovalCreateRequest(aggregate_type="PAYMENT", aggregate_id="p", action="RELEASE", reason="r")
    result = create_pending_approval(request, _principal("alice", 10), _Db(None))
    assert result["maker"] == "alice"
    approval = ProductionApproval(approval_id="apr-2", aggregate_type="PAYMENT", aggregate_id="p", action="RELEASE", maker="alice", state="APPROVED", reason="r")
    with pytest.raises(HTTPException) as exc:
        decide_approval("apr-2", ApprovalDecisionRequest(reason="duplicate"), _principal("bob", 11), _Db(approval))
    assert exc.value.status_code == 404


def test_decision_request_has_no_maker_or_checker_fields():
    assert "maker" not in ApprovalDecisionRequest.model_fields
    assert "checker" not in ApprovalDecisionRequest.model_fields
