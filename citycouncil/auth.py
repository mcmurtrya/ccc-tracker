"""Admin API authentication (shared secret)."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from citycouncil.config import get_settings


async def verify_admin(
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
    authorization: str | None = Header(None),
) -> None:
    """Require ``CITYCOUNCIL_ADMIN_API_KEY`` via ``X-Admin-Key`` or ``Authorization: Bearer <key>``."""
    settings = get_settings()
    expected = settings.admin_api_key
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin endpoints disabled: set CITYCOUNCIL_ADMIN_API_KEY",
        )
    provided = x_admin_key
    if not provided and authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if not provided:
        raise HTTPException(status_code=401, detail="Missing X-Admin-Key or Authorization Bearer token")
    if len(provided) != len(expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Unauthorized")
