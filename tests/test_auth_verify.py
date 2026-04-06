"""Tests for :func:`citycouncil.auth.verify_admin` (timing-safe compare)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from citycouncil.auth import verify_admin
from citycouncil.config import get_settings


def test_verify_admin_wrong_digest_same_length(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CITYCOUNCIL_ADMIN_API_KEY", "dev-admin-secret-key")
    settings = get_settings()
    with pytest.raises(HTTPException) as exc:
        verify_admin(settings, x_admin_key="wrong-key-same-len!!")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Unauthorized"


def test_verify_admin_bearer_wrong_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CITYCOUNCIL_ADMIN_API_KEY", "dev-admin-secret-key")
    settings = get_settings()
    with pytest.raises(HTTPException) as exc:
        verify_admin(
            settings,
            x_admin_key=None,
            authorization="Bearer wrong-key-same-len!!",
        )
    assert exc.value.status_code == 401
