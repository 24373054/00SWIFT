from __future__ import annotations

import pytest

from production.key_provider import (
    KeyProviderError,
    QualifiedHsmKeyProvider,
    SandboxKeyProvider,
    register_key_provider,
)


def test_sandbox_provider_signs_verifies_rotates_and_revokes_without_export_api():
    provider = SandboxKeyProvider()
    message = b"canonical-payment-request"
    signature = provider.sign("key-1", message)
    assert provider.verify("key-1", message, signature)
    assert not provider.verify("key-1", b"tampered", signature)
    before = provider.get_public_key("key-1")
    rotated = provider.rotate("key-1")
    assert rotated.version == 2
    assert provider.get_public_key("key-1") != before
    provider.revoke("key-1")
    assert provider.revoke_status("key-1") == "REVOKED"
    with pytest.raises(KeyProviderError):
        provider.sign("key-1", message)
    assert not hasattr(provider, "export_private_key")


def test_qualified_provider_requires_real_callbacks_and_never_exports_private_key():
    calls = []

    provider = QualifiedHsmKeyProvider(
        sign_fn=lambda key, message: calls.append(("sign", key, message)) or b"signature",
        verify_fn=lambda key, message, signature: calls.append(("verify", key, message, signature)) or signature == b"signature",
        public_key_fn=lambda key: b"public-key",
        rotate_fn=lambda key: (_ for _ in ()).throw(KeyProviderError("HSM unavailable")),
        revoke_status_fn=lambda key: "ACTIVE",
    )
    assert provider.sign("hsm-key", b"message") == b"signature"
    assert provider.verify("hsm-key", b"message", b"signature")
    assert calls
    with pytest.raises(KeyProviderError, match="HSM unavailable"):
        provider.rotate("hsm-key")
    assert not hasattr(provider, "export_private_key")


def test_non_sandbox_registration_without_qualified_provider_fails_closed():
    with pytest.raises(KeyProviderError, match="not registered"):
        register_key_provider(environment="pilot")
