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
    event_type = event_wrapper.get("type")
    team_id = body_json.get("team_id")
    print(f"[slack] event received: type={event_type!r} "
          f"channel={event_wrapper.get('channel')!r} "
          f"user={event_wrapper.get('user')!r} "
          f"thread_ts={event_wrapper.get('thread_ts')!r} "
          f"ts={event_wrapper.get('ts')!r}")

    if event_type == "app_mention":
        from app.services.slack_tracker import handle_app_mention

        def _wrapped_handler():
            try:
                result = handle_app_mention(event_wrapper, team_id)
                print(f"[slack] handle_app_mention returned: {result}")
            except Exception as e:
                import traceback
                print(f"[slack] handle_app_mention CRASHED: {e}")
                traceback.print_exc()
                # Best-effort DM to admin so they don't have to check Render logs
                try:
                    from app.services.slack_tracker import _dm_admin
                    _dm_admin(f"❌ *Tracker handler CRASHED* — `{type(e).__name__}: {e}`\n"
                              f"Check Render logs for full traceback.")
                except Exception:
                    pass

        bg.add_task(_wrapped_handler)
        return {"ok": True}

    # Unknown event type — ignore but ack
    print(f"[slack] ignoring event type {event_type!r}")
    return {"ok": True, "ignored": event_type}
