"""
One-time changelog seed from POST_DEPLOYMENT_CHANGELOG.md.

Runs on first deploy after the changelog table is created. Idempotent —
checks if the table is already populated before doing anything. After
the seed, the markdown file becomes a snapshot; the DB is the live
source of truth.

Parser is intentionally tolerant: each top-level entry is `## #N — Title`,
and inside the entry we extract `**Issue / Feedback:**`, `**RCA:**`,
`**Fix*:** ...`, and `**Date:**` sections. Anything that doesn't match the
pattern is placed into the `fix` field as a catch-all so no data is lost.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Repo root: app/ → web/backend/ → web/ → repo
_REPO_ROOT = Path(__file__).resolve().parents[4]
MARKDOWN_PATH = _REPO_ROOT / "POST_DEPLOYMENT_CHANGELOG.md"


_ENTRY_HEADER_RE = re.compile(
    r"^##\s+#(?P<num>\d+)\s+[—\-–]\s+(?P<title>.+?)\s*$",
    re.MULTILINE,
)

# Section labels we recognize inside an entry. Order matters for fallback.
_SECTION_LABELS = [
    ("issue", r"\*\*Issue\s*/\s*Feedback:\*\*"),
    ("rca",   r"\*\*RCA:\*\*"),
    ("fix",   r"\*\*Fix(?:\s*\([^)]+\))?:\*\*"),  # supports "Fix:" or "Fix (shipped):"
    ("date",  r"\*\*Date:\*\*"),
]


def _parse_date(s: str) -> Optional[datetime]:
    s = s.strip()
    # Strip parenthetical suffixes like "(in progress)"
    s = re.sub(r"\s*\(.*\)$", "", s).strip()
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _split_entry_body(body: str) -> dict:
    """Split an entry's body into Issue / RCA / Fix / Date sections.

    Tolerant: anything outside the labelled sections gets appended to the
    `fix` field rather than dropped. The 'Date' section is parsed to a
    datetime if possible.
    """
    out = {"issue": "", "rca": "", "fix": "", "date": ""}

    # Find each label and where it starts in the body
    starts = []
    for key, label_re in _SECTION_LABELS:
        m = re.search(label_re, body)
        if m:
            starts.append((m.start(), m.end(), key))
    starts.sort()

    if not starts:
        # Nothing matched — dump the whole body into 'fix' so it's at least visible
        out["fix"] = body.strip()
        return out

    # For each label, the section content is from the label's end to the next label's start
    for i, (start, end, key) in enumerate(starts):
        next_start = starts[i + 1][0] if i + 1 < len(starts) else len(body)
        section_text = body[end:next_start].strip()
        # Strip trailing "---" separators if any leaked in
        section_text = re.sub(r"\n\s*---\s*\n?$", "\n", section_text).rstrip("-").strip()
        out[key] = section_text

    return out


def parse_markdown(text: str) -> list[dict]:
    """Parse the whole changelog file into a list of entry dicts."""
    entries = []
    matches = list(_ENTRY_HEADER_RE.finditer(text))
    for i, m in enumerate(matches):
        entry_num = int(m.group("num"))
        title = m.group("title").strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        # Strip leading/trailing separators between entries
        body = re.sub(r"^\s*---\s*\n", "", body)
        body = re.sub(r"\n\s*---\s*$", "", body)

        sections = _split_entry_body(body)
        date_obj = _parse_date(sections.get("date", ""))

        entries.append({
            "entry_number": entry_num,
            "title": title[:500],
            "issue": sections.get("issue", "").strip() or "(no issue section)",
            "rca": sections.get("rca", "").strip() or "(no RCA section)",
            "fix": sections.get("fix", "").strip() or "(no fix section)",
            "entry_date": date_obj or datetime.now(timezone.utc),
            "status": "shipped",
        })
    return entries


def seed_if_empty():
    """Populate the changelog table from the markdown file IF it's currently
    empty. No-op once any entry exists (so future UI-added entries aren't
    overwritten on subsequent deploys)."""
    from app.db import SessionLocal
    from app.models import ChangelogEntry

    db = SessionLocal()
    try:
        existing = db.query(ChangelogEntry).count()
        if existing > 0:
            print(f"[changelog_seeder] skipping — {existing} entries already in DB")
            return

        if not MARKDOWN_PATH.exists():
            print(f"[changelog_seeder] skipping — {MARKDOWN_PATH} not found")
            return

        text = MARKDOWN_PATH.read_text(encoding="utf-8")
        entries = parse_markdown(text)

        if not entries:
            print(f"[changelog_seeder] parsed 0 entries from {MARKDOWN_PATH}; skipping seed")
            return

        for e in entries:
            db.add(ChangelogEntry(
                entry_number=e["entry_number"],
                title=e["title"],
                issue=e["issue"],
                rca=e["rca"],
                fix=e["fix"],
                entry_date=e["entry_date"],
                status=e["status"],
                created_by="system (markdown seed)",
            ))
        db.commit()
        print(f"[changelog_seeder] seeded {len(entries)} entries from markdown")
    except Exception as e:
        db.rollback()
        print(f"[changelog_seeder] error: {e}")
    finally:
        db.close()
