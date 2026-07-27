"""Authenticate client certificates from trusted ASGI TLS context only."""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .models import ProductionCertificate, ProductionParticipant, ProductionServiceIdentity


class CertificateAuthError(ValueError):
    pass


@dataclass(frozen=True)
class AuthenticatedCertificate:
    certificate_id: str
    fingerprint: str
    identity_id: str
    participant_id: str
    tenant_id: str
    trust_domain: str


class ClientCertificateAuthenticator:
    """Resolve cert -> service identity -> participant -> tenant binding."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _certificate_bytes(scope: dict[str, object]) -> bytes:
        extensions = scope.get("extensions")
        if isinstance(extensions, dict):
            tls = extensions.get("tls")
            if isinstance(tls, dict) and isinstance(tls.get("client_cert_der"), bytes):
                return tls["client_cert_der"]
        direct = scope.get("client_cert_der")
        if isinstance(direct, bytes):
            return direct
        raise CertificateAuthError("trusted TLS client certificate is required")

    def authenticate(self, scope: dict[str, object], *, environment: str) -> AuthenticatedCertificate:
        der = self._certificate_bytes(scope)
        fingerprint = hashlib.sha256(der).hexdigest()
        now = dt.datetime.now(dt.UTC)
        certificate = self.db.query(ProductionCertificate).filter_by(fingerprint=fingerprint, status="ACTIVE").one_or_none()
        if certificate is None or certificate.not_before > now or certificate.not_after <= now:
            raise CertificateAuthError("client certificate is inactive, expired or unknown")
        identity = self.db.query(ProductionServiceIdentity).filter_by(certificate_fingerprint=fingerprint, status="ACTIVE", environment=environment).one_or_none()
        if identity is None:
            raise CertificateAuthError("certificate is not bound to an active service identity/environment")
        participant = self.db.query(ProductionParticipant).filter_by(participant_id=identity.participant_id, status="ACTIVE").one_or_none()
        if participant is None or not participant.tenant_id:
            raise CertificateAuthError("certificate participant/tenant binding is inactive")
        return AuthenticatedCertificate(certificate.certificate_id, fingerprint, identity.identity_id, participant.participant_id, participant.tenant_id, certificate.trust_domain)
