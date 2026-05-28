"""
Demo of the Month — top SEs by average score on demo + follow-up demo calls
for the current calendar month.

Eligibility rule (configurable): an SE must have at least MIN_CALLS scored
demo-class calls in the month. This prevents one lucky high-scoring call from
trumping consistent strong performance.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Call


MIN_CALLS = 2                      # eligibility threshold
DEMO_TYPES = ("demo", "followup_demo")
TOP_N = 2


def compute_dotm(db: Session, month: Optional[str] = None) -> list[dict]:
    """
    Return the top-N SEs for the given month (YYYY-MM, defaults to current).
    Each entry: {se_name, se_email, avg_score, call_count, rank}
    """
    month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    cutoff_year, cutoff_month = month.split("-")

    # Pull all scored demo calls for the month
    calls = (
        db.query(Call)
        .filter(Call.call_type.in_(DEMO_TYPES))
        .filter(Call.scorecard.has())
        .all()
    )

    # Group by SE, filter to current month
    by_se: dict[int, dict] = defaultdict(lambda: {"scores": [], "name": "", "email": ""})
    for c in calls:
        when = (c.call_date or c.created_at)
        if when.strftime("%Y-%m") != month:
            continue
        bucket = by_se[c.se_id]
        bucket["scores"].append(c.scorecard.weighted_final)
        bucket["name"] = c.se_name
        # se relationship is lazy; if accessing email, fetch:
        if c.se and not bucket["email"]:
            bucket["email"] = c.se.email

    # Apply eligibility threshold and rank
    eligible = [
        {
            "se_id": se_id,
            "se_name": data["name"],
            "se_email": data["email"],
            "avg_score": round(mean(data["scores"]), 2),
            "call_count": len(data["scores"]),
        }
        for se_id, data in by_se.items()
        if len(data["scores"]) >= MIN_CALLS
    ]
    eligible.sort(key=lambda x: x["avg_score"], reverse=True)

    # Assign ranks; only return top N
    out = []
    for rank, entry in enumerate(eligible[:TOP_N], start=1):
        entry["rank"] = rank
        out.append(entry)
    return out


def is_winner(db: Session, se_email: str, month: Optional[str] = None) -> Optional[dict]:
    """If the given SE is one of the top-N DOTM winners, return their entry."""
    winners = compute_dotm(db, month)
    for w in winners:
        if w["se_email"].lower() == se_email.lower():
            return w
    return None
