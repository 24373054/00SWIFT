import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database import Base
from production.identity_service import IdentityLifecycleError, IdentityService


def test_identity_bootstrap_is_pending_and_activation_is_dual_control(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'identity.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        service = IdentityService(db)
        tenant = service.bootstrap_tenant(tenant_id="tenant-a", name="A", jurisdiction="CN", data_region="cn", actor="maker")
        assert tenant.status == "PENDING"
        with pytest.raises(IdentityLifecycleError, match="active tenant"):
            service.create_participant(participant_id="p-a", tenant_id="tenant-a", name="A", participant_type="BANK", jurisdiction="CN")
        service.transition(tenant, "ACTIVE", maker="alice", checker="bob")
        participant = service.create_participant(participant_id="p-a", tenant_id="tenant-a", name="A", participant_type="BANK", jurisdiction="CN")
        assert participant.status == "PENDING"
        with pytest.raises(IdentityLifecycleError, match="distinct"):
            service.transition(participant, "ACTIVE", maker="alice", checker="alice")
