import pytest

from production.funding_service import FundingService
from production.models import ProductionLiabilityProfile
from production.runtime import ProductionConflict


def test_funding_service_requires_active_liability_profile(db):
    service = FundingService(db)
    with pytest.raises(ProductionConflict, match="liability profile"):
        service.assert_liability_profile("missing")
    db.add(ProductionLiabilityProfile(profile_id="lp-1", operator_id="op-1", operator_type="PLATFORM", liability_type="MIRROR", jurisdiction="CN", active=True))
    db.commit()
    assert service.assert_liability_profile("lp-1").liability_type == "MIRROR"
