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


# Try a handful of plausible locations for the markdown file. Render's Docker
# build copies the file to /app/POST_DEPLOYMENT_CHANGELOG.md; locally it sits
# at the repo root. We try both.
def _find_markdown_path() -> Path | None:
    candidates = [
        Path("/app/POST_DEPLOYMENT_CHANGELOG.md"),
        Path(__file__).resolve().parents[4] / "POST_DEPLOYMENT_CHANGELOG.md",
        Path(__file__).resolve().parents[5] / "POST_DEPLOYMENT_CHANGELOG.md",
        Path.cwd() / "POST_DEPLOYMENT_CHANGELOG.md",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


MARKDOWN_PATH = _find_markdown_path()


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


def _read_markdown() -> str | None:
    """Read the markdown content from disk if available."""
    if MARKDOWN_PATH and MARKDOWN_PATH.exists():
        return MARKDOWN_PATH.read_text(encoding="utf-8")
    return None


def seed_if_empty():
    """Populate the changelog table from the markdown file IF it's currently
    empty. No-op once any entry exists."""
    from app.db import SessionLocal
    from app.models import ChangelogEntry

    db = SessionLocal()
    try:
        existing = db.query(ChangelogEntry).count()
        if existing > 0:
            print(f"[changelog_seeder] skipping — {existing} entries already in DB")
            return

        text = _read_markdown()
        if not text:
            print(f"[changelog_seeder] skipping — markdown file not found at any candidate path")
            return

        entries = parse_markdown(text)
        if not entries:
            print(f"[changelog_seeder] parsed 0 entries; skipping seed")
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


def force_reseed(wipe_existing: bool = False) -> dict:
    """Admin-triggered re-import. Returns stats dict.

    - If `wipe_existing=True`: deletes every row, then re-imports the markdown.
      Use to overwrite the entire DB with the markdown's current state.
    - If `wipe_existing=False`: imports only entries whose entry_number isn't
      already in the DB. Use to top up missing entries without disturbing
      anything already there (e.g. seed only happened partially before).
    """
    from app.db import SessionLocal
    from app.models import ChangelogEntry

    stats = {"existing_before": 0, "added": 0, "skipped_already_present": 0,
             "wiped": 0, "markdown_found": False, "errors": []}

    text = _read_markdown()
    stats["markdown_found"] = bool(text)
    if not text:
        stats["errors"].append("Markdown source file not found at any candidate path")
        return stats

    entries = parse_markdown(text)
    if not entries:
        stats["errors"].append("Parsed 0 entries from markdown")
        return stats

    db = SessionLocal()
    try:
        stats["existing_before"] = db.query(ChangelogEntry).count()

        if wipe_existing:
            stats["wiped"] = db.query(ChangelogEntry).delete()
            db.commit()

        existing_numbers = {row[0] for row in db.query(ChangelogEntry.entry_number).all()}

        for e in entries:
            if e["entry_number"] in existing_numbers:
                stats["skipped_already_present"] += 1
                continue
            try:
                db.add(ChangelogEntry(
                    entry_number=e["entry_number"],
                    title=e["title"],
                    issue=e["issue"],
                    rca=e["rca"],
                    fix=e["fix"],
                    entry_date=e["entry_date"],
                    status=e["status"],
                    created_by="system (force reseed)",
                ))
                stats["added"] += 1
            except Exception as ex:
                stats["errors"].append(f"#{e['entry_number']}: {ex}")
        db.commit()
        print(f"[changelog_seeder] force_reseed done: {stats}")
    except Exception as ex:
        db.rollback()
        stats["errors"].append(str(ex))
    finally:
        db.close()
    return stats
