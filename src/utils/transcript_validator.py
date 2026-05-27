"""
Transcript-vs-notes validator.

Goal: when an SE pastes/uploads content in the portal, reject meeting notes /
summaries / agendas and accept only raw call transcripts. Show the SE a clear
reason if rejected.

Approach: heuristic classifier first (fast, no LLM call). For borderline cases
escalate to a single Claude call for binary classification.

Heuristics:
  - Transcript signals (POSITIVE):
      • Speaker turns: "Name: text" pattern repeated, ≥2 distinct speakers
      • Conversational fragments: "um", "uh", "yeah", "right?", "you know"
      • Short interrupted sentences (median word count < 20)
  - Notes signals (NEGATIVE):
      • Bullet markers (-, •, *) at line start
      • Headings: "Action items:", "Key takeaways:", "Next steps:", "Summary:"
      • Markdown headers (#, ##)
      • Long monologue sentences (>30 words)
      • Single-author voice (no turn-taking)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    ok: bool
    kind: str           # 'ok' | 'warn' | 'empty' | 'short' | 'no_speakers' | 'few_turns' | 'notes' | 'doc'
    title: str
    detail: str
    metrics: dict


SPEAKER_RE = re.compile(r"^[A-Z][a-zA-Z\s.'-]{1,40}:", re.MULTILINE)
NOTES_MARKERS_RE = re.compile(
    r"^\s*[-•*]\s|"
    r"\bAction items?:|\bKey takeaways?:|\bNext steps?:|"
    r"\bDecisions?:|\bSummary:|\bAgenda:|\bAttendees?:",
    re.IGNORECASE | re.MULTILINE,
)
HEADING_RE = re.compile(r"^#+\s", re.MULTILINE)
FILLER_RE = re.compile(r"\b(um|uh|yeah|right\?|you know|kind of|sort of|I mean)\b", re.IGNORECASE)

MIN_WORDS = 500
MIN_SPEAKERS = 2
MIN_TURNS = 10


def validate(text: str) -> ValidationResult:
    """Validate whether `text` is a real call transcript or meeting notes."""
    text = (text or "").strip()
    if not text:
        return ValidationResult(False, "empty", "Empty input",
                                "Paste a transcript or upload a file.", {})

    words = text.split()
    word_count = len(words)
    if word_count < MIN_WORDS:
        return ValidationResult(False, "short",
                                "Too short to be a real call transcript",
                                f"Only {word_count} words. Minimum {MIN_WORDS} — looks like a snippet, not a full call.",
                                {"word_count": word_count})

    speaker_lines = SPEAKER_RE.findall(text)
    distinct_speakers = len({s.replace(":", "").strip() for s in speaker_lines})
    notes_markers = len(NOTES_MARKERS_RE.findall(text))
    heading_markers = len(HEADING_RE.findall(text))
    fillers = len(FILLER_RE.findall(text))
    turn_count = len(speaker_lines)

    metrics = {
        "word_count": word_count,
        "distinct_speakers": distinct_speakers,
        "turn_count": turn_count,
        "notes_markers": notes_markers,
        "heading_markers": heading_markers,
        "fillers": fillers,
    }

    if distinct_speakers < MIN_SPEAKERS:
        return ValidationResult(False, "no_speakers",
                                "No speaker turns detected",
                                f"A real transcript has labeled turns like 'Ishrath: ...' for ≥{MIN_SPEAKERS} different speakers. "
                                f"Detected {distinct_speakers}.",
                                metrics)

    if turn_count < MIN_TURNS:
        return ValidationResult(False, "few_turns",
                                "Too few speaker turns",
                                f"Only {turn_count} turn-takes detected — real calls have dozens. "
                                f"This looks like notes or a summary, not a transcript.",
                                metrics)

    if notes_markers >= 3 and fillers < 5:
        return ValidationResult(False, "notes",
                                "This looks like meeting notes, not a transcript",
                                f"Found {notes_markers} bullet/heading markers and only {fillers} conversational fragments. "
                                f"Please paste the raw spoken-word transcript instead.",
                                metrics)

    if heading_markers >= 2:
        return ValidationResult(False, "doc",
                                "This looks like a structured document",
                                f"Detected {heading_markers} markdown headings. Please paste the raw spoken-word transcript.",
                                metrics)

    if fillers < 3 and word_count > 800:
        return ValidationResult(True, "warn",
                                "Looks like a transcript but very formal",
                                "Few conversational fragments detected. If this is a cleaned-up summary, scoring accuracy may be reduced.",
                                metrics)

    return ValidationResult(True, "ok",
                            f"Looks good — {word_count} words, ~{turn_count} turns, {distinct_speakers} speakers",
                            "Ready to analyze. Estimated time: 30–45 seconds.",
                            metrics)


def validate_with_llm_fallback(text: str, llm=None) -> ValidationResult:
    """
    For borderline cases (warn), optionally double-check with a quick LLM call.
    Wires into the existing LLMClient.
    """
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
        # We piggy-back on the existing LLMClient with a tiny mock-fallback.
        raw = llm.chat_json(
            system=system + " Output JSON: {\"classification\": \"TRANSCRIPT\" | \"NOTES\"}",
            user=user,
            mock_response={"classification": "TRANSCRIPT"},
        )
        if raw.get("classification") == "NOTES":
            return ValidationResult(False, "notes",
                                    "LLM classified this as notes, not a transcript",
                                    "Even though it looked like a transcript at first glance, the content reads like a summary. Please paste the raw transcript.",
                                    result.metrics)
    except Exception:
        pass
    return result
