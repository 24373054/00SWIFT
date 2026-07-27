import pytest

from production.limit_service import LimitError, LimitService


def test_limit_service_rejects_non_positive_and_exposure_overrun():
    profile = type("Profile", (), {"max_amount_minor": 100, "max_exposure_minor": 150})()
    service = LimitService(object())
    with pytest.raises(LimitError, match="positive"):
        service.assert_amount(profile, 0)
    with pytest.raises(LimitError, match="exposure"):
        service.assert_amount(profile, 100, exposure_minor=100)
