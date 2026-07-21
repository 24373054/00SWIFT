"""Application configuration driven by environment variables.

Three environment modes (``SWIFT_ENV``):
* ``sandbox`` — fully local mock. Self-signed CA generates client certs on
  credential creation. All endpoints serve mocked data from the local DB.
* ``pilot`` — real SWIFT sandbox hosts. Requires a real PKI cert uploaded per
  credential. Endpoints forward to the real SWIFT sandbox via httpx.
* ``live`` — real SWIFT production. Strict PKI, startup confirmation required,
  write operations default to ``dry_run=true`` for safety.

The ``Settings`` singleton is created once at import time. Tests can override
via environment variables or by constructing a new ``Settings`` instance.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

EnvMode = Literal["sandbox", "pilot", "live"]


class Settings(BaseSettings):
    """Strongly-typed settings loaded from ``.env`` and process environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment mode.
    swift_env: EnvMode = "sandbox"

    # Server.
    host: str = "127.0.0.1"
    port: int = 8765

    # Database.
    db_url: str = "sqlite:///swift_dev.db"

    # PKI / certificates.
    certs_dir: str = "certs"
    swift_ca_path: str | None = None

    # OAuth.
    oauth_token_ttl_default: int = 3600
    clock_skew_seconds: int = 10
    jti_ttl_seconds: int = 3660

    # Internal /api/* admin auth. In sandbox an empty token is permitted only
    # when explicitly running on loopback. Pilot/live always require a token.
    admin_api_token: str | None = None

    # Browser/API hardening. Comma-separated origins; sandbox defaults to local UI.
    cors_origins: str = (
        "http://localhost,http://127.0.0.1,http://localhost:8765,http://127.0.0.1:8765"
    )
    audit_body_limit: int = 4096

    # Live-mode hosts.
    live_host_oauth: str | None = None
    live_host_preval: str | None = None
    live_host_swiftref: str | None = None
    live_host_tracker: str | None = None
    live_host_messaging: str | None = None

    # HTTP client.
    proxy: str | None = None
    enable_http_logs: bool = False

    # ---- derived helpers ----

    @property
    def is_sandbox(self) -> bool:
        return self.swift_env == "sandbox"

    @property
    def is_live(self) -> bool:
        return self.swift_env == "live"

    @property
    def is_mock(self) -> bool:
        """True when endpoints serve local mock data (sandbox only)."""
        return self.is_sandbox

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def certs_abs_dir(self) -> str:
        """Absolute path to the certs directory."""
        if os.path.isabs(self.certs_dir):
            return self.certs_dir
        backend_root = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(backend_root, self.certs_dir)

    def certs_ca_dir(self) -> str:
        return os.path.join(self.certs_abs_dir(), "ca")

    def certs_apps_dir(self) -> str:
        return os.path.join(self.certs_abs_dir(), "apps")

    def validate_for_live(self) -> None:
        """Validate that live-mode safety settings are in place.

        Called at startup when ``SWIFT_ENV=live``. Raises ``RuntimeError`` if
        any required safety setting is missing.
        """
        if not self.admin_api_token:
            raise RuntimeError(
                "ADMIN_API_TOKEN must be set when SWIFT_ENV=live "
                "(internal management endpoints cannot be unauthenticated in live mode)"
            )
        if not (
            self.live_host_oauth
            and self.live_host_preval
            and self.live_host_swiftref
            and self.live_host_tracker
            and self.live_host_messaging
        ):
            raise RuntimeError("All LIVE_HOST_* settings must be configured when SWIFT_ENV=live")

    def validate_for_pilot(self) -> None:
        """Validate pilot-mode settings."""
        if not self.admin_api_token:
            raise RuntimeError("ADMIN_API_TOKEN must be set when SWIFT_ENV=pilot")
        if not (
            self.live_host_oauth
            and self.live_host_preval
            and self.live_host_swiftref
            and self.live_host_tracker
            and self.live_host_messaging
        ):
            raise RuntimeError("All LIVE_HOST_* settings must be configured when SWIFT_ENV=pilot")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()


def reload_settings() -> Settings:
    """Force-reload settings (used by tests after changing env vars)."""
    get_settings.cache_clear()
    return get_settings()
