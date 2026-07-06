"""PKI certificate and private-key loading utilities.

Mirrors ``research/api-sample-code/python/messaging-api/app/api/utils.py`` but
adapted to the local ``backend/certs/`` directory layout and the ``cryptography``
library (already a transitive dependency via pacs008/pyiso20022).

Used by:
* ``auth/oauth.py`` — to verify the RS256 JWT assertion's ``x5c`` certificate
  chain against the stored client cert when issuing access tokens.
* ``auth/signature.py`` — to verify the ``X-SWIFT-Signature`` JWT against the
  client cert's public key.
* ``client/oauth_token.py`` / ``client/swift_signature.py`` — to load the
  client's own private key + cert when minting assertions/signatures.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.x509 import load_pem_x509_certificate

from config import get_settings


def key_path(filename: str) -> str:
    """Resolve a filename relative to the certs directory."""
    return os.path.join(get_settings().certs_abs_dir(), filename)


@dataclass
class LoadedCertificate:
    """A parsed PEM certificate plus its x5c chain and RFC4514 subject."""

    pem: str  # original PEM text
    x5c: List[str]  # base64 DER segments (no headers/newlines), for JWT x5c header
    cert_subject: str  # RFC4514 string, lowercased (matches SWIFT sample utils.py)
    certificate: object  # the cryptography x509.Certificate object


def load_certificate_from_pem(pem_bytes: bytes) -> LoadedCertificate:
    """Parse a PEM-encoded certificate into a ``LoadedCertificate``.

    ``cert_subject`` is lowercased to match the SWIFT sample's
    ``cert.subject.rfc4514_string().lower()`` convention, which is what the
    OAuth assertion's ``sub`` claim and the signature JWT's ``sub`` claim are
    compared against.
    """
    cert = load_pem_x509_certificate(pem_bytes)
    pem_text = pem_bytes.decode("utf-8")
    # Strip PEM headers/newlines to produce the base64 DER segment for the x5c header.
    der_b64 = (
        pem_text.replace("-----BEGIN CERTIFICATE-----", "")
        .replace("-----END CERTIFICATE-----", "")
        .replace("\r", "")
        .replace("\n", "")
        .strip()
    )
    cert_subject = cert.subject.rfc4514_string().lower()
    return LoadedCertificate(
        pem=pem_text,
        x5c=[der_b64],
        cert_subject=cert_subject,
        certificate=cert,
    )


def load_certificate_from_file(path: str) -> LoadedCertificate:
    with open(path, "rb") as fh:
        return load_certificate_from_pem(fh.read())


def load_private_key_from_pem(pem_bytes: bytes, password: Optional[bytes] = None):
    """Load a PEM-encoded private key (RSA, for RS256 signing).

    ``password`` is the key passphrase bytes, or None for an unencrypted key.
    """
    return load_pem_private_key(pem_bytes, password=password)


def load_private_key_from_file(path: str, password: Optional[bytes] = None):
    with open(path, "rb") as fh:
        return load_private_key_from_pem(fh.read(), password)


def get_certificate(filename: str) -> LoadedCertificate:
    """Load a certificate from the certs dir (mirrors SWIFT sample ``get_certificate``)."""
    return load_certificate_from_file(key_path(filename))


def get_key(filename: str, key_password: Optional[str] = None):
    """Load a private key from the certs dir (mirrors SWIFT sample ``get_key``)."""
    password = key_password.encode("utf-8") if key_password else None
    return load_private_key_from_file(key_path(filename), password)


def get_proxies() -> Optional[dict]:
    """Return a requests/httpx proxies dict if PROXY is set, else None."""
    proxy = get_settings().proxy
    return {"https": proxy, "http": proxy} if proxy else None
