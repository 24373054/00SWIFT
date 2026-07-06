"""SwiftRef API router — mounted at /swiftrefdata/v4.

P1 GET endpoints aligned with the v4.0.0 swagger. All require a bearer token
with the ``swift.swiftref`` (or wildcard ``swift.api``) scope.

Live-mode forwarding is deferred — the mock tier covers the sandbox use case.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.dependencies import get_cred, require_scopes
from database import get_db
from api.swiftref import repository

router = APIRouter(
    prefix="/swiftrefdata/v4",
    tags=["SwiftRef"],
    dependencies=[Depends(get_cred), Depends(require_scopes("swift.swiftref"))],
)


@router.get("/bics/{bic}/validity")
def get_bic_validity(bic: str, db: Session = Depends(get_db)):
    return repository.lookup_bic_validity(db, bic)


@router.get("/bics/{bic}")
def get_bic_details(bic: str, db: Session = Depends(get_db)):
    return repository.lookup_bic_details(db, bic)


@router.get("/ibans/{iban}/validity")
def get_iban_validity(iban: str, db: Session = Depends(get_db)):
    return repository.lookup_iban_validity(db, iban)


@router.get("/ibans/{iban}/bic")
def get_iban_bic(iban: str, db: Session = Depends(get_db)):
    return repository.lookup_iban_bic(db, iban)


@router.get("/ibans/{iban}")
def get_iban_details(iban: str, db: Session = Depends(get_db)):
    return repository.lookup_iban_details(db, iban)


@router.get("/currency_codes/{currency_code}/validity")
def get_currency_validity(currency_code: str, db: Session = Depends(get_db)):
    return repository.lookup_currency_validity(db, currency_code)


@router.get("/currency_codes/{currency_code}")
def get_currency_details(currency_code: str, db: Session = Depends(get_db)):
    return repository.lookup_currency_details(db, currency_code)
