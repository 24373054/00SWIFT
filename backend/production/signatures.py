"""Cryptographic HTTP Message Signatures (RFC 9421) boundary.

The parser and canonicalization are shared by sandbox tests and the qualified
adapter.  Sandbox still performs real Ed25519 verification; it is not a
header-presence or fixed-success verifier.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def configured_algorithms() -> frozenset[str]:
    from config import get_settings

    return frozenset(item.strip().lower() for item in get_settings().production_signature_allowed_algorithms.split(",") if item.strip())


class SignatureVerificationError(ValueError):
    """Raised for malformed, expired, replayable or invalid signatures."""


REQUIRED_COMPONENTS = frozenset(
    {"@method", "@target-uri", "@authority", "content-digest", "content-type", "date", "nonce", "participant-id", "service-identity"}
)
_WEAK_ALGORITHMS = frozenset({"none", "hs256", "hmac-sha256", "rsa-sha1", "sha1"})


@dataclass(frozen=True)
class SignedHttpRequest:
    method: str
    target_uri: str
    authority: str
    headers: Mapping[str, str]
    body: bytes
    signature_input: str
    signature: str
    participant_id: str
    service_identity: str
    now: dt.datetime | None = None


@dataclass(frozen=True)
class SignatureVerificationResult:
    key_id: str
    algorithm: str
    participant_id: str
    service_identity: str
    nonce: str
    created: int
    expires: int
    content_digest: str


class HttpSignatureVerifier(Protocol):
    def verify(self, request: SignedHttpRequest) -> SignatureVerificationResult: ...


def _b64(value: str, field: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise SignatureVerificationError(f"{field} is not valid base64") from exc


def _parse_signature_input(value: str) -> tuple[list[str], dict[str, str]]:
    match = re.fullmatch(r"sig1=\((?P<components>[^)]*)\)(?P<params>.*)", value.strip())
    if not match:
        raise SignatureVerificationError("Signature-Input must contain one sig1 structured field")
    components = re.findall(r'"([^"]+)"', match.group("components"))
    if len(set(components)) != len(components):
        raise SignatureVerificationError("covered components must be unique")
    params: dict[str, str] = {}
    for key, raw in re.findall(r";([a-z][a-z0-9-]*)=(\"[^\"]*\"|-?\d+)", match.group("params")):
        params[key] = raw[1:-1] if raw.startswith('"') else raw
    return components, params


def _parse_signature(value: str) -> bytes:
    match = re.fullmatch(r"sig1=:([^:]+):", value.strip())
    if not match:
        raise SignatureVerificationError("Signature must contain one sig1 byte sequence")
    return _b64(match.group(1), "Signature")


def canonical_signature_input(request: SignedHttpRequest, components: list[str], params: Mapping[str, str]) -> bytes:
    headers = {key.lower(): value.strip() for key, value in request.headers.items()}
    lines: list[str] = []
    for component in components:
        if component == "@method":
            value = request.method.upper()
        elif component == "@target-uri":
            value = request.target_uri
        elif component == "@authority":
            value = request.authority
        elif component.startswith("@"):
            raise SignatureVerificationError(f"unsupported derived component: {component}")
        else:
            if component.lower() not in headers:
                raise SignatureVerificationError(f"covered header is missing: {component}")
            value = headers[component.lower()]
        lines.append(f'"{component}": {value}')
    for key in ("created", "expires", "nonce", "keyid", "alg"):
        if key in params:
            raw = params[key]
            lines.append(f"@signature-params;{key}={raw if key in {'created', 'expires'} else chr(34) + raw + chr(34)}")
    return "\n".join(lines).encode("utf-8")


def _verify_common(request: SignedHttpRequest, allowed_algorithms: frozenset[str]) -> tuple[list[str], dict[str, str], bytes, SignatureVerificationResult]:
    components, params = _parse_signature_input(request.signature_input)
    missing = REQUIRED_COMPONENTS - set(components)
    if missing:
        raise SignatureVerificationError(f"covered components missing: {sorted(missing)}")
    algorithm = params.get("alg", "").lower()
    if not algorithm or algorithm in _WEAK_ALGORITHMS or algorithm not in allowed_algorithms:
        raise SignatureVerificationError(f"signature algorithm is not allowed: {algorithm or '<missing>'}")
    try:
        created = int(params["created"])
        expires = int(params["expires"])
    except (KeyError, ValueError) as exc:
        raise SignatureVerificationError("created and expires signature parameters are required") from exc
    nonce = params.get("nonce", "")
    key_id = params.get("keyid", "")
    if not nonce or not key_id:
        raise SignatureVerificationError("nonce and keyid signature parameters are required")
    from config import get_settings

    now = int((request.now or dt.datetime.now(dt.UTC)).timestamp())
    skew = get_settings().clock_skew_seconds
    if created > now + skew or expires < now - skew or expires <= created:
        raise SignatureVerificationError("signature is outside its validity window")
    headers = {key.lower(): value.strip() for key, value in request.headers.items()}
    digest_header = headers.get("content-digest", "")
    if not digest_header.startswith("sha-256=:") or not digest_header.endswith(":"):
        raise SignatureVerificationError("Content-Digest sha-256 is required")
    expected_digest = _b64(digest_header[len("sha-256=:"):-1], "Content-Digest")
    if not hmac.compare_digest(expected_digest, hashlib.sha256(request.body).digest()):
        raise SignatureVerificationError("content digest does not match body")
    if request.participant_id != headers.get("participant-id") or request.service_identity != headers.get("service-identity"):
        raise SignatureVerificationError("participant/service identity binding failed")
    result = SignatureVerificationResult(key_id, algorithm, request.participant_id, request.service_identity, nonce, created, expires, digest_header)
    return components, params, _parse_signature(request.signature), result


class SandboxHttpSignatureVerifier:
    """Real Ed25519 verifier for isolated sandbox identities."""

    def __init__(self, keys: Mapping[str, bytes], *, allowed_algorithms: set[str] | None = None):
        self.keys = dict(keys)
        self.allowed_algorithms = frozenset(item.lower() for item in (allowed_algorithms or configured_algorithms()))

    def verify(self, request: SignedHttpRequest) -> SignatureVerificationResult:
        components, params, signature, result = _verify_common(request, self.allowed_algorithms)
        public_key = self.keys.get(result.key_id)
        if public_key is None:
            raise SignatureVerificationError("unknown signature key id")
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, canonical_signature_input(request, components, params))
        except (InvalidSignature, ValueError) as exc:
            raise SignatureVerificationError("signature verification failed") from exc
        return result


class QualifiedHttpSignatureVerifier:
    """Adapter for an external trust-domain/HSM verifier.

    The callback must verify the canonical bytes against the qualified key;
    returning success without doing so is intentionally outside this adapter.
    """

    def __init__(self, verify_signature: Callable[[str, bytes, bytes], bool], *, allowed_algorithms: set[str] | None = None):
        self.verify_signature = verify_signature
        self.allowed_algorithms = frozenset(item.lower() for item in (allowed_algorithms or configured_algorithms()))

    def verify(self, request: SignedHttpRequest) -> SignatureVerificationResult:
        components, params, signature, result = _verify_common(request, self.allowed_algorithms)
        if not self.verify_signature(result.key_id, canonical_signature_input(request, components, params), signature):
            raise SignatureVerificationError("qualified signature verification failed")
        return result
