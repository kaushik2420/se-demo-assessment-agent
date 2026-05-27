"""
Granola ingestion — the single source of truth for SE call transcripts.

Why Granola:
  - One integration instead of Recall.ai + Avoma + manual upload
  - Already has transcription + speaker labels
  - Per-SE attribution is automatic (each SE's Granola account = their calls)
  - Has a public API + an MCP connector

Auth options:
  1. Per-SE OAuth (each SE connects their account once) — RECOMMENDED, no IT review
  2. Workspace-admin API key (Granola Business plan) — central, one key for all SEs
  3. MCP path — for ad-hoc reads from this agent (kaushik's workflows)

Production pattern:
  - Nightly cron: for each SE in DynamoDB `ss_se_users`, list new meetings since
    last sync, pull transcript + metadata, push into the analysis pipeline.
  - Webhook (if Granola adds one) replaces the cron for near-real-time.

Caveat: Granola is a client-side notetaker. If an SE forgets to keep the app
running, the call is silently missed. The portal's manual-upload path is the
safety net for those cases.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import requests


GRANOLA_BASE = "https://api.granola.ai/v1"


@dataclass
class GranolaMeeting:
    meeting_id: str
    title: str
    start_time: str   # ISO8601
    duration_min: int
    participants: List[str]
    se_email: Optional[str]  # which SE owns this meeting
    raw: dict


class GranolaClient:
    def __init__(self, api_key: Optional[str] = None, base: str = GRANOLA_BASE):
        self.api_key = api_key or os.getenv("GRANOLA_API_KEY")
        self.base = base

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    def list_meetings_since(self, since_iso: str, limit: int = 200) -> List[GranolaMeeting]:
        """List meetings recorded since `since_iso` (ISO8601 UTC)."""
        r = requests.get(
            f"{self.base}/meetings",
            headers=self._headers(),
            params={"from": since_iso, "limit": limit},
            timeout=30,
        )
        r.raise_for_status()
        out = []
        for m in r.json().get("meetings", []):
            out.append(GranolaMeeting(
                meeting_id=m["id"],
                title=m.get("title", ""),
                start_time=m["start_time"],
                duration_min=int(m.get("duration_seconds", 0) / 60),
                participants=[p.get("email") or p.get("name", "") for p in m.get("participants", [])],
                se_email=m.get("owner_email"),
                raw=m,
            ))
        return out

    def get_transcript(self, meeting_id: str) -> str:
        """Fetch the diarized transcript as 'Speaker: text' lines."""
        r = requests.get(
            f"{self.base}/meetings/{meeting_id}/transcript",
            headers=self._headers(), timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        # Granola format: {speakers: [...], segments: [{speaker_id, text, start}]}
        speakers = {s["id"]: s.get("name", f"Speaker {s['id']}") for s in d.get("speakers", [])}
        return "\n".join(
            f"{speakers.get(seg['speaker_id'], 'Unknown')}: {seg['text']}"
            for seg in d.get("segments", [])
        )

    def get_meeting_metadata(self, meeting_id: str) -> dict:
        r = requests.get(
            f"{self.base}/meetings/{meeting_id}",
            headers=self._headers(), timeout=10,
        )
        r.raise_for_status()
        return r.json()


# ============================================================================
# MCP-based fallback path: when kaushik uses this agent through Cowork, the
# Granola MCP connector gives Claude direct read access via fully-qualified
# tool names. The pattern below mirrors how the AvomaClient was structured.
# ============================================================================

def mcp_fetch_transcript(meeting_id: str) -> Optional[str]:
    """
    Placeholder for MCP-based fetch. In the agent runtime, the Granola MCP
    connector (mcp__granola__get_meeting_transcript) is called directly by
    Claude; this function exists so server-side jobs have a consistent shape.
    """
    raise NotImplementedError(
        "Run via the MCP connector at agent-time, or use GranolaClient with an API key."
    )
