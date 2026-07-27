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
            gl_batch_reference=journal_id,
        )
        self.db.add(journal)
        for item in entries:
            self.db.add(ProductionJournalEntry(entry_id=f"je_{uuid.uuid4().hex}", journal_id=journal_id, **item))
        self.db.flush()
        return journal

    def create_journal_draft(self, *, journal_id: str, legal_entity: str, book: str, reason_code: str, entries: list[dict[str, Any]], order_id: str | None = None) -> ProductionJournal:
        if self.db.query(ProductionJournal).filter_by(journal_id=journal_id).first():
            raise ProductionConflict("Journal id already exists")
        self._validate_entries(entries)
        journal = ProductionJournal(journal_id=journal_id, order_id=order_id, legal_entity=legal_entity, book=book, business_date=dt.date.today().isoformat(), reason_code=reason_code, payload_hash=digest(entries), gl_batch_reference=journal_id, state="DRAFT")
        self.db.add(journal)
        for item in entries:
            self.db.add(ProductionJournalEntry(entry_id=f"je_{uuid.uuid4().hex}", journal_id=journal_id, **item))
        self.db.flush()
        return journal

    def validate_journal(self, journal_id: str) -> ProductionJournal:
        journal = self.db.query(ProductionJournal).filter_by(journal_id=journal_id).with_for_update().one_or_none()
        if journal is None or journal.state not in {"DRAFT", "VALIDATED"}:
            raise ProductionConflict("Journal is not validateable")
        entries = self.db.query(ProductionJournalEntry).filter_by(journal_id=journal_id).all()
        self._validate_entries([{"account_id": item.account_id, "direction": item.direction, "currency": item.currency, "amount_minor": item.amount_minor} for item in entries])
        journal.state = "VALIDATED"
        self.db.flush()
        return journal

    def post_multi_currency(self, *, journal_id: str, legal_entity: str, book: str, reason_code: str, entries: list[dict[str, Any]], fx_clearing_accounts: dict[str, str]) -> list[ProductionJournal]:
        currencies = sorted({entry.get("currency") for entry in entries})
        if len(currencies) < 2:
            raise ProductionConflict("Multi-currency posting requires at least two currencies")
        groups = {currency: [entry for entry in entries if entry.get("currency") == currency] for currency in currencies}
        journals = []
        for currency, group in groups.items():
            clearing = fx_clearing_accounts.get(currency)
            if not clearing:
                raise ProductionConflict(f"FX clearing account required for {currency}")
            if not any(entry.get("account_id") == clearing for entry in group):
                raise ProductionConflict(f"FX clearing leg missing for {currency}")
            self._validate_entries(group)
            journals.append(self.post_journal(journal_id=f"{journal_id}:{currency}", legal_entity=legal_entity, book=book, reason_code=reason_code, entries=group))
        return journals

    def reverse_journal(self, journal_id: str, reversal_journal_id: str, reason: str, approval_ref: str, evidence_ref: str) -> ProductionJournal:
        original = self.db.query(ProductionJournal).filter_by(journal_id=journal_id, state="POSTED").one_or_none()
        if original is None:
            raise ProductionConflict("Only a POSTED journal can be reversed")
        if not reason or not approval_ref or not evidence_ref:
            raise ProductionConflict("Reversal requires reason, approval and evidence")
        entries = self.db.query(ProductionJournalEntry).filter_by(journal_id=journal_id).all()
        reversed_entries = [{"account_id": item.account_id, "direction": "CREDIT" if item.direction == "DEBIT" else "DEBIT", "currency": item.currency, "amount_minor": item.amount_minor} for item in entries]
        reversal = self.post_journal(journal_id=reversal_journal_id, legal_entity=original.legal_entity, book=original.book, reason_code="REVERSAL", entries=reversed_entries, order_id=original.order_id)
        reversal.reverses_journal_id = original.journal_id
        reversal.reversal_reason = reason
        reversal.approval_ref = approval_ref
        reversal.evidence_ref = evidence_ref
        self.db.flush()
        return reversal

    @staticmethod
    def _validate_entries(entries: list[dict[str, Any]]) -> None:
        if len(entries) < 2:
            raise ProductionConflict("A journal requires at least two entries")
        currencies = {entry.get("currency") for entry in entries}
        if len(currencies) != 1:
            raise ProductionConflict("A journal cannot mix currencies")
        debit = sum(int(entry["amount_minor"]) for entry in entries if entry.get("direction") == "DEBIT")
        credit = sum(int(entry["amount_minor"]) for entry in entries if entry.get("direction") == "CREDIT")
        if debit <= 0 or debit != credit:
            raise ProductionConflict("Journal is not balanced")

    def trial_balance(self, currency: str | None = None) -> dict[str, Any]:
        query = self.db.query(ProductionLedgerAccount).filter_by(active=True)
        if currency:
            query = query.filter_by(currency=currency.upper())
        accounts = query.all()
        reconstructed = {account.account_id: 0 for account in accounts}
        entries = self.db.query(ProductionJournalEntry).join(ProductionJournal, ProductionJournal.journal_id == ProductionJournalEntry.journal_id).filter(ProductionJournal.state == "POSTED")
        if currency:
            entries = entries.filter(ProductionJournalEntry.currency == currency.upper())
        for entry in entries.all():
            account = next((item for item in accounts if item.account_id == entry.account_id), None)
            if account is None:
                continue
            normal = NORMAL_BALANCE[account.account_type.lower()]
            reconstructed[account.account_id] += int(entry.amount_minor) if entry.direction == normal else -int(entry.amount_minor)
        return {
            "currency": currency.upper() if currency else None,
            "accounts": [serialize_account(item, balance_minor=reconstructed[item.account_id]) for item in accounts],
            "total_balance_minor": sum(reconstructed.values()),
            "total_reserved_minor": sum(item.reserved_minor for item in accounts),
        }


def serialize_account(account: ProductionLedgerAccount, balance_minor: int | None = None) -> dict[str, Any]:
    balance = account.balance_minor if balance_minor is None else balance_minor
    return {
        "account_id": account.account_id,
        "legal_entity": account.legal_entity,
        "book": account.book,
        "currency": account.currency,
        "account_type": account.account_type,
        "balance_minor": balance,
        "reserved_minor": account.reserved_minor,
        "available_minor": balance - account.reserved_minor,
        "version": account.version,
        "active": account.active,
    }
