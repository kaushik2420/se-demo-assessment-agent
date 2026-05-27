"""
Recall.ai integration.

Recall.ai is a single API that joins Zoom, Google Meet, MS Teams (and Webex) as
a silent participant, records, transcribes (Deepgram / AssemblyAI / Whisper), and
delivers diarized output via webhook + signed S3 URLs.

Why Recall.ai vs native APIs:
  - One API for 4 platforms vs building 4 separate bots
  - Built-in speaker diarization with persistent speaker IDs across calls
  - SOC2 Type II; data can be configured to never be retained server-side
  - ~$0.50-1.00/hr of meeting

Flow:
  1. Calendar event detected (Google Calendar / Outlook webhook) →
  2. create_bot(meeting_url, bot_name='SurveySparrow Coach') →
  3. Recall joins call as participant →
  4. After call ends, Recall posts webhook → we fetch transcript + recording →
  5. Pipe into analysis pipeline.

Production hardening:
  - Show a visible "AI Notetaker — SurveySparrow Coach" name & opt-out screen via
    Recall's pre-join consent message (required for two-party-consent states).
  - Persist meeting_url → HubSpot deal_id mapping so SE/AE attribution works.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import requests


RECALL_BASE = "https://us-east-1.recall.ai/api/v1"


@dataclass
class RecallBot:
    bot_id: str
    meeting_url: str
    status: str


class RecallClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("RECALL_API_KEY")

    def _headers(self):
        return {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

    def create_bot(self, meeting_url: str, bot_name: str = "SurveySparrow Coach") -> RecallBot:
        """Schedule a bot to join `meeting_url`. Idempotent on meeting_url."""
        payload = {
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "transcription_options": {"provider": "deepgram"},
            "recording_mode": "speaker_view",
            "automatic_leave": {"waiting_room_timeout": 300},
            "real_time_transcription": {
                "destination_url": os.getenv("RECALL_WEBHOOK_URL", ""),
            },
        }
        r = requests.post(f"{RECALL_BASE}/bot/", json=payload, headers=self._headers(), timeout=10)
        r.raise_for_status()
        d = r.json()
        return RecallBot(bot_id=d["id"], meeting_url=meeting_url, status=d["status_changes"][-1]["code"])

    def get_transcript(self, bot_id: str) -> str:
        """Fetch the diarized transcript after the call has ended."""
        r = requests.get(f"{RECALL_BASE}/bot/{bot_id}/transcript/", headers=self._headers(), timeout=30)
        r.raise_for_status()
        # Recall returns a list of {speaker, words, start, end}; we format as 'Speaker: text'
        segments = r.json()
        return "\n".join(f"{s['speaker']}: {' '.join(w['text'] for w in s['words'])}" for s in segments)

    def get_recording_url(self, bot_id: str) -> str:
        r = requests.get(f"{RECALL_BASE}/bot/{bot_id}/", headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()["video_url"]


def handle_webhook(payload: dict) -> Optional[str]:
    """
    Webhook handler called from API Gateway → Lambda.
    Returns bot_id if the event is 'bot.done', else None.
    """
    if payload.get("event") == "bot.done":
        return payload["data"]["bot_id"]
    return None
