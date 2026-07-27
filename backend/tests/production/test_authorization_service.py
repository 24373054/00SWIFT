import pytest

from production.authorization_service import AuthorizationError, AuthorizationService


def test_authorization_requires_matching_approved_objects():
    class Query:
        def filter_by(self, **_kwargs):
            return self

        def one_or_none(self):
            return None

    class Db:
        def query(self, _model):
            return Query()

    with pytest.raises(AuthorizationError, match="mandate"):
        AuthorizationService(Db()).validate_mandate(principal_id="p", tenant_id="t", account_id="a", debtor_ref="d", amount_minor=1, currency="CNY", purpose_code="TRADE", mandate_id="m", payment_hash="h")
