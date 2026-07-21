"""API Catalogue — lists the real SWIFT base paths and scopes.

Replaces the old prototype's hand-maintained ``API_CATALOGUE`` list (which
advertised invented paths like ``/payments/pre-validation``).
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/catalogue", tags=["Catalogue"])

CATALOGUE = [
    {
        "product": "OAuth2",
        "version": "v1",
        "base_path": "/oauth2",
        "endpoints": [
            {"method": "POST", "path": "/token", "desc": "Issue access token (JWT-Bearer grant)"},
            {"method": "POST", "path": "/revoke", "desc": "Revoke an access token (RFC 7009)"},
        ],
        "scopes": [],
    },
    {
        "product": "Pre-validation",
        "version": "v2",
        "base_path": "/swift-preval/v2",
        "endpoints": [
            {
                "method": "POST",
                "path": "/payment/payment-instruction",
                "desc": "Contextual multi-check validation",
            },
            {
                "method": "POST",
                "path": "/payment/financial-institution-identity",
                "desc": "Validate FI BIC",
            },
            {
                "method": "POST",
                "path": "/payment/account-format",
                "desc": "Validate account format",
            },
            {"method": "POST", "path": "/payment/amount", "desc": "Validate instructed amount"},
        ],
        "scopes": ["swift.preval"],
    },
    {
        "product": "SwiftRef",
        "version": "v4",
        "base_path": "/swiftrefdata/v4",
        "endpoints": [
            {"method": "GET", "path": "/bics/{bic}/validity", "desc": "Check BIC validity"},
            {"method": "GET", "path": "/bics/{bic}", "desc": "BIC details"},
            {"method": "GET", "path": "/ibans/{iban}/validity", "desc": "Check IBAN validity"},
            {"method": "GET", "path": "/ibans/{iban}/bic", "desc": "Derive BIC from IBAN"},
            {"method": "GET", "path": "/currency_codes/{code}", "desc": "Currency details"},
        ],
        "scopes": ["swift.swiftref"],
    },
    {
        "product": "GPI Tracker",
        "version": "v4",
        "base_path": "/swift-apitracker/v4",
        "endpoints": [
            {
                "method": "GET",
                "path": "/payments/{uetr}/transactions",
                "desc": "Payment transaction details",
            },
            {
                "method": "GET",
                "path": "/payments/changed/transactions",
                "desc": "Changed payments in time window",
            },
            {
                "method": "POST",
                "path": "/payments/{uetr}/status",
                "desc": "Status confirmation (signed)",
            },
            {
                "method": "POST",
                "path": "/payments/{uetr}/cancellation",
                "desc": "Request cancellation (signed)",
            },
            {
                "method": "POST",
                "path": "/payments/{uetr}/cancellation/status",
                "desc": "Report cancellation status (signed)",
            },
        ],
        "scopes": ["swift.apitracker/FullViewer", "swift.apitracker/Update"],
    },
    {
        "product": "Messaging",
        "version": "v2",
        "base_path": "/alliancecloud/v2",
        "endpoints": [
            {"method": "POST", "path": "/fin/messages", "desc": "Send a FIN message (signed)"},
            {"method": "GET", "path": "/distributions", "desc": "List distributions (inbox)"},
            {
                "method": "POST",
                "path": "/distributions/{id}/acks",
                "desc": "ACK a distribution (signed)",
            },
            {
                "method": "POST",
                "path": "/distributions/{id}/naks",
                "desc": "NAK a distribution (signed)",
            },
        ],
        "scopes": ["swift.messaging"],
    },
]


@router.get("")
def get_catalogue():
    return {"apis": CATALOGUE}
