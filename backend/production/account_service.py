"""Tenant-scoped customer account and ownership lifecycle service."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from .models import ProductionAccount, ProductionAccountOwnership, utcnow


class AccountLifecycleError(ValueError):
    pass


class AccountService:
    def __init__(self, db: Session):
        self.db = db

    def create_account(self, *, account_id: str, tenant_id: str, participant_id: str, account_type: str, currency: str, owner_ref: str) -> ProductionAccount:
        if self.db.query(ProductionAccount).filter_by(account_id=account_id).first():
            raise AccountLifecycleError("account already exists")
        account = ProductionAccount(account_id=account_id[:120], tenant_id=tenant_id, participant_id=participant_id, account_type=account_type[:40], currency=currency.upper()[:3], owner_ref=owner_ref[:160], status="PENDING")
        self.db.add(account)
        self.db.flush()
        return account

    def add_ownership(self, *, account_id: str, participant_id: str, role: str, effective_from: dt.datetime, effective_to: dt.datetime | None, evidence_ref: str | None) -> ProductionAccountOwnership:
        account = self.db.query(ProductionAccount).filter_by(account_id=account_id).one_or_none()
        if account is None or account.participant_id != participant_id:
            raise AccountLifecycleError("account participant mismatch")
        if effective_to is not None and effective_to <= effective_from:
            raise AccountLifecycleError("ownership validity window is invalid")
        ownership = ProductionAccountOwnership(ownership_id=f"own_{uuid.uuid4().hex}", account_id=account_id, participant_id=participant_id, role=role[:30], status="PENDING", effective_from=effective_from, effective_to=effective_to, evidence_ref=evidence_ref)
        self.db.add(ownership)
        self.db.flush()
        return ownership

    def activate(self, account: ProductionAccount, ownership: ProductionAccountOwnership, *, maker: str, checker: str) -> None:
        if maker == checker or account.status != "PENDING" or ownership.status != "PENDING":
            raise AccountLifecycleError("account activation requires pending records and distinct maker/checker")
        account.status = "ACTIVE"
        ownership.status = "ACTIVE"
        self.db.flush()

    def authorize(self, *, account_id: str, tenant_id: str, participant_id: str, now: dt.datetime | None = None) -> ProductionAccount:
        current = now or utcnow()
        account = self.db.query(ProductionAccount).filter_by(account_id=account_id, tenant_id=tenant_id, participant_id=participant_id, status="ACTIVE").one_or_none()
        if account is None:
            raise AccountLifecycleError("active account is not authorized for tenant/participant")
        ownership = self.db.query(ProductionAccountOwnership).filter(ProductionAccountOwnership.account_id == account_id, ProductionAccountOwnership.participant_id == participant_id, ProductionAccountOwnership.status == "ACTIVE", ProductionAccountOwnership.effective_from <= current, (ProductionAccountOwnership.effective_to.is_(None) | (ProductionAccountOwnership.effective_to >= current))).first()
        if ownership is None:
            raise AccountLifecycleError("active ownership is required")
        return account
