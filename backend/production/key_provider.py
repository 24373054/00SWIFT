"""Key-provider boundary with explicit sandbox/qualified implementations."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class KeyProviderError(RuntimeError):
    """Raised when a key is unknown, revoked or an HSM operation fails."""


@dataclass(frozen=True)
class KeyMetadata:
    key_id: str
    trust_domain: str
    algorithm: str
    version: int
    status: str
    created_at: dt.datetime
    public_key: bytes


class KeyProvider(Protocol):
    def sign(self, key_id: str, message: bytes) -> bytes: ...

    def verify(self, key_id: str, message: bytes, signature: bytes) -> bool: ...

    def get_public_key(self, key_id: str) -> bytes: ...

    def rotate(self, key_id: str) -> KeyMetadata: ...

    def revoke_status(self, key_id: str) -> str: ...


class SandboxKeyProvider:
    """Real Ed25519 provider for isolated tests; private keys never leave objects."""

    def __init__(self, *, trust_domain: str = "sandbox"):
        self.trust_domain = trust_domain
        self._keys: dict[str, Ed25519PrivateKey] = {}
        self._metadata: dict[str, KeyMetadata] = {}

    def _ensure(self, key_id: str) -> Ed25519PrivateKey:
        if key_id not in self._keys:
            key = Ed25519PrivateKey.generate()
            self._keys[key_id] = key
            self._metadata[key_id] = KeyMetadata(
                key_id=key_id,
                trust_domain=self.trust_domain,
                algorithm="Ed25519",
                version=1,
                status="ACTIVE",
                created_at=dt.datetime.now(dt.UTC),
                public_key=key.public_key().public_bytes_raw(),
            )
        return self._keys[key_id]

    def sign(self, key_id: str, message: bytes) -> bytes:
        self._ensure(key_id)
        if self.revoke_status(key_id) != "ACTIVE":
            raise KeyProviderError(f"key is not active: {key_id}")
        return self._ensure(key_id).sign(message)

    def verify(self, key_id: str, message: bytes, signature: bytes) -> bool:
        self._ensure(key_id)
        if self.revoke_status(key_id) != "ACTIVE":
            return False
        try:
            self._ensure(key_id).public_key().verify(signature, message)
            return True
        except Exception:  # noqa: BLE001 - verification is a boolean boundary
            return False

    def get_public_key(self, key_id: str) -> bytes:
        self._ensure(key_id)
        return self._metadata[key_id].public_key

    def rotate(self, key_id: str) -> KeyMetadata:
        old = self._ensure(key_id)
        old_version = self._metadata[key_id].version
        key = Ed25519PrivateKey.generate()
        self._keys[key_id] = key
        metadata = KeyMetadata(
            key_id=key_id,
            trust_domain=self.trust_domain,
            algorithm="Ed25519",
            version=old_version + 1,
            status="ACTIVE",
            created_at=dt.datetime.now(dt.UTC),
            public_key=key.public_key().public_bytes_raw(),
        )
        self._metadata[key_id] = metadata
        del old
        return metadata

    def revoke_status(self, key_id: str) -> str:
        return self._metadata.get(key_id, KeyMetadata(key_id, self.trust_domain, "Ed25519", 0, "UNKNOWN", dt.datetime.now(dt.UTC), b"")).status

    def revoke(self, key_id: str) -> None:
        self._ensure(key_id)
        metadata = self._metadata[key_id]
        self._metadata[key_id] = KeyMetadata(**{**metadata.__dict__, "status": "REVOKED"})


class QualifiedHsmKeyProvider:
    """Adapter that delegates every private-key operation to an external HSM/KMS."""

    def __init__(
        self,
        *,
        sign_fn: Callable[[str, bytes], bytes],
        verify_fn: Callable[[str, bytes, bytes], bool],
        public_key_fn: Callable[[str], bytes],
        rotate_fn: Callable[[str], KeyMetadata],
        revoke_status_fn: Callable[[str], str],
    ):
        self._sign_fn = sign_fn
        self._verify_fn = verify_fn
        self._public_key_fn = public_key_fn
        self._rotate_fn = rotate_fn
        self._revoke_status_fn = revoke_status_fn

    def sign(self, key_id: str, message: bytes) -> bytes:
        return self._sign_fn(key_id, message)

    def verify(self, key_id: str, message: bytes, signature: bytes) -> bool:
        return self._verify_fn(key_id, message, signature)

    def get_public_key(self, key_id: str) -> bytes:
        return self._public_key_fn(key_id)

    def rotate(self, key_id: str) -> KeyMetadata:
        return self._rotate_fn(key_id)

    def revoke_status(self, key_id: str) -> str:
        return self._revoke_status_fn(key_id)


def register_key_provider(*, environment: str, sandbox: SandboxKeyProvider | None = None, qualified: QualifiedHsmKeyProvider | None = None) -> KeyProvider:
    if environment == "sandbox":
        return sandbox or SandboxKeyProvider()
    if qualified is None:
        raise KeyProviderError("qualified HSM/KMS provider is not registered")
    return qualified
