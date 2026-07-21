"""Authentication and scope dependencies for the e-CNY API."""

from __future__ import annotations

from fastapi import Depends, Header

from auth.dependencies import get_cred, require_admin_token
from auth.oauth import get_token_scopes
from config import get_settings
from core.errors import insufficient_scope, token_not_provided
from database import get_db


def require_ecny_scope(required: str | None = None):
    """Require a valid sandbox admin token or an OAuth e-CNY scope."""

    def _check(
        x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
        authorization: str | None = Header(None),
        db=Depends(get_db),
    ):
        settings = get_settings()
        if settings.is_sandbox and x_admin_token is not None:
            require_admin_token(x_admin_token)
            return None
        if settings.is_sandbox and not settings.admin_api_token and not authorization:
            return None
        if not authorization:
            raise token_not_provided()
        cred = get_cred(authorization=authorization, db=db)
        if required:
            scopes = set(get_token_scopes(authorization, db))
            if required not in scopes and "ecny.api" not in scopes:
                raise insufficient_scope(required)
        return cred

    return _check


require_ecny_cred = require_ecny_scope()
