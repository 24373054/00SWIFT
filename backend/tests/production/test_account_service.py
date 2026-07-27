import datetime as dt

import pytest

from production.account_service import AccountLifecycleError, AccountService


def test_account_service_requires_active_ownership_for_authorization():
    class Query:
        def filter_by(self, **_kwargs):
            return self

        def filter(self, *_predicates):
            return self

        def first(self):
            return None

        def one_or_none(self):
            return None

    class Db:
        def query(self, _model):
            return Query()

    with pytest.raises(AccountLifecycleError, match="authorized"):
        AccountService(Db()).authorize(account_id="a", tenant_id="tenant:a", participant_id="p", now=dt.datetime.now(dt.UTC))
