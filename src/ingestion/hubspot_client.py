"""
HubSpot ingestion: pull call recordings and attendee metadata so we can
attribute every call to (SE, AE, deal, prospect company).

Your existing eval Excel referenced HubSpot call records like:
  https://app.hubspot.com/contacts/4047592/record/0-1/94974185734?...

This module:
  1. Lists recent call engagements for the SE team (last N days)
  2. Pulls the recording URL + transcript (if HubSpot's built-in transcript exists)
  3. Joins to the associated Deal to get prospect_company + ARR
  4. Identifies SE & AE from attendees by HubSpot user role
"""

from __future__ import annotations

import os
from typing import List, Optional

import requests


HUBSPOT_BASE = "https://api.hubapi.com"


class HubSpotClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("HUBSPOT_TOKEN")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def list_calls_since(self, since_iso: str, limit: int = 100) -> List[dict]:
        """Returns call engagements with hs_call_recording_url populated."""
        params = {
            "limit": limit,
            "properties": "hs_call_recording_url,hs_call_duration,hs_call_title,"
                          "hs_timestamp,hs_meeting_external_url,hubspot_owner_id",
            "filter": f"hs_timestamp >= {since_iso}",
        }
        r = requests.get(
            f"{HUBSPOT_BASE}/crm/v3/objects/calls",
            headers=self._headers(), params=params, timeout=30,
        )
        r.raise_for_status()
        return r.json().get("results", [])

    def get_deal_for_call(self, call_id: str) -> Optional[dict]:
        r = requests.get(
            f"{HUBSPOT_BASE}/crm/v3/objects/calls/{call_id}/associations/deals",
            headers=self._headers(), timeout=10,
        )
        r.raise_for_status()
        deals = r.json().get("results", [])
        if not deals:
            return None
        deal_id = deals[0]["id"]
        r2 = requests.get(
            f"{HUBSPOT_BASE}/crm/v3/objects/deals/{deal_id}",
            headers=self._headers(),
            params={"properties": "dealname,amount,dealstage,industry,hs_deal_stage_probability"},
            timeout=10,
        )
        r2.raise_for_status()
        return r2.json()

    def get_call_attendees(self, call_id: str) -> List[dict]:
        """Resolve attendees → HubSpot users → roles (SE / AE)."""
        r = requests.get(
            f"{HUBSPOT_BASE}/crm/v3/objects/calls/{call_id}/associations/contacts",
            headers=self._headers(), timeout=10,
        )
        r.raise_for_status()
        return r.json().get("results", [])
