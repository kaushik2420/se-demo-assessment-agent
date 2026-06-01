"""
Slack Events API webhook receiver.

Slack sends events here as JSON. We:
  1. Verify the request signature (HMAC-SHA256)
  2. Respond instantly to URL verification challenges (during initial setup)
  3. For app_mention events: ack within 3s, process in background
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.integrations.slack_client import verify_signature


router = APIRouter()


@router.post("/events")
async def slack_events(
    request: Request,
    bg: BackgroundTasks,
    x_slack_signature: str = Header(default=""),
    x_slack_request_timestamp: str = Header(default=""),
):
    body_bytes = await request.body()

    # URL verification handshake (Slack sends this once when you configure the URL)
    try:
        import json
        body_json = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        body_json = {}

    if body_json.get("type") == "url_verification":
        # Slack docs: respond with the challenge value to confirm the endpoint
        return {"challenge": body_json.get("challenge", "")}

    # All other events require signature verification
    if not verify_signature(body_bytes, x_slack_request_timestamp, x_slack_signature):
        raise HTTPException(401, "Invalid Slack signature")

    # Slack retries if we don't ack within 3s. Process the event in background.
    event_wrapper = body_json.get("event") or {}
    team_id = body_json.get("team_id")
    if event_wrapper.get("type") == "app_mention":
        from app.services.slack_tracker import handle_app_mention
        bg.add_task(handle_app_mention, event_wrapper, team_id)
        return {"ok": True}

    # Unknown event type — ignore but ack
    return {"ok": True, "ignored": event_wrapper.get("type")}
