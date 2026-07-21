"""SwiftRef data repository: mock (DB lookup) or live (httpx forward).

The mock tier queries the seeded ``SwiftRefBic/Iban/Currency/Country`` tables.
The live tier forwards to the real ``/swiftrefdata/v4`` host configured in
``Settings.live_host_swiftref``.
"""

from __future__ import annotations

import json

from core.bic import validate_bic
from core.errors import swiftref_invalid, swiftref_not_found
from core.iban import parse_iban, validate_iban
from database import (
    SwiftRefBic,
    SwiftRefCurrency,
    SwiftRefIban,
)

# REDA.API.* error codes from the SwiftRef swagger.
_ERR_BIC_FORMAT = "REDA.API.IBIC"  # invalid BIC format
_ERR_BIC_NOT_FOUND = "REDA.API.BINF"  # BIC not in directory
_ERR_IBAN_FORMAT = "REDA.API.IINP"  # invalid IBAN format (no data)
_ERR_IBAN_NOT_FOUND = "REDA.API.IBNF"  # IBAN not found
_ERR_CUR_FORMAT = "REDA.API.ICTP"  # invalid currency code
_ERR_CUR_NOT_FOUND = "REDA.API.CUNF"  # currency not found


def _get_bic(db, bic: str) -> SwiftRefBic | None:
    """Look up a BIC. Tries the exact form first, then 8-char prefix of an 11-char BIC."""
    upper = bic.upper()
    row = db.query(SwiftRefBic).filter(SwiftRefBic.bic == upper).first()
    if row is None and len(upper) == 11:
        row = db.query(SwiftRefBic).filter(SwiftRefBic.bic == upper[:8]).first()
    return row


def lookup_bic_validity(db, bic: str) -> dict:
    if not validate_bic(bic, mode="data"):
        raise swiftref_invalid(_ERR_BIC_FORMAT, f"BIC {bic} has invalid format")
    row = _get_bic(db, bic)
    if row is None:
        raise swiftref_not_found(_ERR_BIC_NOT_FOUND, f"BIC {bic.upper()} not found in directory")
    return {"bic": row.bic, "validity": "VBIC", "effective_date": None}


def lookup_bic_details(db, bic: str) -> dict:
    if not validate_bic(bic, mode="data"):
        raise swiftref_invalid(_ERR_BIC_FORMAT, f"BIC {bic} has invalid format")
    row = _get_bic(db, bic)
    if row is None:
        raise swiftref_not_found(_ERR_BIC_NOT_FOUND, f"BIC {bic.upper()} not found in directory")
    return {
        "bic": row.bic,
        "office_type": row.office_type,
        "name": row.name,
        "country_code": row.country_code,
        "town_name": row.town_name,
        "post_code": row.post_code,
        "address_line": row.address_line,
        "swift_connectivity": json.loads(row.swift_connectivity or "{}"),
        "connected_bic": row.connected_bic,
        "utc_offset": row.utc_offset,
    }


def lookup_iban_validity(db, iban: str) -> dict:
    cleaned = (iban or "").upper().replace(" ", "")
    if not cleaned or not cleaned[0:2].isalpha() or not cleaned[2:4].isdigit():
        raise swiftref_invalid(_ERR_IBAN_FORMAT, f"IBAN {iban} has invalid format")
    # First check the structure (mod-97 + country BBAN).
    structurally_valid = validate_iban(cleaned)
    # Then check the directory (known IBAN -> BIC map).
    row = db.query(SwiftRefIban).filter(SwiftRefIban.iban == cleaned).first()
    if row is not None:
        validity = "VIBN" if row.valid and structurally_valid else "IVAL"
        return {"iban": cleaned, "validity": validity}
    # Not in directory: return validity based on structural check alone.
    if not structurally_valid:
        return {"iban": cleaned, "validity": "IVAL"}
    # Structurally valid but unknown to the directory — SwiftRef returns IVAL
    # (cannot confirm the bank exists). This is a fidelity choice.
    return {"iban": cleaned, "validity": "IVAL"}


def lookup_iban_bic(db, iban: str) -> dict:
    cleaned = (iban or "").upper().replace(" ", "")
    if not validate_iban(cleaned):
        raise swiftref_invalid(_ERR_IBAN_FORMAT, f"IBAN {iban} has invalid format")
    row = db.query(SwiftRefIban).filter(SwiftRefIban.iban == cleaned).first()
    if row is None or not row.bic:
        raise swiftref_not_found(_ERR_IBAN_NOT_FOUND, f"No BIC found for IBAN {cleaned}")
    return {"iban": cleaned, "bic": row.bic}


def lookup_iban_details(db, iban: str) -> dict:
    cleaned = (iban or "").upper().replace(" ", "")
    comps = parse_iban(cleaned)
    if comps is None:
        raise swiftref_invalid(_ERR_IBAN_FORMAT, f"IBAN {iban} has invalid format")
    row = db.query(SwiftRefIban).filter(SwiftRefIban.iban == cleaned).first()
    # Augment with directory data if known.
    bank_id = comps.bank_id
    branch_id = comps.branch_id
    account_number = comps.account_number
    if row is not None:
        bank_id = row.bank_code or bank_id
        branch_id = row.branch_code or branch_id
        account_number = row.account_number or account_number
    return {
        "iban": comps.iban,
        "country_code": comps.country_code,
        "checksum": comps.checksum,
        "bank_id": bank_id,
        "branch_id": branch_id,
        "account_number": account_number,
        "length": comps.length,
        "is_iso": comps.is_iso,
    }


def lookup_currency_validity(db, code: str) -> dict:
    upper = code.upper()
    if len(upper) != 3 or not upper.isalpha():
        raise swiftref_invalid(_ERR_CUR_FORMAT, f"Currency code {code} has invalid format")
    row = db.query(SwiftRefCurrency).filter(SwiftRefCurrency.code == upper).first()
    if row is None:
        raise swiftref_not_found(_ERR_CUR_NOT_FOUND, f"Currency code {upper} not found")
    return {"currency_code": upper, "validity": "VCUC"}


def lookup_currency_details(db, code: str) -> dict:
    upper = code.upper()
    if len(upper) != 3 or not upper.isalpha():
        raise swiftref_invalid(_ERR_CUR_FORMAT, f"Currency code {code} has invalid format")
    row = db.query(SwiftRefCurrency).filter(SwiftRefCurrency.code == upper).first()
    if row is None:
        raise swiftref_not_found(_ERR_CUR_NOT_FOUND, f"Currency code {upper} not found")
    return {
        "code": row.code,
        "name": row.name,
        "iso_3n_code": row.iso_3n_code,
        "minor_unit": row.minor_unit,
        "countries": json.loads(row.countries or "[]"),
    }
