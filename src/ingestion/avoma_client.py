"""
Avoma ingestion: pull recordings + transcripts from Avoma's API.

Avoma already records and transcribes — we just need to fetch the raw transcript
text and metadata. Cheaper than running Recall.ai on a call Avoma already covers.

API docs: https://api.avoma.com/v1/  (Bearer token auth)
"""

from __future__ import annotations

import os
from typing import List, Optional

import requests


AVOMA_BASE = "https://api.avoma.com/v1"


class AvomaClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("AVOMA_API_KEY")

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def list_meetings_since(self, since_iso: str) -> List[dict]:
        r = requests.get(
            f"{AVOMA_BASE}/meetings",
            headers=self._headers(),
            params={"from_date": since_iso, "limit": 200},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("results", [])

    def get_transcript(self, meeting_uuid: str) -> str:
        r = requests.get(
            f"{AVOMA_BASE}/meetings/{meeting_uuid}/transcript",
            headers=self._headers(), timeout=30,
        )
        r.raise_for_status()
        # Avoma returns {speakers: [...], transcript: [{speaker_id, text, start_time}]}
        d = r.json()
        speakers = {s["id"]: s["name"] for s in d.get("speakers", [])}
        return "\n".join(
            f"{speakers.get(seg['speaker_id'], 'Unknown')}: {seg['text']}"
            for seg in d.get("transcript", [])
        )

    def extract_recording_link(self, hubspot_or_url: str) -> Optional[str]:
        """For manual links like 'https://app.avoma.com/meeting/<uuid>'."""
        if "avoma.com/meeting/" in hubspot_or_url:
            return hubspot_or_url.rsplit("/", 1)[-1].split("?")[0]
        return None
