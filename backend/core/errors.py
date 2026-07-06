"""SWIFT error model and FastAPI exception handlers.

Implements the canonical SWIFT error envelope from the SWIFT-API-Guide
``errors.md``:

    {
        "errors": [
            {
                "code": "SwAP506",          # unique id, 3..70 chars
                "severity": "Fatal",         # Fatal | Transient | Logic
                "text": "Resource does not exist",  # 1..255 chars
                "user_message": "...",       # optional
                "more_info": "https://..."   # optional URI
            }
        ]
    }

Two variants:
* ``SwiftErrorEnvelope`` — generic SWIFT envelope (SwAP5xx / payVal codes),
  used by Pre-validation, GPI Tracker, Messaging.
* ``SwiftRefErrorEnvelope`` — same shape but the ``code`` is a ``REDA.API.*``
  code, used by SwiftRef.

The old prototype raised ``HTTPException(detail={"status":"error","code":...,
"message":...})`` or bare strings — wrong field names (status/message vs
severity/code/text), no severity enum, no more_info, no user_message. This
module replaces all of that with a single typed model + exception handler.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# ---- severity enum (from SWIFT-API-Guide errors.md) ----

SEVERITY_FATAL = "Fatal"
SEVERITY_TRANSIENT = "Transient"
SEVERITY_LOGIC = "Logic"


# ---- SwAP gateway error codes (from SWIFT-API-Guide errors.md, APIGEE gateway) ----

SWAP_501 = ("SwAP501", "APIRequestIsMalformed", 400)
SWAP_502 = ("SwAP502", "InvalidOAuthToken", 401)
SWAP_503 = ("SwAP503", "OAuthTokenHasInsufficientScopeForRequestedService", 403)
SWAP_504 = ("SwAP504", "RequestBodyIsNotWellFormed", 400)
SWAP_506 = ("SwAP506", "ResourceDoesNotExist", 404)
SWAP_507 = ("SwAP507", "RequestCannotBeProcessedAtThisTime", 429)
SWAP_508 = ("SwAP508", "OAuthTokenNotProvided", 401)
SWAP_509 = ("SwAP509", "MissingMandatorySignatureOnNonRepudiationAPI", 400)
SWAP_510 = ("SwAP510", "APIMethodDoesNotSupportNonRepudiation", 400)
SWAP_521 = ("SwAP521", "XBICHeaderNotIncluded", 400)
SWAP_522 = ("SwAP522", "XBICHeaderNotValid", 400)
SWAP_590 = ("SwAP590", "ServiceTemporarilyUnavailable", 503)
SWAP_591 = ("SwAP591", "ServiceProviderTimeOut", 504)
SWAP_599 = ("SwAP599", "UnexpectedError", 500)


# ---- error item models ----

class ErrorItem(BaseModel):
    """A single SWIFT error entry."""

    code: str = Field(..., min_length=3, max_length=70, description="Unique error identifier")
    severity: str = Field(..., description="Fatal | Transient | Logic")
    text: str = Field(..., min_length=1, max_length=255, description="Human-readable description")
    user_message: Optional[str] = Field(None, max_length=255)
    more_info: Optional[str] = Field(None, description="URI to more information")


class SwiftErrorEnvelope(BaseModel):
    """Generic SWIFT error envelope: ``{"errors": [ErrorItem]}``."""

    errors: List[ErrorItem]


class SwiftRefErrorEnvelope(BaseModel):
    """SwiftRef error envelope — same shape, codes prefixed ``REDA.API.*``."""

    errors: List[ErrorItem]


# ---- exceptions ----

class SwiftApiException(Exception):
    """Base SWIFT API exception. Carries an ErrorItem + HTTP status.

    Raised by business logic; converted to a ``SwiftErrorEnvelope`` JSON
    response by the FastAPI exception handler.
    """

    def __init__(
        self,
        code: str,
        severity: str,
        text: str,
        status_code: int,
        user_message: Optional[str] = None,
        more_info: Optional[str] = None,
    ):
        self.error = ErrorItem(
            code=code, severity=severity, text=text, user_message=user_message, more_info=more_info
        )
        self.status_code = status_code
        super().__init__(text)


class SwiftRefException(SwiftApiException):
    """SwiftRef-specific exception. ``code`` should be a ``REDA.API.*`` code.

    Rendered as a ``SwiftRefErrorEnvelope`` (identical shape, but signals to
    consumers that the codes follow the REDA namespace).
    """

    is_swiftref = True


# ---- convenience constructors for common SwAP errors ----

def invalid_token(text: str = "Invalid or expired OAuth token") -> SwiftApiException:
    return SwiftApiException(SWAP_502[0], SEVERITY_FATAL, text, SWAP_502[2])


def token_not_provided() -> SwiftApiException:
    return SwiftApiException(SWAP_508[0], SEVERITY_FATAL, SWAP_508[1], SWAP_508[2])


def insufficient_scope(scope: str = "") -> SwiftApiException:
    text = f"OAuth token has insufficient scope for the requested service: {scope}" if scope else SWAP_503[1]
    return SwiftApiException(SWAP_503[0], SEVERITY_FATAL, text, SWAP_503[2])


def resource_not_found(text: str = "Resource does not exist") -> SwiftApiException:
    return SwiftApiException(SWAP_506[0], SEVERITY_FATAL, text, SWAP_506[2])


def missing_signature() -> SwiftApiException:
    return SwiftApiException(SWAP_509[0], SEVERITY_FATAL, SWAP_509[1], SWAP_509[2])


def xbic_not_included() -> SwiftApiException:
    return SwiftApiException(SWAP_521[0], SEVERITY_FATAL, SWAP_521[1], SWAP_521[2])


def xbic_not_valid() -> SwiftApiException:
    return SwiftApiException(SWAP_522[0], SEVERITY_FATAL, SWAP_522[1], SWAP_522[2])


def malformed_request(text: str = SWAP_501[1]) -> SwiftApiException:
    return SwiftApiException(SWAP_501[0], SEVERITY_FATAL, text, SWAP_501[2])


def unexpected_error(text: str = "Unexpected internal error") -> SwiftApiException:
    return SwiftApiException(SWAP_599[0], SEVERITY_FATAL, text, SWAP_599[2])


# ---- SwiftRef REDA.API.* convenience constructors ----

def swiftref_not_found(code: str, text: str) -> SwiftRefException:
    """404 for a SwiftRef lookup (e.g. REDA.API.BINF for BIC not found)."""
    return SwiftRefException(code, SEVERITY_FATAL, text, 404)


def swiftref_invalid(code: str, text: str) -> SwiftRefException:
    """400 for a malformed SwiftRef request (e.g. REDA.API.IBIC for invalid BIC format)."""
    return SwiftRefException(code, SEVERITY_FATAL, text, 400)


def swiftref_unauthorized() -> SwiftRefException:
    return SwiftRefException("REDA.API.ILIC", SEVERITY_FATAL, "Invalid or missing OAuth token", 401)


# ---- exception handlers ----

def _envelope(exc: SwiftApiException) -> dict:
    return {"errors": [jsonable_encoder(exc.error)]}


async def swift_api_exception_handler(request: Request, exc: SwiftApiException) -> JSONResponse:
    """Convert ``SwiftApiException`` into the canonical SWIFT error envelope."""
    return JSONResponse(status_code=exc.status_code, content=_envelope(exc))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert FastAPI/Pydantic request-validation errors into the SwAP envelope.

    Maps the 422 validation error to a 400 ``SwAP501 APIRequestIsMalformed``,
    surfacing the field-level details in the ``text`` field.
    """
    details = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
        details.append(f"{loc}: {err.get('msg', '')}".strip(": "))
    text = "Request body is malformed: " + "; ".join(details) if details else SWAP_501[1]
    err = ErrorItem(code=SWAP_501[0], severity=SEVERITY_FATAL, text=text[:255])
    return JSONResponse(status_code=400, content={"errors": [jsonable_encoder(err)]})


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: never leak stack traces (SWIFT-API-Guide errors.md)."""
    err = ErrorItem(
        code=SWAP_599[0],
        severity=SEVERITY_FATAL,
        text=f"Unexpected internal error: {type(exc).__name__}",
    )
    return JSONResponse(status_code=500, content={"errors": [jsonable_encoder(err)]})


def register_exception_handlers(app: FastAPI) -> None:
    """Register all SWIFT-style exception handlers on the FastAPI app."""
    app.add_exception_handler(SwiftApiException, swift_api_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
