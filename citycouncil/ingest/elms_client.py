"""Thin async HTTP helpers for the Chicago eLMS API (paths match Swagger)."""

from __future__ import annotations

from typing import Any

import httpx

from citycouncil.config import Settings


class ElmsClient:
    """Stateless URL builders + JSON GET helpers."""

    def __init__(self, settings: Settings) -> None:
        self._base = settings.elms_api_base.rstrip("/")

    def meeting_list_url(self) -> str:
        return f"{self._base}/meeting"

    def meeting_detail_url(self, meeting_id: str) -> str:
        return f"{self._base}/meeting/{meeting_id}"

    def matter_detail_url(self, matter_id: str) -> str:
        return f"{self._base}/matter/{matter_id}"

    def person_detail_url(self, person_id: str) -> str:
        return f"{self._base}/person/{person_id}"

    def meeting_matter_votes_url(self, meeting_id: str, matter_id: str) -> str:
        return f"{self._base}/meeting/{meeting_id}/matter/{matter_id}/votes"

    async def get_meeting_detail(self, client: httpx.AsyncClient, meeting_id: str) -> dict[str, Any]:
        r = await client.get(self.meeting_detail_url(meeting_id))
        r.raise_for_status()
        out = r.json()
        if not isinstance(out, dict):
            raise TypeError(f"Expected meeting object, got {type(out)}")
        return out

    async def get_matter_detail(self, client: httpx.AsyncClient, matter_id: str) -> dict[str, Any]:
        r = await client.get(self.matter_detail_url(matter_id))
        r.raise_for_status()
        out = r.json()
        if not isinstance(out, dict):
            raise TypeError(f"Expected matter object, got {type(out)}")
        return out

    async def get_person_detail(self, client: httpx.AsyncClient, person_id: str) -> dict[str, Any]:
        r = await client.get(self.person_detail_url(person_id))
        r.raise_for_status()
        out = r.json()
        if not isinstance(out, dict):
            raise TypeError(f"Expected person object, got {type(out)}")
        return out

    async def get_meeting_matter_votes(
        self, client: httpx.AsyncClient, meeting_id: str, matter_id: str
    ) -> list[dict[str, Any]]:
        r = await client.get(self.meeting_matter_votes_url(meeting_id, matter_id))
        r.raise_for_status()
        out = r.json()
        if not isinstance(out, list):
            raise TypeError(f"Expected vote list, got {type(out)}")
        return out
