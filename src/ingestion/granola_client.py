"""
Granola Enterprise API client.

Verified against the official docs at https://docs.granola.ai/introduction
(fetched 2026-05-28).

Endpoints:
  GET /v1/notes                          — list workspace-accessible notes
  GET /v1/notes/{id}?include=transcript  — fetch a single note + transcript

Auth: Bearer token in Authorization header.
Rate limit: 25 burst / 5 req/s sustained / 300 req/min.
Scope: read-only on notes shared to workspace-wide folders.

Speaker labels: Granola identifies the user's own microphone (`"microphone"`)
vs everything else (`"speaker"`). It does NOT distinguish individual non-user
speakers — so on a 3-way call with SE + AE + prospect, we see:
  - "microphone" → the SE (the Granola account owner)
  - "speaker"    → AE and prospect mixed together
We attribute SE turns by name and let the scoring prompt do its best to
attribute the remaining speakers from content + the attendee list.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Union

import requests


GRANOLA_BASE = os.getenv("GRANOLA_BASE", "https://public-api.granola.ai/v1")


@dataclass
class GranolaNote:
    """Minimal note metadata from the list endpoint."""
    id: str
    title: str
    owner_name: str
    owner_email: str
    created_at: str
    updated_at: str


@dataclass
class GranolaNoteDetail:
    """Full note from /v1/notes/{id} including transcript + calendar event."""
    id: str
    title: str
    owner_name: str
    owner_email: str
    created_at: str
    updated_at: str
    attendees: List[dict] = field(default_factory=list)
    folder_membership: List[dict] = field(default_factory=list)
    summary_text: Optional[str] = None
    summary_markdown: Optional[str] = None
    transcript_segments: List[dict] = field(default_factory=list)
    calendar_event_title: Optional[str] = None
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None
    organiser: Optional[str] = None
    raw: dict = field(default_factory=dict)

    def external_attendees(self, internal_domain: str) -> List[dict]:
        """Attendees whose email is NOT under the SE's company domain."""
        out = []
        for a in self.attendees:
            email = (a.get("email") or "").lower()
            if email and not email.endswith(f"@{internal_domain}"):
                out.append(a)
        return out

    def is_external(self, internal_domain: str) -> bool:
        return len(self.external_attendees(internal_domain)) > 0

    def duration_min(self) -> int:
        """Derive duration from scheduled start/end times."""
        from datetime import datetime
        try:
            s = datetime.fromisoformat(self.scheduled_start.replace("Z", "+00:00"))
            e = datetime.fromisoformat(self.scheduled_end.replace("Z", "+00:00"))
            return max(0, int((e - s).total_seconds() / 60))
        except Exception:
            return 0

    def transcript_text(self, se_name: str) -> str:
        """Format transcript as canonical 'Speaker: text' lines.

        We label microphone-source turns with the SE's actual name (since the
        Granola account owner is the SE), and speaker-source turns generically
        as 'Speaker' (because Granola can't distinguish individual non-user
        speakers). The scoring prompt is given the attendee list separately
        so Claude can attribute AE vs Prospect from content.
        """
        lines = []
        for seg in self.transcript_segments:
            source = (seg.get("speaker") or {}).get("source", "")
            label = se_name if source == "microphone" else "Speaker"
            text = (seg.get("text") or "").strip()
            if text:
                lines.append(f"{label}: {text}")
        return "\n".join(lines)


class GranolaClient:
    def __init__(self, api_key: Optional[str] = None, base: str = GRANOLA_BASE):
        self.api_key = api_key or os.getenv("GRANOLA_API_KEY")
        self.base = base.rstrip("/")
        if not self.api_key:
            raise RuntimeError("GRANOLA_API_KEY env var not set")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def list_notes_since(
        self,
        created_after: Union[str, datetime, None] = None,
        updated_after: Union[str, datetime, None] = None,
        page_size: int = 30,
        max_pages: int = 20,
    ) -> List[GranolaNote]:
        """
        List notes. Pass EITHER created_after (notes created since) OR
        updated_after (notes with any modification — including folder
        membership changes — since). For our sync we use updated_after so
        retroactively-shared notes get caught.

        Accepts a datetime (preferred) or pre-formatted ISO string.
        Datetimes are normalized to ISO 8601 in UTC with 'Z' suffix and no
        microseconds (Granola rejects microseconds).

        Walks the cursor pagination until no more pages or max_pages hit.
        """
        if created_after is None and updated_after is None:
            raise ValueError("must pass either created_after or updated_after")

        def _normalize(value) -> str:
            if isinstance(value, datetime):
                dt = value
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            s = str(value)
            if "." in s:
                pre, _, rest = s.partition(".")
                for sep in ("+", "-", "Z"):
                    idx = rest.find(sep)
                    if idx > 0:
                        s = pre + rest[idx:]
                        break
                else:
                    s = pre
            return s.replace("+00:00", "Z")

        date_param = {}
        if updated_after is not None:
            date_param["updated_after"] = _normalize(updated_after)
        if created_after is not None:
            date_param["created_after"] = _normalize(created_after)

        out: List[GranolaNote] = []
        cursor = None
        for _ in range(max_pages):
            params = {
                **date_param,
                "page_size": min(max(page_size, 1), 30),
            }
            if cursor:
                params["cursor"] = cursor
            r = requests.get(f"{self.base}/notes", headers=self._headers(),
                             params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            for n in data.get("notes", []):
                owner = n.get("owner") or {}
                out.append(GranolaNote(
                    id=n["id"],
                    title=n.get("title") or "Untitled",
                    owner_name=owner.get("name", ""),
                    owner_email=(owner.get("email") or "").lower(),
                    created_at=n.get("created_at", ""),
                    updated_at=n.get("updated_at", ""),
                ))
            if not data.get("hasMore"):
                break
            cursor = data.get("cursor")
            if not cursor:
                break
        return out

    def get_note(self, note_id: str, include_transcript: bool = True) -> GranolaNoteDetail:
        """Fetch a single note with optional transcript."""
        params = {}
        if include_transcript:
            params["include"] = "transcript"
        r = requests.get(f"{self.base}/notes/{note_id}", headers=self._headers(),
                         params=params, timeout=30)
        r.raise_for_status()
        d = r.json()
        owner = d.get("owner") or {}
        cal = d.get("calendar_event") or {}
        return GranolaNoteDetail(
            id=d["id"],
            title=d.get("title") or "Untitled",
            owner_name=owner.get("name", ""),
            owner_email=(owner.get("email") or "").lower(),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            attendees=d.get("attendees") or [],
            folder_membership=d.get("folder_membership") or [],
            summary_text=d.get("summary_text"),
            summary_markdown=d.get("summary_markdown"),
            transcript_segments=d.get("transcript") or [],
            calendar_event_title=cal.get("event_title"),
            scheduled_start=cal.get("scheduled_start_time"),
            scheduled_end=cal.get("scheduled_end_time"),
            organiser=cal.get("organiser"),
            raw=d,
        )
