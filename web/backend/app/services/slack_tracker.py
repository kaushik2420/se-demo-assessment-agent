"""
Slack tracker orchestrator.

Flow when @SE Coach is mentioned in a Slack thread:
  1. Verify webhook signature (already done at router layer)
  2. Fetch the full thread context
  3. Resolve users (SE = the mentioning user; engineer = other non-bot participants)
  4. If thread already has a tracker row: extract delta and append timestamped
     comment, refresh last_updated_at
  5. If new: run full extraction prompt; create row
  6. Best-effort: react with a ✅ in the thread (lets SEs know we caught it)

Daily cron (separate function): find open rows untouched >15 days, DM the SE,
set reminder_sent_at to prevent spamming the same row weekly.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Make src/ importable
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.db import SessionLocal
from app.models import TrackerRequest, User

from src.analysis.llm_client import LLMClient
from src.integrations.slack_client import SlackClient, build_message_url


# ----------------------------------------------------------------------------
# URL detection regexes (applied to thread text — not LLM)
# ----------------------------------------------------------------------------
# L2 ticket links — Zendesk (most common at SurveySparrow). Match common forms:
#   https://surveysparrow.zendesk.com/agent/tickets/12345
#   https://*.zendesk.com/.../tickets/12345
#   https://surveysparrow.zendesk.com/hc/.../articles/...
_L2_RE = re.compile(
    r"https?://[a-zA-Z0-9._-]*zendesk\.com/[^\s>|]+",
    re.IGNORECASE,
)
# Jira links — Atlassian-hosted or self-hosted
_JIRA_RE = re.compile(
    r"https?://[a-zA-Z0-9._-]+(?:\.atlassian\.net|/jira)/browse/[A-Z][A-Z0-9_]+-\d+",
    re.IGNORECASE,
)


def _extract_urls(text: str) -> tuple[Optional[str], Optional[str]]:
    """Find the first L2 (Zendesk) and first Jira URL in a chunk of text.
    Slack often wraps URLs as <https://…|label> — strip that wrapper first."""
    if not text:
        return None, None
    # Unwrap Slack's <url|label> and <url> forms
    cleaned = re.sub(r"<(https?://[^|>\s]+)(?:\|[^>]*)?>", r"\1", text)
    l2 = _L2_RE.search(cleaned)
    jira = _JIRA_RE.search(cleaned)
    return (l2.group(0) if l2 else None,
            jira.group(0) if jira else None)


def _classify_product_heuristic(text: str) -> Optional[str]:
    """Cheap pre-LLM signal: scan for product names. The LLM will refine."""
    if not text:
        return None
    t = text.lower()
    if "thrivesparrow" in t or "thrive sparrow" in t or "enps" in t or "employee engagement" in t:
        return "ThriveSparrow"
    if "sparrowdesk" in t or "sparrow desk" in t or "helpdesk" in t or "ticketing" in t:
        return "SparrowDesk"
    if "surveysparrow" in t or "survey sparrow" in t or " nps " in t or "csat" in t:
        return "SurveySparrow"
    return None


STALENESS_DAYS = 15
REMINDER_COOLDOWN_DAYS = 7   # don't re-remind the same row within this window

# Admin gets a DM on every @SE Coach tag with the outcome (✅ or ❌).
# Useful while we're debugging — set to empty string to disable.
ADMIN_NOTIFY_EMAIL = os.getenv("ADMIN_NOTIFY_EMAIL", "kaushik.natarajan@surveysparrow.com")


def _find_user_id_by_email(email: str) -> Optional[str]:
    """Look up a Slack user ID by their email address."""
    if not email or not os.getenv("SLACK_BOT_TOKEN"):
        return None
    try:
        import requests as _req
        r = _req.get(
            "https://slack.com/api/users.lookupByEmail",
            headers={"Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN')}"},
            params={"email": email}, timeout=10,
        )
        if not r.ok:
            return None
        data = r.json()
        return data.get("user", {}).get("id") if data.get("ok") else None
    except Exception:
        return None


def _dm_admin(message: str):
    """Best-effort DM to the admin notify email. Silent on failure."""
    if not ADMIN_NOTIFY_EMAIL:
        return
    try:
        slack = SlackClient()
        user_id = _find_user_id_by_email(ADMIN_NOTIFY_EMAIL)
        if not user_id:
            print(f"[tracker] admin DM skipped — no Slack user found for {ADMIN_NOTIFY_EMAIL}")
            return
        dm_channel = slack.open_dm(user_id)
        slack.post_message(dm_channel, message)
        print(f"[tracker] admin DM sent to {ADMIN_NOTIFY_EMAIL}")
    except Exception as e:
        print(f"[tracker] admin DM failed: {e}")


# -------------------------------------------------------------------------
# Public — webhook handler entry point
# -------------------------------------------------------------------------

def _resolve_se_from_first_poster(
    db, slack: SlackClient, thread_msgs: list, tagger: dict
) -> tuple[Optional[str], str, dict]:
    """Find the SE who actually OWNS this issue/request — the first person to
    post in the thread, NOT necessarily the one who tagged @SE Coach.

    Returns (se_email, se_name, resolved_user_info).
    Falls back to the tagger if the first poster isn't an SE in our DB.
    """
    # Sort by ts (Slack returns chronologically, but be safe)
    msgs_sorted = sorted(thread_msgs, key=lambda m: float(m.get("ts", "0") or "0"))
    first_human_msg = next(
        (m for m in msgs_sorted if m.get("user") and not m.get("bot_id")),
        None,
    )
    if not first_human_msg:
        return tagger.get("email"), tagger.get("name") or "Unknown", tagger

    first_uid = first_human_msg.get("user")
    if first_uid == tagger.get("id"):
        # Tagger IS the first poster — return them
        return tagger.get("email"), tagger.get("name") or "Unknown", tagger

    try:
        first_info = slack.get_user_info(first_uid)
    except Exception:
        return tagger.get("email"), tagger.get("name") or "Unknown", tagger

    first_email = (first_info.get("email") or "").lower()
    # Check if the first poster is a known SE in our portal
    if first_email:
        u = db.query(User).filter(User.email == first_email).first()
        if u:  # match — they are the owner regardless of role (could be se/manager)
            return first_email, u.name, first_info

    # First poster isn't a known SE — fall back to the tagger
    print(f"[tracker] first poster {first_info.get('name')} <{first_email}> "
          f"is not a known SE — falling back to tagger {tagger.get('name')}")
    return tagger.get("email"), tagger.get("name") or "Unknown", tagger


def handle_app_mention(event: dict, team_id: Optional[str] = None) -> dict:
    """
    Process a Slack `app_mention` event. Returns a stats dict for logging.
    Designed to be called from a FastAPI BackgroundTask so the webhook
    responds to Slack immediately (Slack expects <3s ack).
    """
    channel = event.get("channel")
    user_id = event.get("user")
    text = event.get("text", "")
    thread_ts = event.get("thread_ts") or event.get("ts")

    if not (channel and user_id and thread_ts):
        _dm_admin(f"❌ *Tracker failed* — missing required fields (channel/user/thread_ts) in Slack event.")
        return {"ok": False, "reason": "missing channel/user/thread_ts"}

    print(f"[tracker] processing app_mention: channel={channel} user={user_id} thread_ts={thread_ts}")

    try:
        slack = SlackClient()
        thread_msgs = slack.fetch_thread(channel, thread_ts)
        print(f"[tracker] fetched {len(thread_msgs)} messages from thread")
        tagger = slack.get_user_info(user_id)
        print(f"[tracker] tagger: {tagger.get('name')} <{tagger.get('email')}>")
        channel_info = slack.get_channel_info(channel)
        print(f"[tracker] channel: #{channel_info.get('name')}")
    except Exception as e:
        print(f"[tracker] slack API error: {e}")
        _dm_admin(f"❌ *Tracker failed* — Slack API error: `{e}`\n"
                  f"Channel: <#{channel}> · Thread ts: `{thread_ts}`\n"
                  f"_Common cause: bot not invited to the channel. Try `/invite @SE Coach` there._")
        return {"ok": False, "reason": f"slack api: {e}"}

    # Resolve all participants for the "engineer" guess
    participant_emails: dict[str, dict] = {}  # user_id → user info
    for m in thread_msgs:
        uid = m.get("user")
        if uid and uid != user_id and uid not in participant_emails:
            try:
                participant_emails[uid] = slack.get_user_info(uid)
            except Exception:
                pass

    # Format the conversation for Claude
    thread_text = _format_thread_for_prompt(thread_msgs, participant_emails, tagger)
    # Cheap pre-LLM URL detection — also catches links the LLM might miss
    raw_thread_text = " ".join((m.get("text") or "") for m in thread_msgs)
    detected_l2, detected_jira = _extract_urls(raw_thread_text)

    db = SessionLocal()
    try:
        # SE = first human poster, NOT the tagger
        se_email, se_name, _resolved = _resolve_se_from_first_poster(
            db, slack, thread_msgs, tagger
        )

        existing = db.query(TrackerRequest).filter(
            TrackerRequest.thread_ts == thread_ts
        ).first()

        llm = LLMClient(live=bool(os.getenv("ANTHROPIC_API_KEY")))

        if existing:
            print(f"[tracker] thread already tracked as row #{existing.id}; appending update")
            try:
                extracted = _extract_update(llm, thread_text, existing)
                print(f"[tracker] extracted update: {extracted}")
                _append_comment(existing, extracted.get("new_context", ""))
                if extracted.get("eta") and not existing.eta:
                    existing.eta = _parse_date(extracted["eta"])
                # Backfill any newly-detected URLs (don't overwrite manual edits)
                if detected_l2 and not existing.l2_url:
                    existing.l2_url = detected_l2
                if detected_jira and not existing.jira_url:
                    existing.jira_url = detected_jira
                existing.last_updated_at = datetime.now(timezone.utc)
                existing.last_synced_at = datetime.now(timezone.utc)
                db.commit()
            except Exception as e:
                _dm_admin(f"❌ *Tracker update failed* for row #{existing.id} ({existing.details or '(no details)'}): `{e}`")
                raise
            _dm_admin(
                f"✅ *Tracker updated* (row #{existing.id})\n"
                f"• Channel: <#{channel}>  ({channel_info.get('name', '?')})\n"
                f"• SE (owner): {existing.se_name}\n"
                f"• Tagged by: {tagger.get('name')}\n"
                f"• Request: {existing.details or '(no details)'}\n"
                f"• New context appended: _{extracted.get('new_context', '(none)')[:200]}_"
            )
            return {"ok": True, "action": "updated", "id": existing.id}
        else:
            print(f"[tracker] new thread; running full extraction "
                  f"(SE attributed to first poster: {se_name} <{se_email}>)")
            try:
                extracted = _extract_full(llm, thread_text, se_name, participant_emails)
                print(f"[tracker] extracted: {extracted}")
            except Exception as e:
                _dm_admin(f"❌ *Tracker extraction failed* for new thread in <#{channel}>: `{e}`")
                raise

            # Prefer LLM-detected URLs but fall back to regex-detected ones.
            l2_url = (extracted.get("l2_url") or detected_l2) or None
            jira_url = (extracted.get("jira_url") or detected_jira) or None

            row = TrackerRequest(
                thread_ts=thread_ts,
                channel_id=channel,
                channel_name=channel_info.get("name"),
                slack_url=build_message_url(team_id, channel, thread_ts),
                requested_date=_parse_date(extracted.get("requested_date")) or datetime.now(timezone.utc),
                eta=_parse_date(extracted.get("eta")),
                se_email=se_email or None,
                se_name=se_name,
                engineer_name=extracted.get("engineer_name"),
                details=extracted.get("details"),
                comments=extracted.get("comments") and _stamp(extracted["comments"]),
                product=extracted.get("product") or _classify_product_heuristic(raw_thread_text),
                kind=extracted.get("kind"),
                l2_url=l2_url,
                jira_url=jira_url,
                status="open",
                last_updated_at=datetime.now(timezone.utc),
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(row); db.commit()
            print(f"[tracker] CREATED row #{row.id} for thread {thread_ts}")
            _dm_admin(
                f"✅ *Tracker created* (row #{row.id})\n"
                f"• Channel: <#{channel}>  ({channel_info.get('name', '?')})\n"
                f"• SE (owner): {se_name}{' (auto-attributed)' if se_email != (tagger.get('email') or '') else ''}\n"
                f"• Tagged by: {tagger.get('name')}\n"
                f"• Kind: {row.kind or '(unknown)'} · Product: {row.product or '(unknown)'}\n"
                f"• Engineer: {extracted.get('engineer_name') or '(unknown)'}\n"
                f"• Request: {extracted.get('details') or '(no details)'}\n"
                f"• ETA: {extracted.get('eta') or '(none)'}\n"
                f"• L2: {l2_url or '—'}  ·  Jira: {jira_url or '—'}\n"
                f"• View: <{os.getenv('PORTAL_URL', 'https://se-demo-assessment-agent.vercel.app')}/tracker|Open tracker>"
            )
            return {"ok": True, "action": "created", "id": row.id}
    finally:
        db.close()


# -------------------------------------------------------------------------
# Daily thread refresh cron — re-pull every open thread, append new comments,
# backfill any newly-mentioned L2/Jira URLs, mark closed if the thread says so.
# -------------------------------------------------------------------------

def refresh_open_threads() -> dict:
    """For every open tracker row, re-fetch the Slack thread and:
       - Append any new comments (messages posted since last_synced_at)
       - Backfill L2/Jira URLs if they showed up after the row was created
       - Set status='closed' when the thread contains a closing phrase

       Designed to run once a day. Safe to re-run — uses last_synced_at as
       the high-water mark."""
    if not os.getenv("SLACK_BOT_TOKEN"):
        return {"ok": False, "reason": "SLACK_BOT_TOKEN not set"}

    stats: dict = {"checked": 0, "comments_appended": 0,
                   "urls_added": 0, "closed": 0, "errors": []}
    db = SessionLocal()
    try:
        slack = SlackClient()
        rows = (db.query(TrackerRequest)
                .filter(TrackerRequest.status == "open")
                .all())
        stats["checked"] = len(rows)

        for row in rows:
            try:
                msgs = slack.fetch_thread(row.channel_id, row.thread_ts)

                # 1) URL backfill (cheap)
                full_text = " ".join((m.get("text") or "") for m in msgs)
                l2, jira = _extract_urls(full_text)
                if l2 and not row.l2_url:
                    row.l2_url = l2; stats["urls_added"] += 1
                if jira and not row.jira_url:
                    row.jira_url = jira; stats["urls_added"] += 1

                # 2) Append new messages as comments
                hi_water = (row.last_synced_at or row.last_updated_at
                            or datetime.now(timezone.utc))
                hi_water_ts = hi_water.timestamp() if hi_water else 0
                new_msgs = [m for m in msgs
                            if float(m.get("ts", "0") or "0") > hi_water_ts
                            and m.get("user") and not m.get("bot_id")]
                # Skip the parent message — we already extracted its details on create
                if new_msgs:
                    appended_any = False
                    for m in new_msgs:
                        text = (m.get("text") or "").strip()
                        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()  # strip @ mentions
                        if not text or len(text) < 5:
                            continue
                        # Who said it?
                        try:
                            u = slack.get_user_info(m.get("user"))
                            who = u.get("name") or "Unknown"
                        except Exception:
                            who = "Unknown"
                        _append_comment(row, f"{who}: {text}")
                        appended_any = True
                    if appended_any:
                        row.last_updated_at = datetime.now(timezone.utc)
                        stats["comments_appended"] += 1

                # 3) Detect closure phrases in latest messages
                closure_signal = any(
                    re.search(r"\b(closed|resolved|shipped|deployed|done|fixed)\b",
                              (m.get("text") or ""), re.IGNORECASE)
                    for m in new_msgs
                )
                if closure_signal and row.status == "open":
                    row.status = "closed"
                    row.last_updated_at = datetime.now(timezone.utc)
                    stats["closed"] += 1
                    print(f"[tracker.refresh] row #{row.id} auto-closed (closure phrase in thread)")

                row.last_synced_at = datetime.now(timezone.utc)
                db.commit()
            except Exception as e:
                db.rollback()
                stats["errors"].append(f"row {row.id}: {e}")
                print(f"[tracker.refresh] row #{row.id} failed: {e}")
    finally:
        db.close()

    print(f"[tracker.refresh] done — {stats}")
    return stats


# -------------------------------------------------------------------------
# Staleness reminder cron
# -------------------------------------------------------------------------

def check_staleness_and_remind() -> dict:
    """Find open tracker rows untouched >15 days and DM their SE in Slack."""
    if not os.getenv("SLACK_BOT_TOKEN"):
        return {"ok": False, "reason": "SLACK_BOT_TOKEN not set"}

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=STALENESS_DAYS)
    cooldown = now - timedelta(days=REMINDER_COOLDOWN_DAYS)

    stats = {"checked": 0, "reminded": 0, "errors": []}
    db = SessionLocal()
    try:
        rows = (db.query(TrackerRequest)
                .filter(TrackerRequest.status == "open")
                .filter(TrackerRequest.last_updated_at < threshold)
                .all())
        stats["checked"] = len(rows)

        slack = SlackClient()
        for row in rows:
            if row.reminder_sent_at and row.reminder_sent_at > cooldown:
                continue
            if not row.se_email:
                continue
            # Find the slack user id by email
            user = db.query(User).filter(User.email == row.se_email).first()
            if not user:
                continue
            # Look up the slack user id via email — Slack doesn't have a direct
            # 'lookupByEmail' here without users:read.email; if we have one, use it.
            try:
                import requests as _req
                r = _req.get(f"https://slack.com/api/users.lookupByEmail",
                             headers={"Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN')}"},
                             params={"email": row.se_email}, timeout=10)
                user_id = r.json().get("user", {}).get("id") if r.ok else None
                if not user_id:
                    continue
                dm_channel = slack.open_dm(user_id)
                days_stale = (now - row.last_updated_at).days
                text = (
                    f":wave: This SE-Coach tracker item hasn't had an update in *{days_stale} days*.\n"
                    f"> *Request:* {row.details or '(no details)'}\n"
                    f"> *Engineer:* {row.engineer_name or 'unknown'}\n"
                    f"> *ETA:* {row.eta.strftime('%Y-%m-%d') if row.eta else 'not set'}\n"
                    f"> *Thread:* {row.slack_url or 'n/a'}\n\n"
                    f"Want me to update it? Tag *@SE Coach* again in the thread with the latest status."
                )
                slack.post_message(dm_channel, text)
                row.reminder_sent_at = now
                db.commit()
                stats["reminded"] += 1
            except Exception as e:
                stats["errors"].append(f"row {row.id}: {e}")
    finally:
        db.close()
    return stats


# -------------------------------------------------------------------------
# Internal helpers
# -------------------------------------------------------------------------

def _format_thread_for_prompt(messages: list, participants: dict, tagger: dict) -> str:
    lines = []
    for m in messages:
        uid = m.get("user", "?")
        if uid == tagger.get("id"):
            who = f"{tagger.get('name', 'SE')} (SE)"
        elif uid in participants:
            p = participants[uid]
            who = f"{p.get('name', 'Unknown')} ({p.get('email', '')})"
        else:
            who = uid
        ts = m.get("ts")
        try:
            when = datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            when = ts
        text = (m.get("text") or "").strip()
        # Strip the @SE Coach mention from the text so it doesn't leak
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        lines.append(f"[{when}] {who}: {text}")
    return "\n".join(lines)


def _extract_full(llm: LLMClient, thread_text: str, se_name: str, participants: dict) -> dict:
    participant_list = "\n".join(
        f"  - {p.get('name')} <{p.get('email', 'no-email')}>"
        for p in participants.values()
    ) or "  (none beyond the SE)"

    system = (
        "You read Slack conversations between SEs and engineers/product folks at SurveySparrow. "
        "SurveySparrow products: SurveySparrow (CX/feedback/NPS/surveys), ThriveSparrow "
        "(EX/employee engagement/eNPS/360), SparrowDesk (helpdesk/support tickets). "
        "Extract a structured request. Reply with ONLY a JSON object. No prose."
    )
    user = f"""Conversation thread (chronological):

{thread_text}

SE who owns this request: {se_name}
Other thread participants:
{participant_list}

Return ONLY this JSON:
{{
  "requested_date": "YYYY-MM-DD" or null (when was this request actually made — usually the first message in the thread),
  "eta": "YYYY-MM-DD" or null (any committed completion date discussed; null if not),
  "engineer_name": "Full name of the engineer/PM responsible for fulfilling this request" or null,
  "details": "1-3 sentence summary of what the SE is asking for",
  "kind": "issue" | "request" | null  (use "issue" for bugs / broken behavior / something that USED to work, "request" for new features / enhancements / new asks. null if you genuinely can't tell.),
  "product": "SurveySparrow" | "ThriveSparrow" | "SparrowDesk" | "Unknown"  (which product is the conversation about — see definitions above),
  "l2_url": "https://...zendesk.com/..." or null  (any Zendesk / L2 support ticket link mentioned in the thread),
  "jira_url": "https://...atlassian.net/browse/PROJ-123" or null  (any Jira issue link mentioned),
  "comments": "Anything else useful — prospect mentioned, competitor context, urgency reasoning, etc. Empty string if nothing extra."
}}
"""

    mock = {
        "requested_date": datetime.now(timezone.utc).date().isoformat(),
        "eta": None,
        "engineer_name": next(iter([p.get("name") for p in participants.values()]), None),
        "details": "(mock) Demo prep ask — needs custom dashboard widget by Q3.",
        "kind": "request",
        "product": "SurveySparrow",
        "l2_url": None,
        "jira_url": None,
        "comments": "(mock fallback — Claude not live)",
    }
    return llm.chat_json(system, user, mock_response=mock)


def _extract_update(llm: LLMClient, thread_text: str, existing: TrackerRequest) -> dict:
    system = (
        "You read Slack conversations between SEs and engineers. The thread already "
        "has a tracker entry. Extract ONLY what's NEW since the prior snapshot. "
        "Reply with ONLY a JSON object."
    )
    user = f"""Current thread (chronological):

{thread_text}

Existing tracker entry for this thread (you should NOT repeat what's already here):
- Details: {existing.details or '(none)'}
- ETA: {existing.eta.isoformat() if existing.eta else '(none)'}
- Engineer: {existing.engineer_name or '(unknown)'}
- Existing comment log: {existing.comments or '(empty)'}

Return ONLY this JSON:
{{
  "new_context": "What's new since the last snapshot — 1-2 sentences. Empty if nothing meaningful.",
  "eta": "YYYY-MM-DD" or null (if a new ETA was committed in recent messages)
}}
"""
    mock = {"new_context": "(mock) Engineer confirmed by EOW.", "eta": None}
    return llm.chat_json(system, user, mock_response=mock)


def _stamp(text: str) -> str:
    """Prefix a comment with a timestamp like [23 Jun 2026 10:00 AM] : ..."""
    if not text:
        return ""
    now = datetime.now(timezone.utc)
    stamp = now.strftime("[%-d %b %Y %-I:%M %p UTC]")
    return f"{stamp} : {text.strip()}"


def _append_comment(row: TrackerRequest, new_text: str):
    if not new_text or not new_text.strip():
        return
    stamped = _stamp(new_text)
    row.comments = (row.comments + "\n\n" + stamped) if row.comments else stamped


def _parse_date(s) -> Optional[datetime]:
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    try:
        from datetime import date as _d
        d = _d.fromisoformat(str(s)[:10])
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    except Exception:
        try:
            from dateutil import parser as _du
            dt = _du.parse(str(s), fuzzy=True)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None


def get_status() -> dict:
    db = SessionLocal()
    try:
        total = db.query(TrackerRequest).count()
        open_count = db.query(TrackerRequest).filter(TrackerRequest.status == "open").count()
        return {
            "slack_configured": bool(os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_SIGNING_SECRET")),
            "total_requests": total,
            "open_requests": open_count,
        }
    finally:
        db.close()
