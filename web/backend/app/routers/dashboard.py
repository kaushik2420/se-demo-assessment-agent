"""Dashboard payload endpoints — SE, Manager, CEO (real DB)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.models import Call, CoachingAction, Insights, Scorecard, User
from app.services.dotm import compute_dotm, is_winner


router = APIRouter()


@router.get("/se")
def se_dashboard(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    se = db.query(User).filter(User.email == user.email).first()
    if not se:
        return {"empty": True}

    calls = (db.query(Call).filter(Call.se_id == se.id)
               .order_by(Call.created_at.desc()).limit(200).all())

    # Compute headline metrics
    scored = [c for c in calls if c.scorecard]
    current_score = round(mean(c.scorecard.weighted_final for c in scored), 2) if scored else 0.0

    # Trend by month (last 6 months)
    by_month: dict[str, list[float]] = defaultdict(list)
    for c in scored:
        key = (c.call_date or c.created_at).strftime("%Y-%m")
        by_month[key].append(c.scorecard.weighted_final)
    months_sorted = sorted(by_month.keys())[-6:]
    trend = [{"month": m, "score": round(mean(by_month[m]), 2), "industry_median": 3.4}
             for m in months_sorted]

    # Coaching action this month
    this_month = datetime.now(timezone.utc).strftime("%Y-%m")
    action = (db.query(CoachingAction)
                .filter(CoachingAction.se_id == se.id, CoachingAction.month == this_month)
                .order_by(CoachingAction.created_at.desc()).first())

    pct = scored[0].scorecard.industry_percentile if scored else 50

    # Demo of the Month — is this SE in the top-2?
    dotm_winner = is_winner(db, se.email)

    return {
        "se": {"email": se.email, "name": se.name},
        "dotm_winner": dotm_winner,   # null if not in top-2 this month
        "headline": {
            "current_score": current_score,
            "industry_percentile": pct,
            "calls_this_month": len([c for c in scored
                                     if (c.call_date or c.created_at).strftime("%Y-%m") == this_month]),
            "score_delta_mom": round((trend[-1]["score"] - trend[-2]["score"]) if len(trend) >= 2 else 0, 2),
        },
        "trend_6mo": trend,
        "coaching_action": ({
            "text": action.action_text, "set_by": action.set_by,
            "status": action.status, "month": action.month,
        } if action else None),
        "recent_calls": [_call_summary(c) for c in calls],   # paginate client-side
    }


def _call_summary(c: Call) -> dict:
    """Shared shape for both SE + Manager recent-call lists.

    Reads the NEW `maturity` + `product` insights keys but falls back to the
    OLD `cx_maturity` shape for calls analyzed under the previous prompt.
    """
    ins = (c.insights.data if c.insights else {}) or {}
    maturity_block = ins.get("maturity") or {}
    maturity_category = maturity_block.get("category") or (ins.get("cx_maturity", {}) or {}).get("category")
    maturity_scope = maturity_block.get("scope") or ("CX" if (ins.get("cx_maturity") or {}).get("category") else None)
    product = (ins.get("product") or {}).get("primary")

    return {
        "call_id": c.call_id,
        "prospect": c.prospect_company,
        "type": c.call_type,
        "score": c.scorecard.weighted_final if c.scorecard else None,
        "maturity": maturity_category,        # new key
        "maturity_scope": maturity_scope,     # "CX" | "EX"
        "cx_maturity": maturity_category,     # legacy alias so old frontend keeps working
        "product": product,
        "duration_min": c.duration_min,
        "date": (c.call_date or c.created_at).strftime("%Y-%m-%d"),
    }


@router.get("/manager", dependencies=[Depends(require_role("manager", "admin"))])
def manager_dashboard(db: Session = Depends(get_db)):
    dotm = compute_dotm(db)
    # Anyone who has actually run calls belongs on the leaderboard, regardless
    # of role. Managers and admins frequently run their own demos and should
    # be benchmarked alongside individual contributors. We pull all users who
    # have at least one scored call linked to their se_id (avoids hard-coding
    # which roles "do calls" — works for ceo/observer/future roles too).
    user_ids_with_calls = {
        row[0] for row in db.query(Call.se_id).filter(Call.scorecard.has(), Call.se_id.isnot(None)).distinct().all()
    }
    ses = db.query(User).filter(User.id.in_(user_ids_with_calls)).all() if user_ids_with_calls else []
    leaderboard = []
    for se in ses:
        calls = [c for c in se.calls if c.scorecard]
        if not calls:
            continue
        scores = [c.scorecard.weighted_final for c in calls]
        avg = round(mean(scores), 2)
        # crude trend: first half vs second half
        half = len(scores) // 2 or 1
        early, late = scores[:half], scores[half:] or scores
        trend = "up" if mean(late) > mean(early) + 0.1 else ("down" if mean(late) < mean(early) - 0.1 else "flat")
        # top gap
        crit_avgs: dict[str, list[float]] = defaultdict(list)
        for c in calls:
            for k, v in c.scorecard.per_criterion.items():
                crit_avgs[k].append(v)
        top_gap = min(crit_avgs.items(), key=lambda kv: mean(kv[1]))[0] if crit_avgs else "—"
        leaderboard.append({
            "se": se.name, "email": se.email, "calls": len(calls), "score": avg,
            "percentile": calls[0].scorecard.industry_percentile, "trend": trend, "top_gap": top_gap,
        })
    leaderboard.sort(key=lambda x: x["score"], reverse=True)

    all_calls = db.query(Call).filter(Call.scorecard.has()).all()
    all_insights = [c.insights.data for c in all_calls if c.insights]
    feature_selling_pct = (sum(1 for i in all_insights
                               if i.get("se_selling_style", {}).get("verdict") == "feature_seller")
                           / max(len(all_insights), 1))
    return {
        "demo_of_the_month": dotm,
        "team_metrics": {
            "avg_score": round(mean(c.scorecard.weighted_final for c in all_calls), 2) if all_calls else 0,
            "calls": len(all_calls),
            "feature_selling_pct": round(feature_selling_pct, 2),
            "ae_quality_flags": sum(1 for i in all_insights
                                    if i.get("ae_behavior", {}).get("ae_quality_flag")),
        },
        "leaderboard": leaderboard,
    }


@router.get("/ceo", dependencies=[Depends(require_role("ceo", "admin", "manager"))])
def ceo_dashboard(db: Session = Depends(get_db)):
    """Aggregate of this month's calls into product/process gaps + AE flags."""
    this_month = datetime.now(timezone.utc).strftime("%Y-%m")
    calls = db.query(Call).filter(Call.scorecard.has(), Call.insights.has()).all()
    insights = [c.insights.data for c in calls]

    # Aggregate competitors, feature requests, loss-risk signals
    competitors = Counter()
    for i in insights:
        for c in i.get("competitors_mentioned", []) or []:
            competitors[c.get("name", "?")] += 1

    ae_interruption = [i["ae_behavior"]["interruption_count"] for i in insights
                       if "ae_behavior" in i and "interruption_count" in i["ae_behavior"]]

    feature_requests: list[dict] = []
    for i in insights:
        feature_requests.extend(i.get("feature_requests", []) or [])

    # Top blockers = most-cited blocker-urgency features
    blocker_features = Counter()
    for fr in feature_requests:
        if fr.get("urgency") == "blocker":
            blocker_features[fr.get("feature", "?")] += 1

    return {
        "month": this_month,
        "headline": f"{len(calls)} calls analyzed. "
                    f"{int(100*sum(1 for i in insights if i.get('se_selling_style',{}).get('verdict')=='feature_seller')/max(len(insights),1))}% "
                    f"of demos slipped into feature-selling.",
        "month_metrics": {
            "calls": len(calls),
            "ae_interruption_avg_per_call": round(mean(ae_interruption), 1) if ae_interruption else 0,
            "feature_selling_pct": round(sum(1 for i in insights
                                             if i.get("se_selling_style",{}).get("verdict")=="feature_seller")
                                         / max(len(insights), 1), 2),
        },
        "top_product_blockers": [{"feature": f, "deal_count": n}
                                 for f, n in blocker_features.most_common(5)],
        "most_mentioned_competitors": [{"name": n, "mentions": m}
                                       for n, m in competitors.most_common(5)],
        "ae_quality_risks": [
            {"ae_name": i.get("ae_name"),
             "interruption_count": i["ae_behavior"]["interruption_count"],
             "examples": i["ae_behavior"].get("barge_in_examples", [])}
            for i in insights if i.get("ae_behavior", {}).get("ae_quality_flag")
        ],
    }
