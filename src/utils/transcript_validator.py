"""
Transcript-vs-notes validator + format normalizer.

Goal: when an SE pastes/uploads content in the portal, reject meeting notes /
summaries / agendas and accept only raw call transcripts.

Tools export transcripts in different shapes:
  - Canonical:  "Speaker: text"          (Zoom, Teams, Otter, our internal default)
  - Avoma:       Speaker on own line, text on the NEXT line(s)
  - Granola:    "Speaker: text"          (canonical)
  - VTT/SRT:    Stripped to "Speaker: text" elsewhere

We auto-normalize Avoma-style input into canonical form before validating,
so the user doesn't have to think about source format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ValidationResult:
    ok: bool
    kind: str           # 'ok' | 'warn' | 'empty' | 'short' | 'no_speakers' | 'few_turns' | 'notes' | 'doc'
    title: str
    detail: str
    metrics: dict
    normalized: str = ""    # normalized transcript text (callers should use this downstream)


SPEAKER_LINE_RE = re.compile(r"^[A-Z][a-zA-Z\s.'-]{1,40}:", re.MULTILINE)
NOTES_MARKERS_RE = re.compile(
    r"^\s*[-•*]\s|"
    r"\bAction items?:|\bKey takeaways?:|\bNext steps?:|"
    r"\bDecisions?:|\bSummary:|\bAgenda:|\bAttendees?:",
    re.IGNORECASE | re.MULTILINE,
)
HEADING_RE = re.compile(r"^#+\s", re.MULTILINE)
FILLER_RE = re.compile(r"\b(um|uh|yeah|right\?|you know|kind of|sort of|I mean)\b", re.IGNORECASE)

# Strip standalone timestamp lines:
#   "00:23", "[12:34]", "(00:01:23)", "01:23:45"
TIMESTAMP_RE = re.compile(r"^\s*[\[(]?\d{1,2}(:\d{2}){1,2}[\])]?\s*$",
                          re.MULTILINE)

# Strip VTT/SRT-style timecode lines (Zoom export, Otter, etc):
#   "00:00:01.500 --> 00:00:04.200"   (VTT, dot fractional)
#   "00:00:01,500 --> 00:00:04,200"   (SRT, comma fractional)
#   "0:00:01 --> 0:00:04"             (no fractional)
VTT_TIMECODE_RE = re.compile(
    r"^\s*\d{1,2}:\d{2}(:\d{2})?([.,]\d{1,3})?\s*-->\s*\d{1,2}:\d{2}(:\d{2})?([.,]\d{1,3})?.*$",
    re.MULTILINE,
)

# Strip SRT sequence-number lines (a single integer on its own line, typical
# in SRT/Zoom exports before each subtitle block). Be careful not to nuke
# legitimate one-line-of-digits content — we only match lines that are JUST
# 1-4 digits.
SRT_INDEX_RE = re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE)

# WEBVTT header line — appears once at top of VTT files
WEBVTT_HEADER_RE = re.compile(r"^\s*WEBVTT.*$", re.MULTILINE | re.IGNORECASE)

# Strip inline timestamps from speaker lines, e.g.
#   "John Doe (00:00:23)"        ← Granola
#   "John Doe [00:00:23]"        ← some Granola variants
#   "John Doe • 00:00:23"        ← Granola newer
#   "John Doe - 00:00:23"        ← Fathom / Fellow
#   "John Doe — 0:23"            ← em-dash variant
INLINE_TS_TAIL_RE = re.compile(
    r"\s*[•\-–—]?\s*[\[(]?\s*\d{1,2}(:\d{2}){1,2}\s*[\])]?\s*$"
)
# Strip a leading timestamp from a line: "[00:23] John Doe", "00:23 John Doe"
INLINE_TS_HEAD_RE = re.compile(
    r"^\s*\[?\(?\s*\d{1,2}(:\d{2}){1,2}\s*\)?\]?\s+"
)


def _strip_inline_timestamps(s: str) -> str:
    """Remove leading and trailing timestamp segments from a line."""
    s = INLINE_TS_TAIL_RE.sub("", s)
    s = INLINE_TS_HEAD_RE.sub("", s)
    return s.strip()

MIN_WORDS = 500
MIN_SPEAKERS = 2
MIN_TURNS = 10


# -------------------------------------------------------------
# Normalizer
# -------------------------------------------------------------

def _looks_like_speaker_only_line(line: str) -> bool:
    """Heuristic: does this line (after timestamp stripping) look like just a
    speaker name (Avoma + Granola + Otter + Fathom-style turn header)?"""
    line = _strip_inline_timestamps(line).strip()
    if not line or len(line) > 50:
        return False
    if line.endswith((".", "?", "!", ":", ",", ";")):
        return False
    if any(ch.isdigit() for ch in line):
        return False
    # Reject lines containing common email/handle characters
    if any(ch in line for ch in "@<>/\\|"):
        return False
    words = line.split()
    if not (1 <= len(words) <= 5):
        return False
    # Every "word" should start with an uppercase letter, allow lowercase particles
    PARTICLES = {"de", "van", "von", "la", "le", "du", "der", "den", "el", "bin", "ibn"}
    cap_words = sum(1 for w in words if w[:1].isupper() or w.lower() in PARTICLES)
    return cap_words == len(words)


def _clean_speaker_name(line: str) -> str:
    """Get the clean speaker name from a line (timestamps removed)."""
    return _strip_inline_timestamps(line).strip()


def normalize_transcript_format(text: str) -> str:
    """
    Detect Avoma-style speaker-on-own-line format and convert to canonical
    'Speaker: text' lines. Idempotent — text already in canonical form is
    returned unchanged.
    """
    if not text:
        return ""
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Drop VTT/SRT artifacts that Zoom + Otter exports leave behind when
    # users paste rather than uploading the .vtt file directly.
    text = WEBVTT_HEADER_RE.sub("", text)
    text = VTT_TIMECODE_RE.sub("", text)
    text = SRT_INDEX_RE.sub("", text)
    # Drop standalone timestamp lines
    text = TIMESTAMP_RE.sub("", text)

    lines = [l.rstrip() for l in text.split("\n")]
    out_lines: list[str] = []
    current_speaker: str | None = None
    current_buf: list[str] = []

    def flush():
        if current_speaker and current_buf:
            out_lines.append(f"{current_speaker}: {' '.join(current_buf).strip()}")
        elif current_buf:
            out_lines.append(" ".join(current_buf).strip())

    for raw in lines:
        line = raw.strip()
        if not line:
            # blank line — flush current turn
            flush()
            current_speaker = None
            current_buf = []
            continue

        # Already-canonical line ("Name: text") — pass through
        if SPEAKER_LINE_RE.match(line):
            flush()
            current_speaker = None
            current_buf = []
            out_lines.append(line)
            continue

        # Speaker-only line (Avoma / Granola / Otter / Fathom style)
        if _looks_like_speaker_only_line(line):
            flush()
            current_speaker = _clean_speaker_name(line)
            current_buf = []
            continue

        # Body text — append to current turn
        current_buf.append(line)

    flush()
    return "\n".join(l for l in out_lines if l.strip())


# -------------------------------------------------------------
# Validator
# -------------------------------------------------------------

def validate(text: str) -> ValidationResult:
    """Validate whether `text` is a real call transcript or meeting notes."""
    raw = (text or "").strip()
    if not raw:
        return ValidationResult(False, "empty", "Empty input",
                                "Paste a transcript or upload a file.", {}, "")

    # Normalize first — handles Avoma + variants
    normalized = normalize_transcript_format(raw)

    words = normalized.split()
    word_count = len(words)
    if word_count < MIN_WORDS:
        return ValidationResult(False, "short",
                                "Too short to be a real call transcript",
                                f"Only {word_count} words. Minimum {MIN_WORDS} — looks like a snippet, not a full call.",
                                {"word_count": word_count}, normalized)

    speaker_lines = SPEAKER_LINE_RE.findall(normalized)
    distinct_speakers = len({s.replace(":", "").strip() for s in speaker_lines})
    notes_markers = len(NOTES_MARKERS_RE.findall(normalized))
    heading_markers = len(HEADING_RE.findall(normalized))
    fillers = len(FILLER_RE.findall(normalized))
    turn_count = len(speaker_lines)

    metrics = {
        "word_count": word_count,
        "distinct_speakers": distinct_speakers,
        "turn_count": turn_count,
        "notes_markers": notes_markers,
        "heading_markers": heading_markers,
        "fillers": fillers,
        "was_normalized": normalized != raw,
    }

    if distinct_speakers < MIN_SPEAKERS:
        return ValidationResult(False, "no_speakers",
                                "No speaker turns detected",
                                f"A real transcript has labeled turns like 'Ishrath: ...' for ≥{MIN_SPEAKERS} different speakers. "
                                f"Detected {distinct_speakers}. (If pasting from Avoma, make sure speaker names appear on their own lines above each spoken segment.)",
                                metrics, normalized)

    if turn_count < MIN_TURNS:
        return ValidationResult(False, "few_turns",
                                "Too few speaker turns",
                                f"Only {turn_count} turn-takes detected — real calls have dozens. "
                                f"This looks like notes or a summary, not a transcript.",
                                metrics, normalized)

    if notes_markers >= 3 and fillers < 5:
        return ValidationResult(False, "notes",
                                "This looks like meeting notes, not a transcript",
                                f"Found {notes_markers} bullet/heading markers and only {fillers} conversational fragments. "
                                f"Please paste the raw spoken-word transcript instead.",
                                metrics, normalized)

    if heading_markers >= 2:
        return ValidationResult(False, "doc",
                                "This looks like a structured document",
                                f"Detected {heading_markers} markdown headings. Please paste the raw spoken-word transcript.",
                                metrics, normalized)

    if fillers < 3 and word_count > 800:
        return ValidationResult(True, "warn",
                                "Looks like a transcript but very formal",
                                "Few conversational fragments detected. If this is a cleaned-up summary, scoring accuracy may be reduced.",
                                metrics, normalized)

    return ValidationResult(True, "ok",
                            f"Looks good — {word_count} words, ~{turn_count} turns, {distinct_speakers} speakers"
                            + (" (auto-formatted from Avoma)" if metrics["was_normalized"] else ""),
                            "Ready to analyze. Estimated time: 30–45 seconds.",
                            metrics, normalized)


def validate_with_llm_fallback(text: str, llm=None) -> ValidationResult:
    """For borderline cases, optionally double-check with a quick LLM call."""
    result = validate(text)
    if result.kind != "warn" or llm is None:
        return result

    system = "You are a strict classifier. Reply with only 'TRANSCRIPT' or 'NOTES'."
    user = (
        "Is the following text a raw spoken-word call transcript (speaker turns, "
        "conversational fragments) or post-call meeting notes / summary / agenda?\n\n"
        f"---\n{text[:3000]}\n---"
    )
    try:
        raw = llm.chat_json(
            system=system + " Output JSON: {\"classification\": \"TRANSCRIPT\" | \"NOTES\"}",
            user=user,
            mock_response={"classification": "TRANSCRIPT"},
        )
        if raw.get("classification") == "NOTES":
            return ValidationResult(False, "notes",
                                    "LLM classified this as notes, not a transcript",
                                    "Even though it looked like a transcript at first glance, the content reads like a summary. Please paste the raw transcript.",
                                    result.metrics, result.normalized)
    except Exception:
        pass
    return result
