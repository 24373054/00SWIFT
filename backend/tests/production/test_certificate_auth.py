import pytest

from production.certificate_auth import CertificateAuthError, ClientCertificateAuthenticator


def test_certificate_authenticator_reads_only_trusted_tls_context():
    with pytest.raises(CertificateAuthError, match="TLS client certificate"):
        ClientCertificateAuthenticator(object()).authenticate({"headers": [(b"x-certificate-fingerprint", b"claimed")]}, environment="pilot")


def test_certificate_bytes_must_be_der_bytes():
    with pytest.raises(CertificateAuthError, match="TLS client certificate"):
        ClientCertificateAuthenticator(object()).authenticate({"extensions": {"tls": {"client_cert_der": "claimed"}}}, environment="pilot")
