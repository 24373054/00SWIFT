"""Double-entry subledger and reservation primitives for production flows."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy.orm import Session

from .models import (
    ProductionFundingReservation,
    ProductionJournal,
    ProductionJournalEntry,
    ProductionLedgerAccount,
)
from .runtime import ProductionConflict, digest

NORMAL_BALANCE = {
    "asset": "DEBIT",
    "expense": "DEBIT",
    "liability": "CREDIT",
    "equity": "CREDIT",
    "income": "CREDIT",
    "contra": "CREDIT",
    "suspense": "DEBIT",
}


class ProductionLedgerService:
    def __init__(self, db: Session):
        self.db = db

    def create_account(self, account_id: str, legal_entity: str, book: str, currency: str, account_type: str, opening_balance_minor: int = 0) -> ProductionLedgerAccount:
        if opening_balance_minor < 0:
            raise ProductionConflict("Opening balance cannot be negative")
        account_type = account_type.lower()
        if account_type not in NORMAL_BALANCE:
            raise ProductionConflict(f"Unsupported account type: {account_type}")
        if self.db.query(ProductionLedgerAccount).filter_by(account_id=account_id).first():
            raise ProductionConflict("Ledger account already exists")
        account = ProductionLedgerAccount(
            account_id=account_id,
            legal_entity=legal_entity,
            book=book,
            currency=currency,
            account_type=account_type,
            balance_minor=opening_balance_minor,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def reserve(self, account_id: str, reservation_id: str, amount_minor: int, currency: str) -> ProductionFundingReservation:
        account = self.db.query(ProductionLedgerAccount).filter_by(account_id=account_id, active=True).with_for_update().one_or_none()
        if account is None or account.currency != currency:
            raise ProductionConflict("Funding ledger account is unavailable")
        current = self.db.query(ProductionFundingReservation).filter_by(reservation_id=reservation_id).first()
        if current is not None:
            return current
        available = account.balance_minor - account.reserved_minor
        if amount_minor <= 0 or available < amount_minor:
            raise ProductionConflict("Insufficient available funds")
        account.reserved_minor += amount_minor
        reservation = ProductionFundingReservation(
            reservation_id=reservation_id,
            reservation_intent_id=f"ledger-{reservation_id}",
            order_id=f"ledger:{reservation_id}",
            funding_reference=account_id,
            currency=currency,
            amount_minor=amount_minor,
            state="RESERVED",
        )
        self.db.add(reservation)
        self.db.flush()
        return reservation

    def release(self, reservation_id: str) -> ProductionFundingReservation:
        reservation = self.db.query(ProductionFundingReservation).filter_by(reservation_id=reservation_id).with_for_update().one()
        if reservation.state != "RESERVED":
            return reservation
        account = self.db.query(ProductionLedgerAccount).filter_by(account_id=reservation.funding_reference).with_for_update().one()
        account.reserved_minor = max(0, account.reserved_minor - reservation.amount_minor)
        reservation.state = "RELEASED"
        self.db.flush()
        return reservation

    def consume(self, reservation_id: str) -> ProductionFundingReservation:
        reservation = self.db.query(ProductionFundingReservation).filter_by(reservation_id=reservation_id).with_for_update().one()
        if reservation.state != "RESERVED":
            return reservation
        account = self.db.query(ProductionLedgerAccount).filter_by(account_id=reservation.funding_reference).with_for_update().one()
        account.reserved_minor = max(0, account.reserved_minor - reservation.amount_minor)
        account.balance_minor -= reservation.amount_minor
        reservation.state = "CONSUMED"
        self.db.flush()
        return reservation

    def post_journal(self, *, journal_id: str, legal_entity: str, book: str, reason_code: str, entries: list[dict[str, Any]], order_id: str | None = None) -> ProductionJournal:
        if len(entries) < 2:
            raise ProductionConflict("A journal requires at least two entries")
        currencies = {entry.get("currency") for entry in entries}
        if len(currencies) != 1:
            raise ProductionConflict("A journal cannot mix currencies")
        debit = sum(int(entry["amount_minor"]) for entry in entries if entry.get("direction") == "DEBIT")
        credit = sum(int(entry["amount_minor"]) for entry in entries if entry.get("direction") == "CREDIT")
        if debit <= 0 or debit != credit:
            raise ProductionConflict("Journal is not balanced")
        if self.db.query(ProductionJournal).filter_by(journal_id=journal_id).first():
            raise ProductionConflict("Journal id already exists")
        locked_accounts = {}
        for entry in entries:
            if int(entry["amount_minor"]) <= 0 or entry.get("direction") not in {"DEBIT", "CREDIT"}:
                raise ProductionConflict("Invalid journal entry")
            account = self.db.query(ProductionLedgerAccount).filter_by(account_id=entry["account_id"], active=True).with_for_update().one_or_none()
            if account is None:
                raise ProductionConflict(f"Unknown ledger account: {entry['account_id']}")
            if account.currency != next(iter(currencies)):
                raise ProductionConflict("Journal entry currency does not match account")
            locked_accounts[account.account_id] = account
        for entry in entries:
            account = locked_accounts[entry["account_id"]]
            normal = NORMAL_BALANCE[account.account_type.lower()]
            delta = int(entry["amount_minor"]) if entry["direction"] == normal else -int(entry["amount_minor"])
            if account.balance_minor + delta < 0:
                raise ProductionConflict(f"Ledger account would become negative: {account.account_id}")
            account.balance_minor += delta
            account.version += 1
        journal = ProductionJournal(
            journal_id=journal_id,
            order_id=order_id,
            legal_entity=legal_entity,
            book=book,
            business_date=dt.date.today().isoformat(),
            reason_code=reason_code,
            payload_hash=digest(entries),
        )
        self.db.add(journal)
        for item in entries:
            self.db.add(ProductionJournalEntry(entry_id=f"je_{uuid.uuid4().hex}", journal_id=journal_id, **item))
        self.db.flush()
        return journal

    def trial_balance(self, currency: str | None = None) -> dict[str, Any]:
        query = self.db.query(ProductionLedgerAccount).filter_by(active=True)
        if currency:
            query = query.filter_by(currency=currency.upper())
        accounts = query.all()
        return {
            "currency": currency.upper() if currency else None,
            "accounts": [serialize_account(item) for item in accounts],
            "total_balance_minor": sum(item.balance_minor for item in accounts),
            "total_reserved_minor": sum(item.reserved_minor for item in accounts),
        }


def serialize_account(account: ProductionLedgerAccount) -> dict[str, Any]:
    return {
        "account_id": account.account_id,
        "legal_entity": account.legal_entity,
        "book": account.book,
        "currency": account.currency,
        "account_type": account.account_type,
        "balance_minor": account.balance_minor,
        "reserved_minor": account.reserved_minor,
        "available_minor": account.balance_minor - account.reserved_minor,
        "version": account.version,
        "active": account.active,
    }
