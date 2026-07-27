import datetime as dt
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from production.security import _validate_identity_binding


class _Query:
    def __init__(self, result):
        self.result = result

    def filter_by(self, **_kwargs):
        return self

    def one_or_none(self):
        return self.result


class _Db:
    def __init__(self, *results):
        self.results = iter(results)

    def query(self, _model):
        return _Query(next(self.results))


def test_identity_binding_rejects_environment_and_expired_certificate():
    identity = SimpleNamespace(environment="live", participant_id="p", certificate_fingerprint="fp")
    settings = SimpleNamespace(swift_env="pilot", is_sandbox=False)
    with pytest.raises(HTTPException, match="environment"):
        _validate_identity_binding(_Db(), identity, settings, dt.datetime.now(dt.UTC))
    identity.environment = "pilot"
    participant = SimpleNamespace(participant_id="p", tenant_id="tenant:p")
    certificate = SimpleNamespace(participant_id="p", not_before=dt.datetime.now(dt.UTC) - dt.timedelta(days=2), not_after=dt.datetime.now(dt.UTC) - dt.timedelta(days=1))
    with pytest.raises(HTTPException, match="validity"):
        _validate_identity_binding(_Db(participant, certificate), identity, settings, dt.datetime.now(dt.UTC))
