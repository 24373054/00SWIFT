"""HTTP message integrity boundary for the production API."""

from __future__ import annotations

import base64
import hashlib
import hmac

from fastapi import HTTPException, Request

from config import get_settings

from .signatures import HttpSignatureVerifier, SignatureVerificationError, SignedHttpRequest

_signature_verifier: HttpSignatureVerifier | None = None


def configure_signature_verifier(verifier: HttpSignatureVerifier | None) -> None:
    """Inject a concrete sandbox or qualified verifier at application wiring time."""
    global _signature_verifier
    _signature_verifier = verifier


def verify_content_digest(body: bytes, digest_header: str) -> None:
    try:
        algorithm, encoded = digest_header.split("=:", 1)
        encoded = encoded.rstrip(":")
        if algorithm.lower() != "sha-256":
            raise ValueError("unsupported digest algorithm")
        actual = hashlib.sha256(body).digest()
        if not hmac.compare_digest(base64.b64decode(encoded, validate=True), actual):
            raise ValueError("digest mismatch")
    except Exception as exc:  # noqa: BLE001 - fail closed at the HTTP boundary
        raise SignatureVerificationError(str(exc)) from exc


async def require_request_integrity(request: Request) -> None:
    settings = get_settings()
    digest_header = request.headers.get("content-digest")
    signature_input = request.headers.get("signature-input")
    signature = request.headers.get("signature")
    body = await request.body()

    if digest_header:
        try:
            verify_content_digest(body, digest_header)
        except SignatureVerificationError as exc:
            raise HTTPException(status_code=400, detail={"code": "INVALID_CONTENT_DIGEST", "message": str(exc)}) from exc

    has_signature = bool(signature_input or signature)
    if settings.swift_env not in {"pilot", "live"} and not has_signature:
        return
    missing = [name for name, value in (("Content-Digest", digest_header), ("Signature-Input", signature_input), ("Signature", signature)) if not value]
    if missing:
        raise HTTPException(status_code=400, detail={"code": "MISSING_MESSAGE_INTEGRITY", "headers": missing})
    if _signature_verifier is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "QUALIFIED_SIGNATURE_VERIFIER_NOT_CONFIGURED"},
        )
    headers: dict[str, str] = dict(request.headers)
    signed_request = SignedHttpRequest(
        method=request.method,
        target_uri=str(request.url),
        authority=headers.get("host", ""),
        headers=headers,
        body=body,
        signature_input=signature_input or "",
        signature=signature or "",
        participant_id=headers.get("participant-id", ""),
        service_identity=headers.get("service-identity", ""),
    )
    try:
        result = _signature_verifier.verify(signed_request)
    except SignatureVerificationError as exc:
        raise HTTPException(status_code=401, detail={"code": "INVALID_MESSAGE_SIGNATURE", "message": str(exc)}) from exc
    request.state.signature_verification = result
