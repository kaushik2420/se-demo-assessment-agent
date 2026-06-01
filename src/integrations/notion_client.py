"""
Notion API client for the SurveySparrow Demo Tracker.

Reads the target database's schema at runtime so we adapt to whatever field
types you've configured — no hardcoded property types means the field config
in Notion is the source of truth.

Env vars required:
    NOTION_API_KEY        — integration internal token (starts with ntn_ on
                            newer integrations, or secret_ on older ones —
                            both work identically)
    NOTION_DATABASE_ID    — the 32-char hex ID from the database URL

Setup steps for the admin (one-time):
    1. https://www.notion.so/profile/integrations → New integration
    2. Name it 'SE Coach' → Submit → copy the Internal Integration Token
    3. Open the Demo tracker_2026 database → top-right ... menu → Connections
       → Add 'SE Coach'
    4. Copy the database ID from the URL: notion.so/<workspace>/<DATABASE_ID>?v=...
       (the 32-char hex segment before ?v=)
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import requests


NOTION_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    def __init__(self, api_key: Optional[str] = None, database_id: Optional[str] = None):
        self.api_key = api_key or os.getenv("NOTION_API_KEY")
        self.database_id = database_id or os.getenv("NOTION_DATABASE_ID")
        if not self.api_key:
            raise RuntimeError("NOTION_API_KEY env var not set")
        if not self.database_id:
            raise RuntimeError("NOTION_DATABASE_ID env var not set")
        self._schema_cache: Optional[Dict[str, dict]] = None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    # ---------------------------------------------------------------------
    # Schema discovery — learn the database's property names + types once
    # ---------------------------------------------------------------------
    def get_schema(self, refresh: bool = False) -> Dict[str, dict]:
        """Return {property_name: {type, options?}}. Cached after first call."""
        if self._schema_cache and not refresh:
            return self._schema_cache
        r = requests.get(f"{NOTION_BASE}/databases/{self.database_id}",
                         headers=self._headers(), timeout=15)
        r.raise_for_status()
        props = r.json().get("properties", {})
        out = {}
        for name, p in props.items():
            entry = {"type": p.get("type"), "id": p.get("id")}
            ptype = entry["type"]
            if ptype in ("select", "status", "multi_select"):
                opts = p.get(ptype, {}).get("options", [])
                entry["options"] = [o["name"] for o in opts]
            out[name] = entry
        self._schema_cache = out
        return out

    # ---------------------------------------------------------------------
    # Find existing row by Customer Name + Date (avoid duplicates)
    # ---------------------------------------------------------------------
    def find_row(self, customer_name: str, call_date: date) -> Optional[str]:
        """Return the Notion page_id if a row with this (name, date) exists."""
        if not customer_name:
            return None
        date_str = call_date.isoformat() if isinstance(call_date, (date, datetime)) else str(call_date)
        # Notion's title property name is usually "Customer Name" here.
        # We're cautious: query just by Date (Notion's title equality is fuzzy)
        # then filter by name in Python.
        payload = {
            "filter": {
                "property": "Date",
                "date": {"equals": date_str[:10]},
            },
            "page_size": 100,
        }
        r = requests.post(f"{NOTION_BASE}/databases/{self.database_id}/query",
                          headers=self._headers(), json=payload, timeout=15)
        r.raise_for_status()
        for page in r.json().get("results", []):
            page_name = _extract_title(page.get("properties", {}))
            if page_name and page_name.lower().strip() == customer_name.lower().strip():
                return page["id"]
        return None

    # ---------------------------------------------------------------------
    # Create / update
    # ---------------------------------------------------------------------
    def create_page(self, properties: Dict[str, Any]) -> str:
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
        }
        r = requests.post(f"{NOTION_BASE}/pages", headers=self._headers(),
                          json=payload, timeout=15)
        if r.status_code >= 400:
            raise RuntimeError(f"Notion create_page failed: {r.status_code} {r.text}")
        return r.json()["id"]

    def update_page(self, page_id: str, properties: Dict[str, Any],
                    only_if_blank: bool = True) -> dict:
        """
        Update a page. If only_if_blank is True, fetch current values first
        and only push fields that are currently empty — preserves any manual
        SE edits.
        """
        if only_if_blank:
            properties = self._filter_blank_only(page_id, properties)
            if not properties:
                return {"updated": 0, "fields": []}
        r = requests.patch(f"{NOTION_BASE}/pages/{page_id}",
                           headers=self._headers(),
                           json={"properties": properties}, timeout=15)
        if r.status_code >= 400:
            raise RuntimeError(f"Notion update_page failed: {r.status_code} {r.text}")
        return {"updated": len(properties), "fields": list(properties.keys())}

    def _filter_blank_only(self, page_id: str, new_props: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.get(f"{NOTION_BASE}/pages/{page_id}",
                         headers=self._headers(), timeout=15)
        r.raise_for_status()
        current = r.json().get("properties", {})
        out = {}
        for name, val in new_props.items():
            cur = current.get(name, {})
            if _is_blank(cur):
                out[name] = val
        return out


# ---------------------------------------------------------------------
# Helpers — convert Python values to Notion property payloads based on type
# ---------------------------------------------------------------------

def build_property(prop_type: str, value: Any, *, options: List[str] = None) -> Optional[dict]:
    """
    Wrap `value` in the right Notion API payload shape for `prop_type`.
    Returns None if the value is empty or unmappable.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    options = options or []

    if prop_type == "title":
        return {"title": [{"type": "text", "text": {"content": str(value)[:2000]}}]}
    if prop_type == "rich_text":
        return {"rich_text": [{"type": "text", "text": {"content": str(value)[:2000]}}]}
    if prop_type == "url":
        return {"url": str(value)}
    if prop_type == "email":
        return {"email": str(value)}
    if prop_type == "number":
        try:
            return {"number": float(value)}
        except (TypeError, ValueError):
            return None
    if prop_type == "date":
        if isinstance(value, (date, datetime)):
            return {"date": {"start": value.isoformat()[:10]}}
        return {"date": {"start": str(value)[:10]}}
    if prop_type == "checkbox":
        return {"checkbox": bool(value)}
    if prop_type in ("select", "status"):
        # Fuzzy match to existing options (case-insensitive substring)
        v = str(value).strip()
        matched = _fuzzy_match(v, options)
        if matched is None and not options:
            return {prop_type: {"name": v[:100]}}  # try anyway (Notion may allow)
        if matched is None:
            return None  # no good match; skip rather than create a new option
        return {prop_type: {"name": matched}}
    if prop_type == "multi_select":
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
        matched = [_fuzzy_match(v, options) or v for v in value]
        return {"multi_select": [{"name": m[:100]} for m in matched if m]}
    if prop_type == "people":
        # Skip — we'd need Notion user IDs which we don't have
        return None
    return None


def _fuzzy_match(value: str, options: List[str]) -> Optional[str]:
    if not options:
        return None
    v = value.lower().strip()
    # Exact case-insensitive
    for o in options:
        if o.lower().strip() == v:
            return o
    # Substring either direction
    for o in options:
        ol = o.lower().strip()
        if v in ol or ol in v:
            return o
    return None


def _extract_title(properties: dict) -> Optional[str]:
    for name, p in properties.items():
        if p.get("type") == "title":
            t = p.get("title", [])
            if t and t[0].get("plain_text"):
                return t[0]["plain_text"]
            return None
    return None


def _is_blank(prop: dict) -> bool:
    """True if a Notion property value is effectively empty."""
    if not prop:
        return True
    t = prop.get("type")
    v = prop.get(t)
    if v is None or v == "" or v == [] or v == {}:
        return True
    if t == "title" or t == "rich_text":
        return not (v and v[0].get("plain_text"))
    if t == "date":
        return not (isinstance(v, dict) and v.get("start"))
    if t in ("select", "status"):
        return not (isinstance(v, dict) and v.get("name"))
    if t == "multi_select":
        return len(v) == 0
    if t == "checkbox":
        return False  # checkbox always has a value (true/false)
    if t == "number":
        return v is None
    if t == "url" or t == "email":
        return not v
    return False
