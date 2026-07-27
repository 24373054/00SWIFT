import datetime as dt

import pytest

from production.certificate_service import CertificateLifecycleError, CertificateService


def test_rotation_requires_distinct_dual_control_and_valid_overlap():
    class Query:
        def filter_by(self, **_kwargs):
            return self

        def one_or_none(self):
            return None

    class Db:
        def query(self, _model):
            return Query()

        def flush(self):
            return None

    with pytest.raises(CertificateLifecycleError, match="active certificate"):
        CertificateService(Db()).rotate("old", fingerprint="new", serial_number="s", issuer="i", not_before=dt.datetime.now(dt.UTC), not_after=dt.datetime.now(dt.UTC) + dt.timedelta(days=1), overlap_until=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1), maker="a", checker="b")


def test_refresh_rejects_untrusted_provider_status():
    class Query:
        def filter(self, *_predicates):
            return self

        def all(self):
            return [type("Certificate", (), {"fingerprint": "fp", "not_after": dt.datetime.now(dt.UTC) + dt.timedelta(days=1)})()]

    class Db:
        def query(self, _model):
            return Query()

        def flush(self):
            return None

    with pytest.raises(CertificateLifecycleError, match="invalid status"):
        CertificateService(Db()).refresh_external_status(checker=lambda _fingerprint: "BAD")
