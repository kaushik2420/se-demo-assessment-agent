"""
Community events feed — auto-fetched from public RSS / iCal sources, merged
with a curated baseline so the panel is never empty.

Architecture:
  - SOURCES: list of (name, url, kind) tuples — easy to add/remove
  - CACHE: in-memory dict with 6h TTL — avoids hammering external feeds
  - get_events(): merges live-fetched + curated, dedupes, sorts by date

Sources are added defensively: any one feed failing falls back gracefully.
Add new sources by appending to SOURCES below.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Literal


FeedKind = Literal["rss", "ical"]

# ----------------------------------------------------------------------------
# Configure your sources here.
# RSS feeds: anything that returns valid RSS/Atom XML.
# iCal feeds: anything that returns valid .ics text/calendar content.
# ----------------------------------------------------------------------------
SOURCES: list[tuple[str, str, FeedKind]] = [
    # PreSales Collective blog (covers community events, summit announcements)
    ("PreSales Collective", "https://www.presalescollective.com/blog?format=rss", "rss"),
    # The Sales Engineer Podcast (community-relevant content; speakers + events often)
    ("The Sales Engineer Podcast", "https://feeds.buzzsprout.com/853259.rss", "rss"),
    # Sales Hacker — broader sales community (frequently announces events / webinars)
    ("Sales Hacker", "https://www.saleshacker.com/feed/", "rss"),
    # Add more sources by appending tuples here. Examples:
    #   ("Your Meetup", "https://www.meetup.com/<group>/events/ical/", "ical"),
    #   ("PSC iCal",    "https://example.com/psc.ics", "ical"),
]

CACHE_TTL_SECONDS = 6 * 60 * 60   # 6 hours
_cache: dict = {"data": None, "fetched_at": 0}


@dataclass
class Event:
    title: str
    source: str
    url: str
    date: str | None           # ISO8601 if known, else None
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------------
# Curated baseline — well-known recurring events with real URLs.
# Edit this list to add internal events (SurveySparrow internal SE huddles, etc).
# ----------------------------------------------------------------------------
def _curated() -> list[Event]:
    return [
        Event(
            title="PreSales Collective Summit (annual)",
            source="PreSales Collective",
            url="https://www.presalescollective.com/summit",
            date=None,
            description="Annual summit for SE / Solutions Consulting community. "
                        "Sessions, networking, vendor showcase.",
        ),
        Event(
            title="PSC Community — monthly virtual meetups",
            source="PreSales Collective",
            url="https://www.presalescollective.com/events",
            date=None,
            description="Recurring virtual meetups by region / topic. "
                        "Join the PSC Slack to get invites.",
        ),
        Event(
            title="PreSales Mastermind — Slack community",
            source="PreSales Mastermind",
            url="https://presalesmastermind.com/",
            date=None,
            description="Open community + events for solution engineers.",
        ),
        Event(
            title="DemoFest — annual demo skills conference",
            source="PreSales Collective",
            url="https://www.presalescollective.com/demofest",
            date=None,
            description="Skills-focused event on demo storytelling, "
                        "discovery, and POCs.",
        ),
        Event(
            title="The Sales Engineer Podcast — weekly episodes",
            source="The Sales Engineer Podcast",
            url="https://thesalesengineer.com/podcast",
            date=None,
            description="Recurring podcast with SE leaders and operators.",
        ),
    ]


# ----------------------------------------------------------------------------
# Fetchers
# ----------------------------------------------------------------------------
def _fetch_rss(name: str, url: str) -> list[Event]:
    """Fetch and parse an RSS/Atom feed into Event objects."""
    try:
        import feedparser
        d = feedparser.parse(url)
        items = []
        for entry in d.entries[:8]:  # cap per feed
            published = entry.get("published") or entry.get("updated") or ""
            try:
                # Normalize date to ISO if parseable
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(published) if published else None
                date_iso = dt.isoformat() if dt else None
            except Exception:
                date_iso = published or None
            items.append(Event(
                title=entry.get("title", "Untitled"),
                source=name,
                url=entry.get("link", url),
                date=date_iso,
                description=(entry.get("summary", "") or "")[:240],
            ))
        return items
    except Exception as e:
        print(f"[events] RSS fetch failed for {name}: {e}")
        return []


def _fetch_ical(name: str, url: str) -> list[Event]:
    """Fetch and parse an iCal feed into Event objects (upcoming only)."""
    try:
        import httpx
        from icalendar import Calendar
        resp = httpx.get(url, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.text)
        items = []
        now = datetime.now(timezone.utc)
        for component in cal.walk("VEVENT"):
            try:
                start = component.get("DTSTART").dt
                if hasattr(start, "tzinfo") and start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                # Skip past events
                if hasattr(start, "year"):
                    start_dt = start if isinstance(start, datetime) else datetime.combine(start, datetime.min.time(), timezone.utc)
                    if start_dt < now - timedelta(days=1):
                        continue
                    date_iso = start_dt.isoformat()
                else:
                    date_iso = str(start)
                items.append(Event(
                    title=str(component.get("SUMMARY", "Event")),
                    source=name,
                    url=str(component.get("URL", url)),
                    date=date_iso,
                    description=str(component.get("DESCRIPTION", ""))[:240],
                ))
            except Exception:
                continue
        # Take next 8 upcoming
        items.sort(key=lambda e: e.date or "")
        return items[:8]
    except Exception as e:
        print(f"[events] iCal fetch failed for {name}: {e}")
        return []


def _fetch_all() -> list[Event]:
    out: list[Event] = []
    for name, url, kind in SOURCES:
        if kind == "rss":
            out.extend(_fetch_rss(name, url))
        elif kind == "ical":
            out.extend(_fetch_ical(name, url))
    return out


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------
def get_events(force_refresh: bool = False) -> dict:
    """Return cached events feed; refresh if stale or forced."""
    now = time.time()
    fresh = (now - _cache["fetched_at"]) < CACHE_TTL_SECONDS
    if not force_refresh and fresh and _cache["data"] is not None:
        return _cache["data"]

    live = _fetch_all()
    curated = _curated()

    # Dedupe by URL
    seen_urls = set()
    merged: list[Event] = []
    # Live first so curated baseline is a fallback when feeds have overlap
    for ev in live + curated:
        if ev.url and ev.url in seen_urls:
            continue
        seen_urls.add(ev.url)
        merged.append(ev)

    # Sort: dated items first (by date asc), undated last
    def _sort_key(e: Event):
        return (e.date is None, e.date or "")
    merged.sort(key=_sort_key)

    payload = {
        "events": [e.to_dict() for e in merged[:20]],
        "sources": [{"name": n, "url": u, "kind": k} for n, u, k in SOURCES],
        "live_count": len(live),
        "curated_count": len(curated),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cache_ttl_hours": CACHE_TTL_SECONDS // 3600,
    }
    _cache["data"] = payload
    _cache["fetched_at"] = now
    return payload
