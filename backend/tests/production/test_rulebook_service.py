import datetime as dt

import pytest

from production.rulebook_service import RulebookError, RulebookService


def test_rulebook_digest_and_window_are_fail_closed():
    class Query:
        def filter_by(self, **_kwargs):
            return self

        def filter(self, *_predicates):
            return self

        def one_or_none(self):
            return None

    class Db:
        def query(self, _model):
            return Query()

    with pytest.raises(RulebookError, match="active participant"):
        RulebookService(Db()).accept(participant_id="p", rulebook_version="v1", document=b"doc", document_digest="0" * 64, accepted_by="s", signer_subject="s", effective_from=dt.datetime.now(dt.UTC), effective_to=None, evidence_ref="e")
