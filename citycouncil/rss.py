"""RSS 2.0 for activity items (Phase 5)."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from email.utils import format_datetime
from citycouncil.activity import ActivityItem


def _pub_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt, usegmt=True)


def _item_title(item: ActivityItem) -> str:
    kind = item["kind"]
    if kind == "meeting":
        m = item["meeting"]
        d = m.get("meeting_date") or ""
        b = m.get("body") or "Meeting"
        return f"Meeting {d}: {b}"
    if kind == "ordinance":
        o = item["ordinance"]
        return o.get("title") or "Ordinance"
    if kind == "document":
        d = item["document"]
        return d.get("file_name") or "Document"
    return kind


def _item_link(item: ActivityItem, base_url: str) -> str:
    base = base_url.rstrip("/")
    kind = item["kind"]
    if kind == "meeting":
        return f"{base}/meetings/{item['id']}"
    if kind == "ordinance":
        return f"{base}/ordinances/{item['id']}"
    if kind == "document":
        d = item.get("document") or {}
        if d.get("source_url"):
            return str(d["source_url"])
        return str(d.get("uri") or base)
    return base


def _item_description(item: ActivityItem) -> str:
    kind = item["kind"]
    if kind == "meeting":
        m = item["meeting"]
        parts = [
            f"Date: {m.get('meeting_date')}",
            f"Location: {m.get('location') or ''}",
            f"Status: {m.get('status') or ''}",
        ]
        return "\n".join(parts)
    if kind == "ordinance":
        o = item["ordinance"]
        parts = [o.get("title") or ""]
        if o.get("topic_tags"):
            parts.append("Tags: " + ", ".join(o["topic_tags"]))
        return "\n".join(parts)
    if kind == "document":
        d = item["document"] or {}
        return f"{d.get('file_name') or ''}\n{d.get('parse_status') or ''}"
    return ""


def render_activity_rss(
    items: list[ActivityItem],
    *,
    feed_title: str,
    feed_link: str,
    feed_description: str,
    self_link: str,
    base_url: str,
) -> str:
    """Build RSS 2.0 XML (UTF-8) with Atom self link."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        f"<title>{html.escape(feed_title, quote=False)}</title>",
        f"<link>{html.escape(feed_link, quote=False)}</link>",
        f"<description>{html.escape(feed_description, quote=False)}</description>",
        f'<atom:link href="{html.escape(self_link, quote=True)}" rel="self" type="application/rss+xml" />',
        "<generator>citycouncil</generator>",
    ]
    for item in items:
        title = html.escape(_item_title(item), quote=False)
        link = html.escape(_item_link(item, base_url), quote=False)
        desc = html.escape(_item_description(item), quote=False)
        pub = _pub_date(item["activity_at"])
        guid = html.escape(f"tag:citycouncil:{item['kind']}:{item['id']}", quote=True)
        lines.append("<item>")
        lines.append(f"<title>{title}</title>")
        lines.append(f"<link>{link}</link>")
        lines.append(f"<description>{desc}</description>")
        lines.append(f"<pubDate>{pub}</pubDate>")
        lines.append(f'<guid isPermaLink="false">{guid}</guid>')
        lines.append("</item>")
    lines.append("</channel>")
    lines.append("</rss>")
    return "\n".join(lines) + "\n"
