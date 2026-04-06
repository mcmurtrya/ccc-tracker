"""Tests for :func:`citycouncil.auth.verify_admin` (timing-safe compare)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from citycouncil.auth import verify_admin


@pytest.mark.asyncio
async def test_verify_admin_wrong_digest_same_length(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CITYCOUNCIL_ADMIN_API_KEY", "dev-admin-secret-key")
    with pytest.raises(HTTPException) as exc:
        await verify_admin(x_admin_key="wrong-key-same-len!!")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Unauthorized"


@pytest.mark.asyncio
async def test_verify_admin_bearer_wrong_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CITYCOUNCIL_ADMIN_API_KEY", "dev-admin-secret-key")
    with pytest.raises(HTTPException) as exc:
        await verify_admin(
            x_admin_key=None,
            authorization="Bearer wrong-key-same-len!!",
        )
    assert exc.value.status_code == 401
