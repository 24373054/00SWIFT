"""SwiftRef API response schemas (subset of the v4.0.0 swagger).

Aligned with ``research/api-sample-code/dotnet/SwiftRef/SwiftRef/SWIFT-API-swiftref_api-4.0.0-swagger.yaml``.
Field names are snake_case per SWIFT naming conventions.
"""

from __future__ import annotations

from pydantic import BaseModel


class BicValidity(BaseModel):
    bic: str
    validity: str = "VBIC"  # VBIC = valid BIC
    effective_date: str | None = None  # YYYY-MM-DDZ (UTC)


class IbanValidity(BaseModel):
    iban: str
    validity: str = "IVAL"  # IVAL = invalid by default; VIBN if valid


class SwiftService(BaseModel):
    code: str
    name: str | None = None


class BicDetails(BaseModel):
    bic: str
    office_type: str | None = None
    name: str | None = None
    country_code: str | None = None
    town_name: str | None = None
    post_code: str | None = None
    address_line: str | None = None
    swift_connectivity: dict = {}
    connected_bic: str | None = None
    utc_offset: str | None = None


class IbanBic(BaseModel):
    iban: str
    bic: str


class IbanComponents(BaseModel):
    iban: str
    country_code: str
    checksum: str
    bank_id: str | None = None
    branch_id: str | None = None
    account_number: str | None = None
    length: int
    is_iso: bool


class CurrencyCode(BaseModel):
    code: str
    name: str | None = None
    iso_3n_code: str | None = None
    minor_unit: int | None = None
    countries: list[str] = []


class CurrencyCodeValidity(BaseModel):
    currency_code: str
    validity: str = "VCUC"  # VCUC = valid currency code
