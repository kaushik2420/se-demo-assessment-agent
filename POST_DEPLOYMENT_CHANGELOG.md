# SE Coach — Post-Deployment Change Log

A running record of every bug, feedback item, and feature request raised by the team **after the day-1 deployment**, with root cause analysis and the fix that landed.

| Field | Meaning |
|---|---|
| **Issue / Feedback** | What was reported and by whom (when known) |
| **RCA** | Root cause — *why* the system behaved this way |
| **Fix** | What we actually changed (with file references) |
| **Date** | When the fix was committed |

Day-1 deployment: **2026-05-27** (initial build) — first team-facing usage began **2026-05-31** when the Granola Business integration was switched on.

Last updated: **2026-06-05** (latest entry #33)

---

## #1 — Granola sync: date format rejected by API

**Issue / Feedback:** First Granola sync failed with HTTP 400 from `public-api.granola.ai/v1/notes`. No notes were pulled into the portal even though the API key was valid.

**RCA:** Python's `datetime.isoformat()` produces `2026-05-31T10:00:00.123456+00:00`. Granola's API rejected both the microseconds and the `+00:00` timezone suffix — it requires `2026-05-31T10:00:00Z`.

**Fix:** Normalize the `created_after` / `updated_after` parameter in `src/ingestion/granola_client.py::list_notes_since()` — strip microseconds, force UTC, suffix with `Z`. Accepts both `datetime` objects and pre-formatted strings.

**Date:** 2026-05-31

---

## #2 — Granola sync stuck "in progress"

**Issue / Feedback:** Manual "Sync now" button stopped working — the UI permanently showed "Sync running…" with no progress, even days later.

**RCA:** The sync sets an `/tmp/granola_sync_in_progress` lock file at start and removes it on completion. If the process crashed mid-run (Render dyno restart, OOM), the lock file stayed forever and blocked all future syncs.

**Fix:** Added a 15-minute TTL on the lock file. `_is_progress_stale()` checks the file's mtime; if older than 15 minutes the lock is considered abandoned and auto-cleared on the next status check. Added `_set_in_progress()` / `_is_in_progress()` helpers in `web/backend/app/services/granola_sync.py`.

**Date:** 2026-05-31

---

## #3 — Granola sync: long-running requests blocked the UI thread

**Issue / Feedback:** Clicking "Sync now" hung the API call for minutes (Granola pagination + per-note Claude scoring), causing browser timeouts and double-clicks that spawned duplicate runs.

**RCA:** The sync was wired as a synchronous HTTP handler. Each note requires two Claude calls (scoring + insights), so a sync of 10 notes was ~10 minutes — far past Render's HTTP timeout.

**Fix:** Sync now runs as a `FastAPI BackgroundTask`. The endpoint returns immediately with `{status: "started"}`. The Team-page UI polls `/team/granola/status` every 5s and surfaces `in_progress`, `last_sync_at`, and counters from `last_result`.

**Date:** 2026-05-31

---

## #4 — Granola sync: missed retroactively-shared notes

**Issue / Feedback:** Kaushik shared an existing note to the "Calls for analysis" folder *after* the sync had already run. The note never got picked up even on subsequent runs.

**RCA:** The sync passed `created_after=last_sync_at`. A note created two weeks ago but shared yesterday has `created_at` outside the window, so the API didn't return it. Compounded by a 7-day incremental lookback that was too narrow.

**Fix:** Three iterations:
1. Switched filter from `created_after` to `updated_after` (catches retroactive share events, which bump `updated_at`).
2. Replaced incremental `last_sync_at` with a **constant 30-day lookback** so back-shared notes within a month always surface.
3. Dedupe via `external_id` (Granola note ID) prevents reprocessing.

**Date:** 2026-06-01

---

## #5 — Granola sync: 5 notes wrongly flagged "wrong folder"

**Issue / Feedback:** Sync result showed `notes_seen: 8, imported: 0, wrong_folder: 5`. Kaushik confirmed all notes were in the "Calls for analysis" folder in the Granola UI.

**RCA:** Investigation in two passes:
1. **First hypothesis (wrong):** case-sensitivity of `GRANOLA_FOLDER_NAME` env var vs API response. Shipped a permissive fix.
2. **Diagnostic logging revealed the truth:** the 5 notes had `folder_membership: []`. These were *Kaushik's personal notes*, not in any workspace folder. The permissive fix was actually wrong because it would have allowed personal notes through.
3. **Corrected:** reverted to strict folder match. Empty `folder_membership` correctly means "not in the shared folder, reject."

**Fix:** Final state in `web/backend/app/services/granola_sync.py`:
- Case-insensitive + whitespace-tolerant name match (still rejects non-matching folders)
- Empty `folder_membership` → reject (these are personal notes)
- Verbose logging: per-rejected note prints `note_id`, `owner`, `wanted`, `seen`, `raw_keys`, `folder_ish` so any future folder-related issue is one log line away from diagnosis

**Date:** 2026-06-02

---

## #6 — Granola API token is user-scoped (BLOCKING — pending Granola support)

**Issue / Feedback:** After fixing #5, sync still returned only 8 notes — all owned by Kaushik. None of the team's notes (shared to the same workspace folder) appeared.

**RCA:** Added diagnostic logging that prints `owners_seen` per sync. Confirmed: `owners=['kaushik.natarajan@surveysparrow.com']` even though team members were saving to the same shared folder. Conclusion: Granola's per-user API token only returns notes owned by the token holder. Sharing a folder doesn't make other users' notes visible through your token.

**Fix:** Email drafted to Granola support requesting a workspace-scoped API key. Multi-token fallback prepared as Plan B (each SE generates their own key; we loop through all). Not yet deployed pending Granola's response.

**Date:** 2026-06-02 (in progress)

---

## #7 — Notion auto-fill: Timeline field rejected by Notion API

**Issue / Feedback:** BTS call was being analyzed and inserted into Notion, but Notion returned 400 on the Timeline field. Backfill aborted on the offending row.

**RCA:** The extractor produced strings like `"Hard July"` for the Timeline column. Notion's `date` property requires strict ISO 8601 — anything not parseable as a date is rejected, which 400'd the entire row.

**Fix:** Defensive date parsing in `src/integrations/notion_client.py::build_property()`:
- Try `datetime.fromisoformat()` first
- Fall back to `dateutil.parser.parse()` with fuzzy=True
- Sanity-check the resulting date (must be within ±2 years of today) — anything outside is treated as unparseable
- If unparseable, **skip the field** rather than failing the whole row

Other rows still backfill successfully; the bad Timeline value is simply left blank.

**Date:** 2026-06-01

---

## #8 — Slack tracker: @SE Coach mentions weren't creating rows

**Issue / Feedback:** Kaushik tagged @SE Coach in test threads. Could see the POST event hit Render but no tracker rows appeared in the UI.

**RCA:** Multiple silent failures in `handle_app_mention`:
- `slack.fetch_thread` was 401-ing because `channels:history` / `groups:history` scopes weren't added when the app was first installed
- The exception was caught and logged, but the response to Slack was always `200 OK` (which is required by Slack — but it meant we never saw the failure)

**Fix:** Two-pronged:
1. **Verbose logging** on every step: `[tracker] fetched N messages`, `[tracker] tagger: name <email>`, `[tracker] channel: #name`, etc. Made the failure point immediately visible in Render logs.
2. **Admin DM on every outcome** — success or failure — sent to `ADMIN_NOTIFY_EMAIL`. So Kaushik gets a Slack DM with the full result (or the exact error) within seconds of each tag.

Plus: IT added the missing Slack scopes (`channels:history`, `groups:history`, `users:read.email`) and reinstalled the app.

**Date:** 2026-06-01

---

## #9 — Manager dashboard: Sushmitha missing from leaderboard

**Issue / Feedback:** Sushmitha (role=manager) ran demos but never appeared in the Manager tab's SE leaderboard.

**RCA:** `web/backend/app/routers/dashboard.py::manager_dashboard()` queried `User.role == "se"`. Managers and admins who run their own demos were excluded by role.

**Fix:** Replaced the role filter with `User.id IN (SELECT DISTINCT se_id FROM calls WHERE scorecard IS NOT NULL)` — i.e. *any user who has actually run at least one scored call* belongs on the leaderboard, regardless of role. No more role-list maintenance, works for any future role.

**Date:** 2026-06-01

---

## #10 — Manager dashboard: no drill-down into individual call scorecards

**Issue / Feedback:** Manager leaderboard only showed per-SE aggregates. Managers wanted to click into any individual call and view the full scorecard (same as SEs see their own).

**RCA:** Feature gap — drill-down wasn't built. The `/calls/{id}` endpoint already returned the full detail (and already allowed managers/admins to view anyone's call), but no UI surfaced it on the manager page.

**Fix:** Added an "All team calls" section to `web/frontend/src/app/manager/page.tsx` below the leaderboard. Uses the existing `RecentCalls` component with `showSE={true}` to render the SE column. Each row click navigates to `/call/[id]` which reads the same per-call detail endpoint the SE flow uses.

**Date:** 2026-06-01

---

## #11 — Analysis quality: visual hallucinations on audio-only calls

**Issue / Feedback:** Team reported scoring claimed "logo not shown" and "craftsmanship poor" on calls where the screen was never shared. The model was inventing visual observations from an audio-only transcript.

**RCA:** The scoring prompt asked Claude to score every sub-criterion 0-5. For visual sub-criteria (`Craftsmanship → Personalization/Customization`, `Presentation → Relevance/Cohesion`), Claude had no choice but to guess, and the existing "score 2.5 if low confidence" rule penalized every audio-only call unfairly.

**Fix:** Three changes (bumped `scoring_prompt.VERSION` to `2026-06-v2`):
1. Prompt explicitly tells Claude it has **only a transcript, no video**. Lists which sub-criteria are visual.
2. Introduced `not_assessable: true` flag — visual sub-criteria with no verbal evidence return `score: null` and are **excluded** from the weighted average rather than penalized.
3. Updated `src/utils/call_types.py::weighted_total_for_type()` to **rescale remaining criterion weights to sum to 100** when a criterion drops out. Audio-only calls aren't unfairly deflated.

Per-call detail page now shows a grey banner listing which sub-criteria were excluded.

**Date:** 2026-06-02

---

## #12 — Analysis quality: all features mislabeled as "feature requests"

**Issue / Feedback:** Insights extractor lumped every feature mentioned on a call into `feature_requests` — including capabilities already in the product. Product/engineering had a polluted list of "requests" that were actually existing features.

**RCA:** Single `feature_requests` array in the insights prompt with no distinction between "prospect explored an existing capability" vs "prospect asked for something we don't have."

**Fix:** Split the insights schema (bumped `insights_prompt.VERSION` to `2026-06-v2`):
- `features_discussed[]` — capabilities ALREADY in the product (demoed / mentioned / asked about that exist)
- `feature_requests[]` — true gaps only (explicitly missing or our team admitted unavailable)
- Prompt now has a "CRITICAL distinction" callout with examples and a "when in doubt → discussed, not requested" tiebreaker

UI: call detail page now renders two separate cards. Old calls fall back gracefully (lumped `feature_requests` keeps displaying, `features_discussed` shows "—" until re-analyzed).

**Date:** 2026-06-02

---

## #13 — Analysis quality: Product field missing; "CX Maturity" too narrow

**Issue / Feedback:** No way to tell whether a call was about SurveySparrow, ThriveSparrow, or SparrowDesk. "CX Maturity" label was wrong for ThriveSparrow conversations (which are about employee experience, not customer experience).

**RCA:** Insights schema only had `cx_maturity.category`. No `product` field. The maturity classification assumed CX scope.

**Fix:**
- Added `insights.product.primary` (`SurveySparrow | ThriveSparrow | SparrowDesk | Unknown`) with secondary list + grounding evidence quote
- Renamed `cx_maturity` → `maturity` with a new `scope` field (`CX | EX`). Bands and dimensions unchanged
- UI: Product badge (teal / violet / orange) + Maturity badge showing "Form / Basic · CX" or "High · EX"
- Backend `_call_summary()` in `dashboard.py` and `calls.py` reads both new and legacy shapes for backward compatibility

**Date:** 2026-06-02

---

## #14 — Existing calls were analyzed under v1 prompts

**Issue / Feedback:** After shipping the v2 prompts (#11, #12, #13), Kaushik wanted existing analyzed calls retroactively re-scored under the new logic so the team sees a consistent yardstick.

**RCA:** Prompts changed; old `Scorecard`/`Insights` rows still held v1 output. No mechanism existed to re-run analysis on existing calls.

**Fix:** Built `web/backend/app/services/reanalyze.py` + admin endpoint `POST /team/reanalyze` (background task, status-polled). Modes: `outdated` (only re-runs calls where `prompt_version != current`) or `all` (force re-run everything). Updates scorecard + insights in place; preserves call dates and IDs. UI card on the Team page (admin only) with live progress + per-call error list. Added `not_assessable` JSON column to `scorecards` with idempotent ALTER TABLE migration.

**Date:** 2026-06-02

---

## #15 — Methodology drawer docs out of date after v2 changes

**Issue / Feedback:** The in-app methodology drawer (ⓘ icons) still described v1 behaviour — no mention of visual sub-criteria handling, the features split, or product/maturity scope.

**RCA:** Docs hadn't been updated alongside the prompt changes.

**Fix:** Added two new sections to `MethodologyDrawer.tsx`:
- **§7 Audio-only scoring** — explains `not_assessable`, the decision rule for visual sub-criteria, what the grey banner means, and "narrate your craft out loud during demos" takeaway
- **§8 Deal intelligence** — table of all extracted signals with a callout drawing the bright line between features discussed vs requested

Updated TL;DR, Formula (weight rescaling), Scorecard (new fields), and added 5 new FAQ entries covering the v2 changes.

**Date:** 2026-06-02

---

## #16 — Tracker: SE-only visibility was wrong policy

**Issue / Feedback:** SEs could only see their own tracker rows. Kaushik wanted everyone to see every record (team transparency on engineering asks).

**RCA:** `_query()` filtered `TrackerRequest.se_email == user.email` for SE role.

**Fix:** Removed the role filter from `web/backend/app/routers/tracker.py::_query()` and `get_tracker_item()`. Every authenticated user sees every row. Added CEO role to the Tracker tab in `TopNav.tsx`.

**Date:** 2026-06-02

---

## #17 — Tracker: schema missing Product / Kind / L2 / Jira columns

**Issue / Feedback:** Kaushik wanted tracker rows to categorize by product (SS/TS/SD), issue vs request, and capture L2 (Zendesk) + Jira links automatically.

**RCA:** Schema gap — `TrackerRequest` model only had basic fields. No categorization or external-system link columns.

**Fix:** Added columns to `TrackerRequest`: `product`, `kind`, `l2_url`, `jira_url`, `last_synced_at`. Idempotent ALTER TABLE migrations in `db.py::init_db()`. Updated CSV export to include them.

**Date:** 2026-06-02

---

## #18 — Tracker: SE attribution was the tagger, not the actual issue owner

**Issue / Feedback:** The system assigned the SE owner as whoever tagged @SE Coach. But often anyone (PM, EM, another SE) tags the bot on someone else's thread — the actual issue owner is whoever started the thread.

**RCA:** `handle_app_mention()` used `event.user` (= the tagger) for `se_email`/`se_name`. Never looked at the rest of the thread.

**Fix:** New `_resolve_se_from_first_poster()` walks the thread chronologically, finds the first non-bot human message, resolves the poster's Slack email via `users.info`, looks them up in our `User` table. If they're a known user → they're assigned as owner. Falls back to the tagger if first-poster isn't in our system. Admin DM now shows both "SE (owner)" and "Tagged by" so the auto-attribution is auditable.

**Date:** 2026-06-02

---

## #19 — Tracker: extraction should classify product/kind + capture URLs

**Issue / Feedback:** Tracker rows had no product / kind classification, and L2/Jira links in the thread weren't being captured.

**RCA:** Extraction prompt only pulled `requested_date`, `eta`, `engineer_name`, `details`, `comments`. Nothing about classification or URLs.

**Fix:** Two-layer detection:
- **LLM:** Extended the extraction prompt with `kind` (issue|request|null), `product` (SS/TS/SD/Unknown), `l2_url`, `jira_url` fields + product definitions in the system message
- **Regex (deterministic, runs in parallel):** `_extract_urls()` scans raw thread text for `*.zendesk.com/*` and `*.atlassian.net/browse/PROJ-123` patterns, including Slack's `<url|label>` wrapper

LLM-found values win; regex backfills anything LLM missed. Both run on every webhook + every daily refresh.

**Date:** 2026-06-02

---

## #20 — Tracker: daily thread refresh cron

**Issue / Feedback:** Tracker rows showed initial Slack thread content but never refreshed when new comments / L2 links / Jira tickets were added later in the same thread.

**RCA:** Feature gap. Rows only updated when someone explicitly re-tagged @SE Coach in the thread.

**Fix:** Added `refresh_open_threads()` to `slack_tracker.py`, scheduled daily at 03:00 UTC via APScheduler. For every open row:
- Re-fetches thread via `conversations.replies`
- Appends new messages (since `last_synced_at`) as timestamped comments — bot-filtered, speaker-prefixed
- Backfills L2/Jira URLs if they showed up after row creation (won't overwrite existing values)
- Auto-closes the row if any recent message contains a closure phrase (closed/resolved/shipped/deployed/done/fixed)
- Updates `last_synced_at` checkpoint

Zero Claude calls (regex + string match only) — runs against ~30 rows in seconds.

**Date:** 2026-06-02

---

## #21 — Tracker: no UI to manually edit / re-assign

**Issue / Feedback:** Auto-attribution and auto-classification get it wrong sometimes. Admin/manager needed to manually re-assign SE, fix product/kind, edit details, etc.

**RCA:** Detail drawer was read-only.

**Fix:** Added `PATCH /tracker/{item_id}` (admin/manager only) + helper endpoint `GET /tracker/ses` returning all role=se users for a dropdown. Detail drawer now has an "✎ Edit" button (visible only to admin/manager) that swaps the view for a form: SE dropdown (with current-value fallback for non-SE-role owners), product / kind / status selects, date pickers, L2/Jira URL inputs, details textarea. Save commits via PATCH and refreshes the list.

**Date:** 2026-06-02

---

## #22 — Re-extract existing tracker rows under v2 prompts

**Issue / Feedback:** Same problem as #14 but for tracker — pre-v2 rows had no product/kind/L2/Jira values.

**RCA:** Tracker prompts changed (#19); old rows still on v1 extraction.

**Fix:** Built `web/backend/app/services/tracker_reextract.py` + admin endpoint `POST /tracker/reextract`. For each row: re-fetches the original Slack thread, runs `_extract_full` under the v2 prompt, and **backfills only** — preserves any manual edits made via the edit UI (#21). UI card on the Tracker page (admin only) with per-field backfill counters + error list.

**Date:** 2026-06-02

---

## #23 — Re-extract didn't actually re-attribute SE owner

**Issue / Feedback:** After running the re-extract (#22), the SE column for existing rows still showed the original tagger. None of the first-poster corrections (#18) actually applied.

**RCA:** I'd guarded SE re-assignment with `if not row.se_email` to avoid clobbering manual edits. But every existing row already had `se_email` set (to the tagger). The guard rejected every legitimate re-attribution.

**Fix:** Removed the guard for re-extract. Re-attribution now happens on every run — if a human manually re-assigns later, they can re-edit. Added `se_email_reassigned` counter to the stats and a "N SE re-assignments (first-poster correction)" expandable audit list in the result UI showing exactly which rows changed (`from → to`).

**Date:** 2026-06-02

---

## #24 — Melodina got "Failed to fetch" clicking Tracker

**Issue / Feedback:** Melodina (role=se) clicked the Tracker tab and got `TypeError: Failed to fetch`. Other users worked fine.

**RCA:** "Failed to fetch" is a browser-level error (network / CORS / extension-block), not a server error. Two suspects:
1. **Backend risk:** if any tracker row had bad data (naive datetime, missing column) the whole list response 500'd. CORS headers may not always attach on 500s → browser reports as "Failed to fetch."
2. **Route ordering:** `/{item_id}` was declared before `/reextract/status`, `/reextract`, `/export.csv`. FastAPI's int converter could 422 those routes before reaching the correct handler.

**Fix:**
- **Per-row try/except** in the list endpoint — a single bad row is logged and skipped, doesn't kill the whole response
- **`_aware()` helper** coerces every datetime to UTC-aware before any arithmetic (prevents `naive vs aware` TypeError)
- **Reordered routes**: static paths now precede `/{item_id}`
- **Per-request log line** `[tracker.list] user=… role=…` — future per-user issues are immediately diagnosable from Render logs

**Date:** 2026-06-02

---

## #25 — Delete capability for test data

**Issue / Feedback:** Several team members were uploading test transcripts to learn the system. The DB filled with test data that was visible in production dashboards. No way to clean up.

**RCA:** No DELETE endpoints existed for calls or tracker rows.

**Fix:**
- `DELETE /calls/{call_id}` — manager/admin only. Cascades Scorecard + Insights via existing SQLAlchemy relationship config. SEs see no button and the endpoint rejects them.
- `DELETE /tracker/{item_id}` — manager/admin only. Hard delete.
- UI: red "🗑 Delete call" button on `/call/[id]` (next to Back link); "🗑 Delete" button next to Edit in the tracker drawer. Both with `confirm()` dialog naming what's being deleted. Render logs every delete with the actor + content summary.

**Date:** 2026-06-02

---

## #26 — Analyze button: silent failure on upload

**Issue / Feedback:** User clicked Analyze after pasting a transcript. Button went disabled ("Analyzing…"), then re-enabled with no result, no error message, no analysis. Loom video confirmed.

**RCA:** Two bugs compounded:
1. **Frontend:** `upload/page.tsx::submit()` had `try / finally` with no `catch`. Any thrown error from `api()` (500, timeout, network) re-enabled the button via `finally` without ever calling `setResult()`. User saw nothing.
2. **Backend:** `/calls/upload` ran scoring + insights *synchronously* inside the HTTP request. For a 45-minute transcript that's 2 sequential Claude calls = 60-120s. Render kills HTTP requests at ~100s, so longer demos timed out before completing.

**Fix:**
1. **Async pipeline:** upload endpoint now validates synchronously (cheap), creates the Call row, fires the scoring+insights as a `BackgroundTask`, returns in <1s. The call detail page shows a pulsing "Analyzing your call…" card and **polls `/calls/{id}` every 4s via SWR** until the scorecard lands, then renders it. Polling stops automatically when scorecard arrives.
2. **Error display:** added `catch` block to upload page that shows the actual error in a red box with retry instructions — user no longer sees a silent reset.

**Date:** 2026-06-03

---

## #27 — Zoom transcripts rejected when copy-pasted with timestamps

**Issue / Feedback:** Pasting a Zoom transcript (with `00:00:01.500 --> 00:00:04.200` timecodes and sequence numbers) failed validation with "looks like notes."

**RCA:** Normalizer only stripped VTT/SRT artifacts when the user *uploaded* a `.vtt` / `.srt` *file*. When the same text was pasted into the textarea, the timecode lines and sequence numbers stayed — confusing the speaker-line detector.

**Fix:** Extended `transcript_validator.py::normalize_transcript_format()` to strip — regardless of input source:
- VTT timecodes: `00:00:01.500 --> 00:00:04.200`
- SRT timecodes (comma fractional)
- Standalone integer sequence numbers (1-4 digits on their own line)
- `WEBVTT` header
- Standalone timestamps (already handled)

**Date:** 2026-06-03

---

## #28 — Users getting logged out after upload

**Issue / Feedback:** After analyzing a call, the user was kicked back to the login page. Had to re-authenticate to view their own analysis.

**RCA:** Likely correlation rather than direct causation:
- **JWT TTL was 24h.** If the user logged in early in the day and tested a transcript later, the token could expire mid-session. The call detail page fires multiple SWR requests on mount (`/auth/me`, `/calls/{id}`, and polling); whichever 401's first triggers the redirect.
- **`api()` helper was aggressive:** any 401 → `clearToken()` + hard redirect to `/login` with no memory of where the user was.

**Fix:**
- **JWT TTL extended to 7 days** in `auth.py` (internal coaching tool, low risk, much less friction)
- **Return URL preservation:** `api()` now redirects to `/login?next=<encoded-current-path>`. Login page reads `?next=` and pushes there after auth. Open-redirect guard ensures only same-origin paths are honored.
- **Infinite-loop guard:** if a 401 happens on `/login` itself, the redirect is skipped.

**Date:** 2026-06-03

---

## #29 — Otter/Avoma inline-timestamp speaker format rejected

**Issue / Feedback:** Pasting a transcript with `Speaker 1 (58:03): Perfect.` format failed with "No speaker turns detected." Screenshot showed a clearly valid transcript with three labeled speakers being rejected.

**RCA:** Two regex bugs in `transcript_validator.py`:
1. `SPEAKER_LINE_RE = r"^[A-Z][a-zA-Z\s.'-]{1,40}:"` rejected digits in speaker names. "Speaker 1" failed because of the `1`. Also fails common patterns like "Speaker 2", "Bot1".
2. No handling of inline timestamps **between the speaker name and the colon**. `Speaker 1 (58:03):` failed because the `(58:03)` chars aren't in the allowed character class.

**Fix:** Two-layer permanent solution:

**Layer 1 — heuristics (free, instant):**
- `SPEAKER_LINE_RE` now uses `\w` (allows digits + underscores): `Speaker 1`, `Speaker 2`, `Bot1`, etc.
- New `SPEAKER_INLINE_TS_RE` strips inline timestamps from speaker lines BEFORE validation: `Name (HH:MM): text` → `Name: text`. Handles parens, brackets, em-dash, bullet variants.

**Layer 2 — LLM fallback for unknown formats (~$0.005 per failed upload):**
- `validate_with_llm_fallback()` now ALSO normalizes — when heuristics fail, Claude classifies the input (transcript vs notes) AND rewrites it into canonical `Speaker: text` form. The rewritten version is re-validated.
- Wired into `/calls/upload` so unknown transcript shapes (Fellow, Fathom, proprietary tools) work without manual reformatting.

**Net result:** any transcript shape now works. Heuristics handle the common cases instantly; LLM rescues the edge cases. Only genuine notes/agendas still get rejected.

**Date:** 2026-06-03

---

## #30 — Analysis stuck on "Analyzing your call…" for 30+ minutes

**Issue / Feedback:** User uploaded a 60-min "scentia" demo. Hit "Analyze." Got redirected to the call detail page showing the "⏳ Analyzing your call…" card. Stayed there for 30+ minutes. No scorecard ever appeared. No error message. Screenshot confirmed the spinner state.

**RCA:** Multiple compounding bugs:
1. **Background task swallowed errors silently.** `_run_analysis_in_background` caught all exceptions, logged them, and returned. The Call row stayed without a Scorecard; the page polled forever waiting for one that would never come.
2. **No status field on Call.** UI had no way to know the difference between "still running" and "crashed 25 minutes ago."
3. **Claude `max_tokens=4096` was too small for fat insights JSON.** 60-min transcripts with many feature requests + use cases produce >4k tokens of output. Response truncated mid-JSON → `JSONDecodeError` → silent failure path.
4. **FastAPI `BackgroundTasks` is unreliable on Render.** Runs inside the worker process after the response. If the dyno sleeps or restarts, the task can be lost with no observable failure.
5. **No retry mechanism.** Even if the user knew it failed, there was no way to re-trigger from the UI without re-uploading.

**Fix:** Five-part comprehensive fix:
1. **Status column on `Call`**: `analysis_status` (`pending`/`analyzing`/`done`/`failed`), `analysis_started_at`, `analysis_error`. Idempotent ALTER TABLE migration. Existing rows backfilled — `done` if they have a scorecard, `failed` (with retry-prompt error message) if they don't.
2. **New `app/services/upload_analysis.py`** — replaces FastAPI BackgroundTasks with `threading.Thread(daemon=True)` for reliability. Strict lifecycle: sets status='analyzing' at entry, 'done' on success, 'failed' on any exception with a user-facing error message. Every step logged loudly to Render.
3. **Increased Claude `max_tokens` to 8192** in `LLMClient.chat_json()`. Catches JSON parse failures and raises a useful error like `"Claude returned non-JSON (stop_reason=max_tokens, output_len=4096). Likely truncated."` instead of cryptic `JSONDecodeError`.
4. **Retry endpoint** `POST /calls/{call_id}/retry` (owning SE or manager/admin). Resets status and re-spawns the analysis thread. Frontend has a 🔁 Retry button on failed calls AND a "Force retry" button if `analyzing` for >10 minutes.
5. **Stuck-cleanup cron** every 5 minutes — any call stuck in 'analyzing' for >15 min is marked 'failed' with a clear error message so the user gets a Retry button instead of a perpetual spinner.

**Plus** — the call detail page now shows three distinct states:
- `analyzing` → pulsing card with elapsed time; offers "Force retry" if >10 min
- `failed` → red error card with the server-side error message + always-on Retry button
- `done` → full scorecard renders normally

Polling automatically stops once the scorecard arrives OR the row is marked failed (no point polling a broken row).

**Date:** 2026-06-03

---

## #31 — Team feedback round 1 (Parul + Sushmitha) — analysis quality fixes

**Issue / Feedback:** Two SEs sent detailed feedback after reviewing their own scorecards.

*From Parul:*
- "AI did not capture the additional customization point I had mentioned verbally."
- "When I paused to ask if there were any questions before closing the call, the AI interpreted that as a pain point that needed to be addressed."
- "Discussed potential additional use cases — ticketing was for Phase 2. AI interpreted it as the client still needing to identify phases. A phased rollout had already been discussed during discovery."

*From Sushmitha:*
- "No demo — showing as negatives in procurement call."
- "First half of the call and discovery was driven by me but it says only 5-6 lines spoken."
- "Commercials, process, and paperwork are to be handled by AE's by default."
- "Product mapping — Captured ThriveSparrow instead of SurveySparrow."

**RCA:** Most issues are prompt-quality problems where Claude lacked the contextual rules an SE coach would naturally apply. Two are inherent limitations of Granola transcription.

**Fix (shipped — scoring + insights bumped to v3):**

1. **SE check-ins are no longer flagged as pain.** Scoring prompt now explicitly says: "any questions?", "does that make sense?", "anything I missed?" etc. are SE facilitation, NOT prospect pain that went unaddressed. Only flag a pain if the PROSPECT raised it and the SE failed to loop back.

2. **AE-domain topics no longer dock the SE.** Scoring prompt explicitly excludes from SE evaluation: commercial terms, pricing, contracts/SOW, procurement process, security questionnaires, billing, legal review. These are AE responsibilities by default — SE stepping aside is good role boundary, not a gap.

3. **Phased rollouts respected.** If the prospect says "Phase 1 / Phase 2" or refers to prior planning, the phases have already been defined — don't flag them as needing identification.

4. **New call type: `procurement`** with appropriate weight profile (Consultative Approach 40%, Solution Skills only 10%, Craftsmanship 10%, no demo expected). Auto-detection in `_detect_call_type()` triggers on title keywords: procurement, security review, vendor security, SOC 2, compliance, infosec, vendor onboarding, security questionnaire, etc. Procurement option added to the upload UI picker.

5. **Stronger product classification rules.** Insights prompt v3 has explicit signal lists per product (e.g. "customer" repeated → SurveySparrow; "employee/team member/manager" repeated → ThriveSparrow), a "DEFAULT to SurveySparrow when uncertain — ThriveSparrow needs EXPLICIT employee-focused signals" rule, and "return Unknown rather than guessing" guidance. Surveysparrow-vs-ThriveSparrow confusion in customer-focused calls (Sushmitha's mis-classified call) should now resolve correctly.

**Honest limitations — NOT fixed in this round:**

- **"5-6 lines spoken" for Sushmitha's call.** This is a Granola transcript-fidelity issue, not analysis logic. Granola only distinguishes the *microphone-source speaker* (= the Granola account holder) from *everyone else mixed together*. If Sushmitha was NOT the Granola account owner for that recording (e.g. she joined someone else's calendar invite), her turns get lumped with the prospect/AE in the "speaker" track and we can't attribute them back to her. The fix is operational, not code: SEs should be the Granola account owner on their own calls so their microphone is identified separately. For calls where SE attribution matters and Granola isn't reliable, pasting a richer per-speaker transcript via the Upload flow is the workaround.

- **Missing specific verbal mentions (Parul's customization point).** This is inherent LLM recall — Claude reads the whole transcript but its summarization will sometimes miss a specific sentence. Re-running with the v3 prompt may catch it; can't guarantee 100%. If a specific point matters, the SE can ask Claude directly via the (planned) per-call chat feature, or note it in the manual coaching action.

- **Cross-call context (Parul's phased rollout already done in discovery).** The system only sees the current call's transcript — no memory of earlier discovery calls with the same prospect. We could solve this by linking calls by prospect_company and feeding earlier-call summaries as context, but that's a bigger architectural change. For now, the v3 prompt at least won't flag phases as "still needing identification" — but it also can't actively reference what was decided in the earlier discovery call.

**Recommended action after deploy:** kaushik re-runs the admin "Re-analyze under current prompts" job (Team page → outdated mode) so Parul's and Sushmitha's existing calls get re-scored under v3.

**Date:** 2026-06-03

---

## #32 — BU Head dashboard for Rishul — deal anatomy, buying committee, velocity, incumbent displacement, aha patterns

**Issue / Feedback:** BU Head Rishul reviewed the prototype dashboard, found the direction useful, asked for additional deal-anatomy detail: buying committee composition with titles, primary/secondary users, the aha moment that sealed the deal, days from first demo → close, days from close → go-live, previous tool + years used + switching reason, how prospects discovered us. Anything not auto-extractable should be an SE-editable field.

**RCA:** N/A — feature request.

**Fix (shipped):**

1. **Insights prompt v4** — added `buying_committee[]` (with role: champion / decision_maker / primary_user / secondary_user / it_security / procurement / finance / exec_sponsor / influencer), `primary_users`, `incumbent` (tool / years_using / experience / switching_reason), `discovery_source`, `aha_candidates[]`. All auto-extracted from the transcript.

2. **`Call` schema additions** — `deal_outcome` (open/won/lost/no_decision), `closed_date`, `go_live_date`, `discovery_source_override`, `aha_moment_override`, `enrichment_notes`, `enrichment_updated_at`, `enrichment_updated_by`. Idempotent ALTER TABLE migration in `db.py::init_db()`.

3. **`PATCH /calls/{call_id}/enrichment`** — owning SE can edit their own call; manager/admin can edit any. CEO/BU head are read-only.

4. **New role `bu_head`** added to deps + TopNav. Admin + manager + CEO + bu_head can view `/bu`. Team page user-creation includes bu_head option.

5. **`GET /dashboard/bu`** aggregator — wins (with full anatomy), buying committee patterns (with score-when-present vs score-when-absent), deal velocity cohorts (median + P90, split by product/POC/source/maturity), incumbent displacement (with top switching reason), discovery source (with win rate per channel), aha patterns (by category — what's actually closing deals).

6. **`/bu` page** — data-dense, export-first, no graphics. Every panel has a `⤓ CSV` button that downloads the actual table data. Print/PDF button at top for board-deck snapshots. Deal-anatomy cards for each win show buying committee with role pills, previous tool, discovery source, demo→close + close→go-live days, and the aha moment as a teal pull-quote.

7. **Enrichment edit form on `/call/[id]`** — SE clicks "✎ Edit fields", form has deal outcome selector, close/go-live date pickers, discovery source override (dropdown matching the v4 enum), aha override (textarea — prefill auto-extracted candidate), enrichment notes (free text).

8. **Auto-extracted deal-anatomy surfaced** on the existing call detail deal-intelligence grid — Previous tool, Discovery source, Buying committee (N), Primary users. So SEs see what was auto-extracted before they decide what to override.

**Recommended action after deploy:** kaushik triggers the admin "Re-analyze under current prompts" job to backfill the v4 fields onto existing analyzed calls. New calls automatically use v4. SEs then go through their wins and fill in `deal_outcome=won`, `closed_date`, `go_live_date` from the corresponding CRM record.

**Open follow-ups (deferred to next iteration):**
- HubSpot/Salesforce sync to auto-populate close + go-live dates (removes manual entry).
- Monthly emailed digest of the BU dashboard (Render mail + Jinja template).
- ACV / deal-value weighting once CRM is connected (currently using deal counts).

**Date:** 2026-06-05

---

## #33 — Manual HubSpot fields on Call + ACV-weighted BU dashboard panels

**Issue / Feedback:** Kaushik confirmed the BU dashboard direction but flagged that real HubSpot integration would take too long. Asked for the same data fields exposed as SE-editable inputs so the dollar-weighted panels can work today.

**RCA:** Feature scope decision — defer real CRM integration, ship manual entry first.

**Fix (shipped):**

1. **5 new manual columns on `Call`**: `deal_value` (numeric), `deal_currency` (default USD), `deal_stage` (10-value enum from prospecting → closed_won/lost), `crm_deal_url` (link back to HubSpot deal), `expected_close_date`. Idempotent ALTER TABLE migration.

2. **Enrichment form on `/call/[id]` now has three labeled sections:**
   - **Deal status (from HubSpot — manual for now)**: outcome, stage, value, currency, CRM link, expected close
   - **Dates after close**: closed date, go-live date
   - **Context (override auto-extracted)**: discovery source override, aha override, notes

3. **BU dashboard headlines row 2** added: *Won this period ($)*, *Open pipeline ($)*, *Pipeline at risk ($)* (open deals with loss-risk signals), *Avg deal size*. With an italic footnote noting the multi-currency caveat.

4. **New "Pipeline by stage" panel** showing deal count + how many have $ entered + total value per stage, with "missing values" warning on stages where SEs haven't filled in.

5. **Wins panel cards now show ACV prominently** (top-right, emerald) next to the velocity numbers, plus a small "HubSpot ↗" link to the source-of-truth deal page if `crm_deal_url` is filled.

6. **Discovery source table extended** with *Total won $* and *Avg deal size* columns — Rishul can see "Referrals: 6 wins, $580K total, avg $96K" instead of just "Referrals: 6 wins."

**Honest caveats kept in the UI:**
- Multi-currency: aggregations sum across currencies. Footnote tells SEs to enter USD-equivalent if they want accurate totals. HubSpot sync solves this properly later.
- "% of stages with missing values" callout on the Pipeline panel — Rishul will see immediately how much data SEs have entered vs not.

**Recommended SE rollout:** kaushik sends a short Slack note asking each SE to go to their current open deals + recent closed deals, and fill in deal_value + deal_stage + crm_deal_url. ~5 min per deal × ~10 deals per SE = 50 min one-time backfill per SE. Going forward, it's a 30-second add at the time of deal-stage change.

**Open follow-ups (deferred):**
- Real HubSpot connector via OAuth, syncing deal value + stage + close date + amount currency hourly.
- Per-currency aggregations on the BU panels (separate totals per currency code) once we have HubSpot's currency on each deal.
- ACV-weighted feature-gap and loss-risk panels (currently still deal-count weighted).

**Date:** 2026-06-05

---

## Open / pending items

These haven't been fixed yet:

- **#6 — Granola workspace-scoped API key.** Email to Granola support pending. Multi-token fallback design ready to deploy if their answer is no.
- **Render dyno restarts during long uploads.** Now much less likely after #26 made uploads <1s, but if it ever recurs we may need a `status` column on `Call` (`pending`/`analyzing`/`done`/`failed`) to support explicit retry from the UI.

---

*This document is auto-maintained by the SE Coach development workflow. Every new bug or feedback item that surfaces will be appended here using the same Issue / RCA / Fix / Date format. Source-of-truth lives at `se-demo-assessment-agent/POST_DEPLOYMENT_CHANGELOG.md` in the repo; the linked Google Doc mirrors it.*
