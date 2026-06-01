"""
Push analyzed calls to the Notion Demo Tracker.

Called after a call is successfully analyzed (Granola sync or manual upload).
Maps our internal data → Notion properties, handles dedupe by customer + date,
and respects manual SE edits (won't overwrite filled fields).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Ensure src/ is on path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.integrations.notion_client import NotionClient, build_property


# Map our internal call_type → the closest existing value in the Notion tracker.
CALL_TYPE_TO_NOTION = {
    "demo":             "New demo",
    "followup_demo":    "Follow up query call/Demo",
    "followup_query":   "Follow up query call/Demo",
    "poc":              "Onboarding/Assisstance Call",
    "closure":          "Follow up query call/Demo",
    "other":            "New demo",
}


def push_call(call_data: dict, insights: Optional[dict] = None) -> dict:
    """
    Push a single call to Notion. Returns a status dict for logging.

    call_data shape (from Call ORM + scorecard):
        {
          "prospect_company": "...", "call_date": datetime, "call_type": "demo",
          "se_name": "...", "ae_name": "...", "stated_use_case": "...",
        }
    insights: full 9-signal blob (optional but improves coverage)
    """
    if not os.getenv("NOTION_API_KEY") or not os.getenv("NOTION_DATABASE_ID"):
        return {"pushed": False, "reason": "Notion env vars not set"}

    try:
        client = NotionClient()
        schema = client.get_schema()
    except Exception as e:
        return {"pushed": False, "reason": f"Notion init failed: {e}"}

    # Build Notion properties using the live schema
    props = _build_properties(call_data, insights or {}, schema)
    if not props:
        return {"pushed": False, "reason": "No mappable properties"}

    customer = call_data.get("prospect_company") or ""
    call_date = call_data.get("call_date") or datetime.now(timezone.utc)

    try:
        existing = client.find_row(customer, call_date)
        if existing:
            result = client.update_page(existing, props, only_if_blank=True)
            return {"pushed": True, "action": "updated", "page_id": existing,
                    "fields_updated": result.get("fields", [])}
        else:
            page_id = client.create_page(props)
            return {"pushed": True, "action": "created", "page_id": page_id,
                    "fields_created": list(props.keys())}
    except Exception as e:
        return {"pushed": False, "reason": f"Notion API error: {e}"}


def _build_properties(call: dict, insights: dict, schema: dict) -> dict:
    """Map our data to Notion properties, respecting schema field types."""
    out = {}

    def set_field(name: str, value, prop_type: Optional[str] = None):
        if name not in schema:
            return  # field doesn't exist in this database
        ptype = prop_type or schema[name]["type"]
        options = schema[name].get("options", []) or []
        payload = build_property(ptype, value, options=options)
        if payload is not None:
            out[name] = payload

    # Customer Name (title)
    set_field("Customer Name", call.get("prospect_company"))

    # Date
    call_date = call.get("call_date")
    if call_date:
        set_field("Date", call_date)

    # Call Type / No Shows
    ct = call.get("call_type", "demo")
    set_field("Call Type/No Shows", CALL_TYPE_TO_NOTION.get(ct, "New demo"))

    # SE Name
    set_field("SE Name", _first_name(call.get("se_name")))

    # AE Name (only if we know it from manual upload — Granola can't reliably detect)
    if call.get("ae_name"):
        set_field("AE Name", _first_name(call["ae_name"]))

    # Present Survey Provider (from competitors_mentioned)
    competitors = insights.get("competitors_mentioned") or []
    if competitors:
        # First non-empty competitor name
        for c in competitors:
            name = (c or {}).get("name", "").strip()
            if name and name.lower() not in ("none", "n/a", "unknown"):
                set_field("Present Survey Provider", name)
                break

    # Timeline (from prospect_engagement buying signals — try to find a real
    # date. Only push if we can parse it; otherwise leave the field blank
    # rather than fail the whole row.)
    pe = insights.get("prospect_engagement") or {}
    timeline_date = _extract_timeline_date(pe.get("buying_signals", []))
    if timeline_date:
        set_field("Timeline", timeline_date)

    # Product (default to SurveySparrow unless use_case mentions ThriveSparrow / SparrowDesk)
    use_case = (insights.get("use_case") or {}).get("summary", "")
    product = _infer_product(use_case)
    if product:
        set_field("Product", product)

    return out


def _first_name(full_name: Optional[str]) -> Optional[str]:
    if not full_name:
        return None
    return full_name.strip().split()[0]


def _extract_timeline_date(signals: list):
    """
    Find a buying signal that contains a date mention AND can actually be
    parsed into a real calendar date. Returns a `date` object or None.

    We use dateutil's fuzzy parser, which handles:
      - "by March 31, 2026"
      - "end of June"  → assumes current year
      - "Q3 2026"      → handled separately (dateutil doesn't parse 'Q3')
      - "next quarter" → can't parse → returns None (which is correct)
    """
    if not signals:
        return None
    import re
    from datetime import date as _date, datetime as _dt

    # Quarter mentions: "Q1 2026" → first day of that quarter
    quarter_re = re.compile(r"\bQ([1-4])\s*(\d{4})\b", re.IGNORECASE)
    # Month mentions: at least a month name should be present for the signal to be a candidate
    month_re = re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
        re.IGNORECASE
    )

    try:
        from dateutil import parser as _du_parser
        default = _dt(_dt.now().year, 1, 1)
    except ImportError:
        _du_parser = None
        default = None

    for s in signals:
        if not isinstance(s, str) or not s.strip():
            continue

        # Try quarter syntax first
        qm = quarter_re.search(s)
        if qm:
            q = int(qm.group(1))
            yr = int(qm.group(2))
            return _date(yr, (q - 1) * 3 + 1, 1)

        # Skip signals that don't even mention a month — avoids false positives
        if not month_re.search(s):
            continue

        if _du_parser is None:
            continue

        # Try fuzzy parse — but only accept the result if it didn't fall back
        # to ALL of the default values (which would mean nothing was parsed)
        try:
            parsed = _du_parser.parse(s, fuzzy=True, default=default)
            # Sanity-check: must be within ±2 years of today (to filter out
            # parses like "Team agree" → some bizarre year)
            today = _dt.now()
            if abs((parsed.year - today.year)) <= 2:
                return parsed.date()
        except (ValueError, OverflowError, TypeError):
            continue
    return None


def _infer_product(use_case: str) -> Optional[str]:
    if not use_case:
        return None
    u = use_case.lower()
    if "thrive" in u or "360" in u or "engagement" in u or "performance review" in u:
        return "ThriveSparrow"
    if "sparrowdesk" in u or "helpdesk" in u or "support ticket" in u:
        return "SparrowDesk"
    return "SurveySparrow"


def get_status() -> dict:
    """Quick status snapshot for the Team page UI."""
    return {
        "configured": bool(os.getenv("NOTION_API_KEY") and os.getenv("NOTION_DATABASE_ID")),
        "database_id": os.getenv("NOTION_DATABASE_ID", "")[:8] + "..." if os.getenv("NOTION_DATABASE_ID") else None,
    }
