import datetime as dt

import pytest

from production.limit_reservation import LimitReservationError, LimitReservationService


def test_reservation_rejects_non_positive_amount_without_writing():
    with pytest.raises(LimitReservationError, match="positive"):
        LimitReservationService(object()).reserve(tenant_id="t", participant_id="p", service="payment.create", corridor="CN-HK", currency="CNY", business_date=dt.date.today(), amount_minor=0, daily_limit_minor=100, exposure_limit_minor=100)
