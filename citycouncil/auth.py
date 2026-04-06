"""Admin API authentication (shared secret)."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from citycouncil.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


def _bearer_token_from_authorization(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization[7:].strip() or None


def _resolve_provided_key(
    x_admin_key: str | None,
    authorization: str | None,
) -> str | None:
    if x_admin_key:
        return x_admin_key
    return _bearer_token_from_authorization(authorization)


def verify_admin(
    settings: SettingsDep,
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
    authorization: str | None = Header(None),
) -> None:
    """Require ``CITYCOUNCIL_ADMIN_API_KEY`` via ``X-Admin-Key`` or ``Authorization: Bearer <key>``."""
    expected = settings.admin_api_key_value()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin endpoints disabled: set CITYCOUNCIL_ADMIN_API_KEY",
        )
    provided = _resolve_provided_key(x_admin_key, authorization)
    if not provided:
        raise HTTPException(status_code=401, detail="Missing X-Admin-Key or Authorization Bearer token")
    if len(provided) != len(expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Unauthorized")
