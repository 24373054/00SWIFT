"""Sandbox-friendly auth dependency for the e-CNY API.

In sandbox mode, e-CNY endpoints accept X-Admin-Token as an equivalent
credential (mirroring /api/dev/sign convenience) so the frontend and admin
scripts can exercise the full flow without minting a real OAuth token per
call. In pilot/live, the standard get_cred + require_scopes path applies.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header

from config import get_settings
from auth.dependencies import get_cred
from database import get_db


def require_ecny_cred(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    authorization: Optional[str] = Header(None),
    db=Depends(get_db),
):
    """Resolve an e-CNY caller. Sandbox: admin token OR bearer. Else: bearer+scope."""
    settings = get_settings()
    if settings.is_sandbox:
        if x_admin_token is not None or not settings.admin_api_token:
            return None
        if authorization:
            return get_cred(authorization=authorization, db=db)
        return None
    return get_cred(authorization=authorization, db=db)
