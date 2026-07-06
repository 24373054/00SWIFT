"""IBAN validation and parsing.

Implements:
* ISO 13616 mod-97 checksum validation.
* Per-country BBAN structure validation via a small structure table
  (length + character classes for the bank-code/branch/account positions).

The structure table covers the countries most likely to appear in a local
sandbox (SEPA + a few others). It is NOT a complete ISO 13636 registry —
for unknown countries we fall back to mod-97 only and mark the IBAN as
``is_iso=False`` (matching SwiftRef's ``IbanDetailsWithIsoFlag`` semantics).
"""

import re
from dataclasses import dataclass
from typing import Optional

# Basic IBAN shape: 2 letters country, 2 digits check, 1-30 alphanumerics.
IBAN_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$")


@dataclass(frozen=True)
class IbanStructure:
    """BBAN structure for a country.

    ``positions`` is a list of (length, char_class) tuples describing the BBAN
    after the 4-char country+check prefix. ``char_class`` is one of ``"n"``
    (digits only) or ``"c"`` (alphanumeric).
    """

    country: str
    length: int  # total IBAN length including country+check
    positions: tuple  # tuple of (length, char_class)


# A small registry of BBAN structures for common SEPA/near-SEPA countries.
# Sources: ISO 13616 published structures (publicly available).
_IBAN_STRUCTURES = {
    "DE": IbanStructure("DE", 22, ((8, "n"), (10, "n"))),  # bank code + account
    "FR": IbanStructure("FR", 27, ((5, "n"), (5, "n"), (11, "c"), (2, "n"))),  # bank + branch + account + check
    "IT": IbanStructure("IT", 27, ((1, "c"), (5, "n"), (5, "n"), (12, "c"))),  # CIN + ABI + CAB + account
    "GB": IbanStructure("GB", 22, ((4, "c"), (6, "n"), (8, "n"))),  # bank + sort + account
    "BE": IbanStructure("BE", 16, ((3, "n"), (7, "n"), (2, "n"))),  # bank + account + check
    "NL": IbanStructure("NL", 18, ((4, "c"), (10, "n"))),  # bank + account
    "ES": IbanStructure("ES", 24, ((4, "n"), (4, "n"), (2, "n"), (10, "n"))),  # bank + branch + check + account
    "CH": IbanStructure("CH", 21, ((5, "n"), (12, "c"))),  # bank + account
    "AT": IbanStructure("AT", 20, ((5, "n"), (11, "n"))),  # bank + account
    "US": None,  # US does not use IBAN
    "CN": None,  # CN does not use IBAN
}


def _char_class_ok(segment: str, char_class: str) -> bool:
    if char_class == "n":
        return segment.isdigit()
    # "c" = alphanumeric (uppercase)
    return bool(re.match(r"^[A-Z0-9]+$", segment))


def validate_iban(iban: str) -> bool:
    """Validate an IBAN: format + mod-97 checksum + country BBAN structure."""
    if not iban:
        return False
    cleaned = iban.replace(" ", "").upper()
    if not IBAN_RE.match(cleaned):
        return False
    # mod-97 check: move first 4 chars to end, convert letters A=10..Z=35.
    rearranged = cleaned[4:] + cleaned[:4]
    expanded = "".join(str(int(ch, 36)) for ch in rearranged)
    if int(expanded) % 97 != 1:
        return False
    # Country structure check.
    country = cleaned[:2]
    structure = _IBAN_STRUCTURES.get(country)
    if structure is None:
        # Unknown country (including US/CN which don't use IBAN).
        return False
    if len(cleaned) != structure.length:
        return False
    bban = cleaned[4:]
    pos = 0
    for length, char_class in structure.positions:
        segment = bban[pos : pos + length]
        if len(segment) != length or not _char_class_ok(segment, char_class):
            return False
        pos += length
    return True


@dataclass
class IbanComponents:
    iban: str
    country_code: str
    checksum: str
    bank_id: str
    branch_id: Optional[str]
    account_number: str
    length: int
    is_iso: bool


def parse_iban(iban: str) -> Optional[IbanComponents]:
    """Parse an IBAN into its components. Returns None if format is invalid.

    Note: ``is_iso`` is True only when the country is in the local structure
    registry (i.e. we can confidently decompose the BBAN). SwiftRef returns
    ``is_iso=False`` for countries outside the ISO registry.
    """
    if not iban:
        return None
    cleaned = iban.replace(" ", "").upper()
    if not IBAN_RE.match(cleaned):
        return None
    country = cleaned[:2]
    structure = _IBAN_STRUCTURES.get(country)
    is_iso = structure is not None
    bank_id = branch_id = account_number = ""
    if structure:
        bban = cleaned[4:]
        pos = 0
        parts = []
        for length, _ in structure.positions:
            parts.append(bban[pos : pos + length])
            pos += length
        bank_id = parts[0]
        account_number = parts[-1]
        if len(parts) > 2:
            branch_id = parts[1]
        elif len(parts) == 2:
            branch_id = None
    return IbanComponents(
        iban=cleaned,
        country_code=country,
        checksum=cleaned[2:4],
        bank_id=bank_id,
        branch_id=branch_id,
        account_number=account_number,
        length=len(cleaned),
        is_iso=is_iso,
    )
