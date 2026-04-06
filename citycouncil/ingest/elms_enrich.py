"""Fetch meeting detail, matters, roll-call votes, and persons; build ingest bundles."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from citycouncil.config import Settings
from citycouncil.ingest.elms_adapter import _elms_meeting_row_to_bundle
from citycouncil.ingest.elms_client import ElmsClient
from citycouncil.parsing import coerce_ward_optional

logger = logging.getLogger(__name__)


def elms_roll_call_vote_to_position_code(raw: str) -> str:
    """Map ELMS roll-call ``vote`` string to :func:`normalize._pos` tokens."""
    k = (raw or "").strip().lower()
    if k in ("yea", "yes", "y", "aye"):
        return "aye"
    if k in ("nay", "no", "n"):
        return "nay"
    if k in ("abstain", "abstention"):
        return "abstain"
    if k in ("absent", "not present", "not voting", "nv", "excused", ""):
        return "absent"
    # "Present" often recorded when not voting on consent — treat as abstain for tallies
    if k in ("present", "paired", "recused", "recusal"):
        return "abstain"
    logger.debug("Unknown ELMS vote value %r; defaulting to absent", raw)
    return "absent"


def _matter_to_ordinance_dict(matter: dict[str, Any]) -> dict[str, Any]:
    mid = matter.get("matterId")
    if not mid:
        raise ValueError("matter missing matterId")
    sponsor_id = matter.get("filingSponsorId")
    sponsors = matter.get("sponsors") or []
    if not sponsor_id and sponsors:
        sponsor_id = sponsors[0].get("personId")
    return {
        "id": str(mid),
        "title": str(matter.get("title") or matter.get("shortTitle") or mid),
        "sponsor_id": str(sponsor_id) if sponsor_id else None,
        "introduced_date": matter.get("introductionDate"),
        "topic_tags": None,
        "elms": matter,
    }


def _person_to_member_row(person: dict[str, Any]) -> dict[str, Any]:
    pid = person.get("personId")
    if not pid:
        raise ValueError("person missing personId")
    name = str(person.get("displayName") or "").strip() or str(pid)
    return {
        "id": str(pid),
        "name": name,
        "ward": coerce_ward_optional(person.get("ward")),
        "body": None,
        "elms": person,
    }


async def enrich_meeting_bundle(
    client: httpx.AsyncClient,
    api: ElmsClient,
    settings: Settings,
    meeting_external_id: str,
) -> dict[str, Any]:
    """Return a fixture-shaped bundle with ordinances, agenda, and roll-call votes."""
    detail = await api.get_meeting_detail(client, meeting_external_id)
    agenda = detail.get("agenda")
    if not isinstance(agenda, list) or not agenda:
        return _elms_meeting_row_to_bundle(detail)

    cap = settings.elms_enrich_max_agenda_items
    agenda_slice = agenda[:cap]
    matter_ids: list[str] = []
    seen: set[str] = set()
    for item in agenda_slice:
        mid = item.get("matterId")
        if not mid or mid in seen:
            continue
        seen.add(str(mid))
        matter_ids.append(str(mid))

    sem = asyncio.Semaphore(settings.elms_enrich_concurrency)

    async def _run(coro: Any) -> Any:
        async with sem:
            return await coro

    matter_payloads: dict[str, dict[str, Any]] = {}
    results = await asyncio.gather(
        *[_run(api.get_matter_detail(client, mid)) for mid in matter_ids],
        return_exceptions=True,
    )
    for mid, res in zip(matter_ids, results, strict=True):
        if isinstance(res, BaseException):
            logger.warning("ELMS matter %s failed: %s", mid, res)
            continue
        matter_payloads[mid] = res

    roll_by_matter: dict[str, list[dict[str, Any]]] = {}
    vresults = await asyncio.gather(
        *[
            _run(api.get_meeting_matter_votes(client, meeting_external_id, mid))
            for mid in matter_ids
        ],
        return_exceptions=True,
    )
    for mid, res in zip(matter_ids, vresults, strict=True):
        if isinstance(res, BaseException):
            logger.warning("ELMS votes %s / %s failed: %s", meeting_external_id, mid, res)
            roll_by_matter[mid] = []
        else:
            roll_by_matter[mid] = res

    person_ids: set[str] = set()
    for mid in matter_ids:
        m = matter_payloads.get(mid)
        if m:
            sid = m.get("filingSponsorId")
            if sid:
                person_ids.add(str(sid))
            for sp in m.get("sponsors") or []:
                pid = sp.get("personId")
                if pid:
                    person_ids.add(str(pid))
        for row in roll_by_matter.get(mid) or []:
            pid = row.get("personId")
            if pid:
                person_ids.add(str(pid))

    persons: dict[str, dict[str, Any]] = {}
    if person_ids:
        pres = await asyncio.gather(
            *[_run(api.get_person_detail(client, pid)) for pid in sorted(person_ids)],
            return_exceptions=True,
        )
        for pid, res in zip(sorted(person_ids), pres, strict=True):
            if isinstance(res, BaseException):
                logger.warning("ELMS person %s failed: %s", pid, res)
                continue
            persons[pid] = res

    members_by_id: dict[str, dict[str, Any]] = {}
    for pid in sorted(persons):
        members_by_id[pid] = _person_to_member_row(persons[pid])

    ordinances: list[dict[str, Any]] = []
    for mid in matter_ids:
        m = matter_payloads.get(mid)
        if m:
            ordinances.append(_matter_to_ordinance_dict(m))
        else:
            line = next((x for x in agenda_slice if str(x.get("matterId")) == mid), None)
            ordinances.append(
                {
                    "id": mid,
                    "title": str((line or {}).get("matterTitle") or mid),
                    "sponsor_id": None,
                    "introduced_date": None,
                    "topic_tags": None,
                    "elms": {"matterId": mid, "from": "agenda_only"},
                }
            )

    agenda_items: list[dict[str, Any]] = []
    for idx, item in enumerate(agenda_slice, start=1):
        mid = item.get("matterId")
        if not mid:
            continue
        raw_txt = item.get("actionText") or item.get("matterTitle") or item.get("actionName")
        agenda_items.append(
            {
                "sequence": idx,
                "ordinance_id": str(mid),
                "raw_text": raw_txt,
                "elms": item,
            }
        )

    votes_out: list[dict[str, Any]] = []
    for mid in matter_ids:
        roll = roll_by_matter.get(mid) or []
        if not roll:
            continue
        ayes = nays = abstentions = 0
        vmembers: list[dict[str, Any]] = []
        for row in roll:
            code = elms_roll_call_vote_to_position_code(str(row.get("vote") or ""))
            if code == "aye":
                ayes += 1
            elif code == "nay":
                nays += 1
            elif code == "abstain":
                abstentions += 1
            pid = str(row.get("personId") or "")
            if pid and pid not in members_by_id:
                try:
                    p = await api.get_person_detail(client, pid)
                    persons[pid] = p
                    members_by_id[pid] = _person_to_member_row(p)
                except Exception as e:
                    logger.warning("ELMS lazy person %s failed: %s", pid, e)
                    continue
            if pid:
                vmembers.append({"member_id": pid, "position": code})

        vote_ext = f"{meeting_external_id}-{mid}"
        votes_out.append(
            {
                "id": vote_ext,
                "ordinance_id": mid,
                "result": None,
                "ayes": ayes,
                "nays": nays,
                "abstentions": abstentions,
                "members": vmembers,
                "elms": roll,
            }
        )

    members_out = sorted(members_by_id.values(), key=lambda r: r["id"])

    bundle: dict[str, Any] = {
        "id": str(detail["meetingId"]),
        "date": detail.get("date"),
        "body": detail.get("body"),
        "location": detail.get("location"),
        "status": detail.get("status"),
        "members": members_out,
        "ordinances": ordinances,
        "agenda_items": agenda_items,
        "votes": votes_out,
        "elms": detail,
        "elms_enriched": True,
    }
    return bundle


async def maybe_enrich_poll_payload(
    client: httpx.AsyncClient,
    settings: Settings,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Enrich the first N meetings in a ``{\"meetings\": [...]}`` payload."""
    meetings = payload.get("meetings")
    if not isinstance(meetings, list) or not meetings:
        return payload

    api = ElmsClient(settings)
    out: list[dict[str, Any]] = []
    limit = settings.elms_enrich_max_meetings
    for i, m in enumerate(meetings):
        if i >= limit:
            out.append(m)
            continue
        mid = m.get("id")
        if not mid:
            out.append(m)
            continue
        try:
            out.append(await enrich_meeting_bundle(client, api, settings, str(mid)))
        except Exception as e:
            logger.warning("ELMS enrich failed for meeting %s: %s", mid, e)
            out.append(m)
    return {"meetings": out}
