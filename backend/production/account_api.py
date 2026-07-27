from __future__ import annotations

import datetime as dt

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db

from .account_service import AccountLifecycleError, AccountService
from .models import ProductionAccount
from .security import ProductionPrincipal, require_production_scope


class AccountCreate(BaseModel):
    account_id: str = Field(min_length=2, max_length=120)
    tenant_id: str
    participant_id: str
    account_type: str
    currency: str = Field(min_length=3, max_length=3)
    owner_ref: str


class OwnershipCreate(BaseModel):
    participant_id: str
    role: str
    effective_from: dt.datetime
    effective_to: dt.datetime | None = None
    evidence_ref: str | None = None


class AccountActivation(BaseModel):
    ownership_id: str
    checker: str


def _admin():
    return require_production_scope("production.admin")


def create_account(request: AccountCreate, principal: ProductionPrincipal = Depends(_admin()), db: Session = Depends(get_db)):
    try:
        account = AccountService(db).create_account(**request.model_dump())
        db.commit()
        return {"account_id": account.account_id, "tenant_id": account.tenant_id, "participant_id": account.participant_id, "status": account.status}
    except AccountLifecycleError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


def create_ownership(account_id: str, request: OwnershipCreate, principal: ProductionPrincipal = Depends(_admin()), db: Session = Depends(get_db)):
    try:
        ownership = AccountService(db).add_ownership(account_id=account_id, **request.model_dump())
        db.commit()
        return {"ownership_id": ownership.ownership_id, "account_id": ownership.account_id, "status": ownership.status}
    except AccountLifecycleError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


def activate_account(account_id: str, request: AccountActivation, principal: ProductionPrincipal = Depends(_admin()), db: Session = Depends(get_db)):
    try:
        account = db.query(ProductionAccount).filter_by(account_id=account_id).one_or_none()
        if account is None:
            raise AccountLifecycleError("account not found")
        from .models import ProductionAccountOwnership
        ownership = db.query(ProductionAccountOwnership).filter_by(ownership_id=request.ownership_id, account_id=account_id).one_or_none()
        if ownership is None:
            raise AccountLifecycleError("ownership not found")
        AccountService(db).activate(account, ownership, maker=principal.subject, checker=request.checker)
        db.commit()
        return {"account_id": account.account_id, "ownership_id": ownership.ownership_id, "status": account.status}
    except AccountLifecycleError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
