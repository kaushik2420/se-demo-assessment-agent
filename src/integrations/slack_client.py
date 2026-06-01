"""
Slack API client (Bot user) + Events API signature verification.

We use plain requests + stdlib hmac to avoid an extra dependency. The Slack
SDK would also work, but for our small surface (fetch thread, post message,
verify signature, get user email) the wrapper is overkill.

Env vars:
    SLACK_BOT_TOKEN       xoxb-...   (Bot User OAuth Token)
    SLACK_SIGNING_SECRET             (Basic Information → App Credentials)
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import List, Optional

import requests


SLACK_API = "https://slack.com/api"


class SlackClient:
    def __init__(self, bot_token: Optional[str] = None):
        self.token = bot_token or os.getenv("SLACK_BOT_TOKEN")
        if not self.token:
            raise RuntimeError("SLACK_BOT_TOKEN env var not set")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def fetch_thread(self, channel_id: str, thread_ts: str, limit: int = 50) -> List[dict]:
        """Get all messages in a thread (parent + replies)."""
        r = requests.get(
            f"{SLACK_API}/conversations.replies",
            headers={"Authorization": f"Bearer {self.token}"},
            params={"channel": channel_id, "ts": thread_ts, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack fetch_thread failed: {data.get('error')}")
        return data.get("messages", [])

    def get_user_info(self, user_id: str) -> dict:
        """Resolve a Slack user ID to {name, email, real_name}."""
        r = requests.get(
            f"{SLACK_API}/users.info",
            headers={"Authorization": f"Bearer {self.token}"},
            params={"user": user_id},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            return {"id": user_id}
        u = data.get("user", {}) or {}
        profile = u.get("profile", {}) or {}
        return {
            "id": u.get("id"),
            "name": u.get("real_name") or u.get("name") or "Unknown",
            "email": profile.get("email", "").lower(),
            "username": u.get("name"),
        }

    def post_message(self, channel: str, text: str, thread_ts: Optional[str] = None) -> dict:
        """Post a message. Pass thread_ts to reply in-thread."""
        payload = {"channel": channel, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        r = requests.post(f"{SLACK_API}/chat.postMessage",
                          headers=self._headers(), json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack post_message failed: {data.get('error')}")
        return data

    def open_dm(self, user_id: str) -> str:
        """Open a DM channel with a user; returns the channel id to post into."""
        r = requests.post(f"{SLACK_API}/conversations.open",
                          headers=self._headers(),
                          json={"users": user_id}, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack open_dm failed: {data.get('error')}")
        return data["channel"]["id"]

    def get_channel_info(self, channel_id: str) -> dict:
        r = requests.get(
            f"{SLACK_API}/conversations.info",
            headers={"Authorization": f"Bearer {self.token}"},
            params={"channel": channel_id},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            return {}
        return data.get("channel", {}) or {}


# -------------------------------------------------------------------------
# Signature verification (Slack Events API)
# https://api.slack.com/authentication/verifying-requests-from-slack
# -------------------------------------------------------------------------

def verify_signature(body_bytes: bytes, timestamp: str, signature: str,
                     signing_secret: Optional[str] = None,
                     tolerance_seconds: int = 60 * 5) -> bool:
    """
    Verify a Slack Events API request. Returns True if the request is
    authentic and within the freshness window (default 5 minutes).
    """
    secret = signing_secret or os.getenv("SLACK_SIGNING_SECRET")
    if not secret:
        return False  # fail-closed if not configured
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(time.time() - ts) > tolerance_seconds:
        return False  # replay-attack guard
    basestring = f"v0:{timestamp}:".encode("utf-8") + body_bytes
    expected = "v0=" + hmac.new(
        secret.encode("utf-8"), basestring, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def build_message_url(team_id: Optional[str], channel_id: str, thread_ts: str) -> str:
    """Build a deep link to the original thread in Slack."""
    # ts comes as "1234567890.123456"; remove the dot for the URL
    ts_for_url = thread_ts.replace(".", "")
    if team_id:
        return f"https://app.slack.com/client/{team_id}/{channel_id}/thread/{channel_id}-{thread_ts}"
    return f"https://slack.com/archives/{channel_id}/p{ts_for_url}"
