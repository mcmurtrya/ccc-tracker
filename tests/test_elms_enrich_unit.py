import httpx
import pytest

from citycouncil.config import Settings
from citycouncil.ingest.elms_enrich import elms_roll_call_vote_to_position_code, enrich_meeting_bundle


def test_elms_vote_strings() -> None:
    assert elms_roll_call_vote_to_position_code("Yea") == "aye"
    assert elms_roll_call_vote_to_position_code("Nay") == "nay"
    assert elms_roll_call_vote_to_position_code("Abstain") == "abstain"
    assert elms_roll_call_vote_to_position_code("Absent") == "absent"
    assert elms_roll_call_vote_to_position_code("Present") == "abstain"


@pytest.mark.asyncio
async def test_enrich_meeting_bundle_with_mocks() -> None:
    meeting_id = "M1-GUID"
    matter_id = "MAT-GUID"
    person_id = "P1-GUID"

    meeting_detail = {
        "meetingId": meeting_id,
        "date": "2026-01-15T15:00:00+00:00",
        "body": "City Council",
        "location": "Hall",
        "status": "Adjourned",
        "agenda": [
            {
                "matterId": matter_id,
                "matterTitle": "Test matter",
                "matterType": "Ordinance",
                "recordNumber": "O2026-1",
                "actionName": "Passed",
                "actionText": "Passed",
                "sort": 0,
                "agendaItemDescription": None,
            }
        ],
    }
    matter_detail = {
        "matterId": matter_id,
        "title": "Test matter",
        "recordNumber": "O2026-1",
        "filingSponsorId": person_id,
        "sponsors": [],
        "introductionDate": "2026-01-01T00:00:00+00:00",
    }
    roll = [{"voterName": "A", "vote": "Yea", "personId": person_id}]
    person = {
        "personId": person_id,
        "displayName": "Ald. Test",
        "ward": "1",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/meeting/{meeting_id}"):
            return httpx.Response(200, json=meeting_detail)
        if path.endswith(f"/matter/{matter_id}"):
            return httpx.Response(200, json=matter_detail)
        if path.endswith(f"/meeting/{meeting_id}/matter/{matter_id}/votes"):
            return httpx.Response(200, json=roll)
        if path.endswith(f"/person/{person_id}"):
            return httpx.Response(200, json=person)
        return httpx.Response(404, json={"error": path})

    transport = httpx.MockTransport(handler)
    settings = Settings(
        database_url="postgresql+asyncpg://x:x@localhost:5432/x",
        elms_api_base="https://elms.test",
        elms_enrich_max_agenda_items=10,
        elms_enrich_concurrency=2,
    )
    async with httpx.AsyncClient(transport=transport, base_url="https://elms.test") as client:
        from citycouncil.ingest.elms_client import ElmsClient

        bundle = await enrich_meeting_bundle(client, ElmsClient(settings), settings, meeting_id)

    assert bundle["elms_enriched"] is True
    assert bundle["id"] == meeting_id
    assert len(bundle["ordinances"]) == 1
    assert bundle["ordinances"][0]["id"] == matter_id
    assert len(bundle["agenda_items"]) == 1
    assert bundle["agenda_items"][0]["ordinance_id"] == matter_id
    assert len(bundle["votes"]) == 1
    assert bundle["votes"][0]["ayes"] == 1
    assert bundle["votes"][0]["nays"] == 0
    assert bundle["votes"][0]["members"][0]["member_id"] == person_id
    assert any(m["id"] == person_id for m in bundle["members"])


@pytest.mark.asyncio
async def test_enrich_empty_agenda_returns_minimal() -> None:
    meeting_id = "M2"
    detail = {
        "meetingId": meeting_id,
        "date": "2026-01-15T15:00:00+00:00",
        "body": "X",
        "location": "Y",
        "status": "S",
        "agenda": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(f"/meeting/{meeting_id}"):
            return httpx.Response(200, json=detail)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    settings = Settings(
        database_url="postgresql+asyncpg://x:x@localhost:5432/x",
        elms_api_base="https://elms.test",
    )
    async with httpx.AsyncClient(transport=transport, base_url="https://elms.test") as client:
        from citycouncil.ingest.elms_client import ElmsClient

        bundle = await enrich_meeting_bundle(client, ElmsClient(settings), settings, meeting_id)

    assert bundle.get("elms_enriched") is None
    assert bundle["votes"] == []
