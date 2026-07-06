"""SwiftRef API response schemas (subset of the v4.0.0 swagger).

Aligned with ``research/api-sample-code/dotnet/SwiftRef/SwiftRef/SWIFT-API-swiftref_api-4.0.0-swagger.yaml``.
Field names are snake_case per SWIFT naming conventions.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class BicValidity(BaseModel):
    bic: str
    validity: str = "VBIC"  # VBIC = valid BIC
    effective_date: Optional[str] = None  # YYYY-MM-DDZ (UTC)


class IbanValidity(BaseModel):
    iban: str
    validity: str = "IVAL"  # IVAL = invalid by default; VIBN if valid


class SwiftService(BaseModel):
    code: str
    name: Optional[str] = None


class BicDetails(BaseModel):
    bic: str
    office_type: Optional[str] = None
    name: Optional[str] = None
    country_code: Optional[str] = None
    town_name: Optional[str] = None
    post_code: Optional[str] = None
    address_line: Optional[str] = None
    swift_connectivity: dict = {}
    connected_bic: Optional[str] = None
    utc_offset: Optional[str] = None


class IbanBic(BaseModel):
    iban: str
    bic: str


class IbanComponents(BaseModel):
    iban: str
    country_code: str
    checksum: str
    bank_id: Optional[str] = None
    branch_id: Optional[str] = None
    account_number: Optional[str] = None
    length: int
    is_iso: bool


class CurrencyCode(BaseModel):
    code: str
    name: Optional[str] = None
    iso_3n_code: Optional[str] = None
    minor_unit: Optional[int] = None
    countries: List[str] = []


class CurrencyCodeValidity(BaseModel):
    currency_code: str
    validity: str = "VCUC"  # VCUC = valid currency code
