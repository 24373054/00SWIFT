"""Generate a mock CA and a client certificate for sandbox mode.

Usage:
    python -m scripts.gen_mock_certs <app_consumer_key> [<cert_subject_cn>]

Produces (under backend/certs/):
    ca/ca.key         — mock CA private key
    ca/ca.crt         — mock CA self-signed certificate
    apps/<key>.key    — client private key (unencrypted, for sandbox)
    apps/<key>.crt    — client certificate signed by the mock CA

The client cert's subject CN is the consumer_key (lowercased to match the
RFC4514 subject convention used by the OAuth ``sub`` claim).

In pilot/live mode this script is NOT used — real SWIFT PKI certs must be
uploaded per credential.
"""

from __future__ import annotations

import contextlib
import datetime
import os
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _backend_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_dirs() -> tuple[str, str]:
    from config import get_settings

    settings = get_settings()
    ca_dir = settings.certs_ca_dir()
    apps_dir = settings.certs_apps_dir()
    os.makedirs(ca_dir, exist_ok=True)
    os.makedirs(apps_dir, exist_ok=True)
    return ca_dir, apps_dir


def _gen_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _save_key(key, path: str) -> None:
    with open(path, "wb") as fh:
        fh.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def _save_cert(cert, path: str) -> None:
    with open(path, "wb") as fh:
        fh.write(cert.public_bytes(serialization.Encoding.PEM))


def ensure_ca(ca_dir: str) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    """Load or generate the mock CA key + self-signed cert."""
    key_path = os.path.join(ca_dir, "ca.key")
    crt_path = os.path.join(ca_dir, "ca.crt")
    if os.path.exists(key_path) and os.path.exists(crt_path):
        with open(key_path, "rb") as fh:
            key = serialization.load_pem_private_key(fh.read(), password=None)
        with open(crt_path, "rb") as fh:
            cert = x509.load_pem_x509_certificate(fh.read())
        return key, cert

    key = _gen_key()
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "swift-mock-ca"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SWIFT Dev Sandbox"),
        ]
    )
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    _save_key(key, key_path)
    _save_cert(cert, crt_path)
    return key, cert


def issue_client_cert(
    consumer_key: str,
    ca_key: rsa.RSAPrivateKey,
    ca_cert: x509.Certificate,
    apps_dir: str,
) -> tuple[str, str, str]:
    """Issue a client cert signed by the mock CA. Returns (key_path, crt_path, cert_subject)."""
    cn = consumer_key.lower()
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SWIFT Dev Sandbox App"),
        ]
    )
    key = _gen_key()
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(ca_key, hashes.SHA256())
    )
    key_path = os.path.join(apps_dir, f"{consumer_key}.key")
    crt_path = os.path.join(apps_dir, f"{consumer_key}.crt")
    _save_key(key, key_path)
    _save_cert(cert, crt_path)
    return key_path, crt_path, subject.rfc4514_string().lower()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    consumer_key = argv[1]
    ca_dir, apps_dir = _ensure_dirs()
    ca_key, ca_cert = ensure_ca(ca_dir)
    key_path, crt_path, subject = issue_client_cert(consumer_key, ca_key, ca_cert, apps_dir)
    print(f"CA:       {os.path.join(ca_dir, 'ca.crt')}")
    print(f"Client:   {crt_path}")
    print(f"Key:      {key_path}")
    print(f"Subject:  {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
