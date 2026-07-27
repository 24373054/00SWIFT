"""Certificate rotation, revocation and external OCSP/CRL refresh orchestration."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from .models import ProductionCertificate, utcnow


class CertificateLifecycleError(ValueError):
    pass


class CertificateService:
    def __init__(self, db: Session):
        self.db = db

    def rotate(self, old_certificate_id: str, *, fingerprint: str, serial_number: str, issuer: str, not_before: dt.datetime, not_after: dt.datetime, overlap_until: dt.datetime, maker: str, checker: str) -> ProductionCertificate:
        old = self.db.query(ProductionCertificate).filter_by(certificate_id=old_certificate_id, status="ACTIVE").one_or_none()
        if old is None:
            raise CertificateLifecycleError("active certificate to rotate is required")
        if maker == checker or not_before >= not_after or overlap_until <= not_before or overlap_until > old.not_after:
            raise CertificateLifecycleError("invalid rotation window or dual control")
        replacement = ProductionCertificate(certificate_id=f"cert_{uuid.uuid4().hex}", participant_id=old.participant_id, fingerprint=fingerprint, serial_number=serial_number, issuer=issuer, trust_domain=old.trust_domain, status="ACTIVE", not_before=not_before, not_after=not_after)
        self.db.add(replacement)
        self.db.flush()
        old.not_after = overlap_until
        self.db.flush()
        return replacement

    def revoke(self, certificate_id: str, *, maker: str, checker: str, reason: str) -> None:
        certificate = self.db.query(ProductionCertificate).filter_by(certificate_id=certificate_id, status="ACTIVE").one_or_none()
        if certificate is None or maker == checker or not reason.strip():
            raise CertificateLifecycleError("active certificate, reason and distinct maker/checker are required")
        certificate.status = "REVOKED"
        certificate.revoked_at = utcnow()
        self.db.flush()

    def refresh_external_status(self, *, checker: Callable[[str], str], now: dt.datetime | None = None) -> int:
        current = now or utcnow()
        changed = 0
        for certificate in self.db.query(ProductionCertificate).filter(ProductionCertificate.status == "ACTIVE").all():
            status = checker(certificate.fingerprint)
            if status not in {"GOOD", "REVOKED", "UNKNOWN"}:
                raise CertificateLifecycleError("OCSP/CRL provider returned invalid status")
            if status == "REVOKED":
                certificate.status = "REVOKED"
                certificate.revoked_at = current
                changed += 1
            elif certificate.not_after <= current:
                certificate.status = "EXPIRED"
                changed += 1
        self.db.flush()
        return changed
