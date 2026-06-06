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


@router.get("/bu", dependencies=[Depends(require_role("bu_head", "admin", "manager", "ceo"))])
def bu_dashboard(db: Session = Depends(get_db)):
    """Aggregated deal-anatomy view for the BU head. Same insights pipeline,
    different lens — wins, buying committee, velocity, incumbent displacement,
    discovery source, and aha patterns. All panels surface raw data for export."""

    calls = (db.query(Call)
             .filter(Call.insights.has())
             .order_by(Call.created_at.desc())
             .all())
    insights_blob = [(c, c.insights.data or {}) for c in calls if c.insights]

    # ─── Wins (deal anatomy cards) ─────────────────────────────────
    wins_recent = []
    for c in calls:
        if c.deal_outcome == "won" and c.closed_date:
            ins = (c.insights.data if c.insights else {}) or {}
            committee = ins.get("buying_committee") or []
            incumbent = ins.get("incumbent") or {}
            source = c.discovery_source_override or (ins.get("discovery_source") or {}).get("source")
            aha_override = c.aha_moment_override
            aha_candidates = ins.get("aha_candidates") or []
            aha = aha_override or (aha_candidates[0].get("quote") if aha_candidates else None)
            # Velocity
            demo_to_close = None
            close_to_live = None
            if c.call_date and c.closed_date:
                demo_to_close = max(0, (c.closed_date - c.call_date).days)
            if c.closed_date and c.go_live_date:
                close_to_live = max(0, (c.go_live_date - c.closed_date).days)
            wins_recent.append({
                "call_id": c.call_id,
                "prospect": c.prospect_company,
                "use_case": (ins.get("use_case") or {}).get("summary"),
                "product": (ins.get("product") or {}).get("primary"),
                "se_name": c.se_name,
                "ae_name": c.ae_name,
                "closed_date": c.closed_date.isoformat(),
                "go_live_date": c.go_live_date.isoformat() if c.go_live_date else None,
                "demo_to_close_days": demo_to_close,
                "close_to_go_live_days": close_to_live,
                "buying_committee": committee,
                "primary_users": ins.get("primary_users") or [],
                "incumbent": incumbent,
                "discovery_source": source,
                "aha": aha,
                "deal_value": c.deal_value,
                "deal_currency": c.deal_currency or "USD",
                "deal_stage": c.deal_stage,
                "crm_deal_url": c.crm_deal_url,
            })
    # Sort by close date desc, limit 20
    wins_recent.sort(key=lambda w: w["closed_date"], reverse=True)
    wins_recent = wins_recent[:20]

    # ─── Buying committee composition patterns ─────────────────────
    role_stats: dict[str, dict] = {}
    titles_by_role: dict[str, Counter] = defaultdict(Counter)
    score_with_role: dict[str, list[float]] = defaultdict(list)
    score_without_role: dict[str, list[float]] = defaultdict(list)
    KNOWN_ROLES = ("champion", "decision_maker", "primary_user", "secondary_user",
                   "it_security", "procurement", "finance", "exec_sponsor", "influencer")
    for c, ins in insights_blob:
        committee = ins.get("buying_committee") or []
        roles_on_call = {m.get("role") for m in committee if m.get("role")}
        weighted = c.scorecard.weighted_final if c.scorecard else None
        for role in KNOWN_ROLES:
            present = role in roles_on_call
            if weighted is not None:
                (score_with_role if present else score_without_role)[role].append(weighted)
            for m in committee:
                if m.get("role") == role and m.get("title"):
                    titles_by_role[role][m["title"]] += 1
        for m in committee:
            r = m.get("role")
            if r in KNOWN_ROLES:
                role_stats.setdefault(r, {"calls_present": set()})
                role_stats[r]["calls_present"].add(c.id)
    total_calls = len(insights_blob) or 1
    committee_table = []
    for role in KNOWN_ROLES:
        present_count = len(role_stats.get(role, {}).get("calls_present", set()))
        top_titles = [t for t, _ in titles_by_role[role].most_common(4)]
        committee_table.append({
            "role": role,
            "calls_present": present_count,
            "pct_calls": round(present_count / total_calls, 3),
            "top_titles": top_titles,
            "avg_score_when_present": round(mean(score_with_role[role]), 2) if score_with_role[role] else None,
            "avg_score_when_absent": round(mean(score_without_role[role]), 2) if score_without_role[role] else None,
        })
    committee_table.sort(key=lambda r: r["calls_present"], reverse=True)

    # ─── Deal velocity (cohorts) ───────────────────────────────────
    velocities = []
    for c in calls:
        if c.deal_outcome == "won" and c.call_date and c.closed_date:
            d2c = max(0, (c.closed_date - c.call_date).days)
            c2l = (c.go_live_date - c.closed_date).days if c.go_live_date else None
            ins = (c.insights.data if c.insights else {}) or {}
            velocities.append({
                "demo_to_close": d2c,
                "close_to_go_live": c2l,
                "product": (ins.get("product") or {}).get("primary"),
                "maturity": (ins.get("maturity") or {}).get("category"),
                "call_type": c.call_type,
                "source": c.discovery_source_override or (ins.get("discovery_source") or {}).get("source"),
            })

    def _stats(values: list[int]):
        if not values:
            return {"median": None, "p90": None, "n": 0}
        s = sorted(values)
        return {
            "median": s[len(s) // 2],
            "p90": s[min(len(s) - 1, int(len(s) * 0.9))],
            "n": len(s),
        }

    def _cohort(name: str, predicate) -> dict:
        d2c = [v["demo_to_close"] for v in velocities if predicate(v) and v["demo_to_close"] is not None]
        c2l = [v["close_to_go_live"] for v in velocities if predicate(v) and v["close_to_go_live"] is not None]
        return {"cohort": name, "n": len(d2c),
                "demo_to_close": _stats(d2c),
                "close_to_go_live": _stats(c2l)}

    velocity_cohorts = [
        _cohort("All closed-won", lambda v: True),
        _cohort("Product · SurveySparrow", lambda v: v["product"] == "SurveySparrow"),
        _cohort("Product · ThriveSparrow", lambda v: v["product"] == "ThriveSparrow"),
        _cohort("Product · SparrowDesk", lambda v: v["product"] == "SparrowDesk"),
        _cohort("With POC", lambda v: v["call_type"] == "poc"),
        _cohort("Source · Referral", lambda v: v["source"] == "referral"),
        _cohort("Source · AE outbound", lambda v: v["source"] == "ae_outbound"),
        _cohort("Source · Inbound", lambda v: v["source"] in ("organic_search", "g2_comparison", "plg_upgrade")),
        _cohort("Maturity · High Maturity", lambda v: (v["maturity"] or "").lower().startswith("high")),
    ]

    # ─── Incumbent displacement ────────────────────────────────────
    incumbent_stats: dict[str, dict] = {}
    for c, ins in insights_blob:
        inc = ins.get("incumbent") or {}
        tool = (inc.get("tool") or "").strip()
        if not tool:
            continue
        if tool not in incumbent_stats:
            incumbent_stats[tool] = {
                "tool": tool, "calls": 0, "products": Counter(),
                "switching_reasons": Counter(),
                "years_using_samples": [],
            }
        s = incumbent_stats[tool]
        s["calls"] += 1
        product = (ins.get("product") or {}).get("primary")
        if product:
            s["products"][product] += 1
        if inc.get("switching_reason"):
            s["switching_reasons"][inc["switching_reason"][:80]] += 1
        if inc.get("years_using"):
            s["years_using_samples"].append(str(inc["years_using"]))
    incumbent_table = sorted([
        {
            "tool": s["tool"], "calls": s["calls"],
            "products": list(s["products"].keys()),
            "top_switching_reason": s["switching_reasons"].most_common(1)[0][0] if s["switching_reasons"] else None,
            "years_using_samples": s["years_using_samples"][:5],
        }
        for s in incumbent_stats.values()
    ], key=lambda x: x["calls"], reverse=True)

    # ─── Discovery source breakdown ───────────────────────────────
    source_stats: dict[str, dict] = {}
    for c, ins in insights_blob:
        source = c.discovery_source_override or (ins.get("discovery_source") or {}).get("source") or "unknown"
        if source not in source_stats:
            source_stats[source] = {"source": source, "calls": 0, "wins": 0,
                                    "scores": [], "won_values": []}
        s = source_stats[source]
        s["calls"] += 1
        if c.deal_outcome == "won":
            s["wins"] += 1
            if c.deal_value:
                s["won_values"].append(c.deal_value)
        if c.scorecard:
            s["scores"].append(c.scorecard.weighted_final)
    source_table = sorted([
        {
            "source": s["source"],
            "calls": s["calls"],
            "pct_of_calls": round(s["calls"] / total_calls, 3),
            "wins": s["wins"],
            "win_rate": round(s["wins"] / s["calls"], 3) if s["calls"] else 0,
            "avg_score": round(mean(s["scores"]), 2) if s["scores"] else None,
            "total_won_value": round(sum(s["won_values"]), 2) if s["won_values"] else 0,
            "avg_deal_size": round(mean(s["won_values"]), 2) if s["won_values"] else None,
        }
        for s in source_stats.values()
    ], key=lambda x: x["calls"], reverse=True)

    # ─── Aha moments — what's actually closing ────────────────────
    aha_categories = Counter()
    aha_examples: dict[str, list[dict]] = defaultdict(list)
    for c, ins in insights_blob:
        if c.deal_outcome != "won":
            continue
        for cand in (ins.get("aha_candidates") or []):
            cat = cand.get("category") or "other"
            aha_categories[cat] += 1
            if len(aha_examples[cat]) < 3:
                aha_examples[cat].append({
                    "quote": cand.get("quote"),
                    "moment": cand.get("moment"),
                    "prospect": c.prospect_company,
                })
    aha_total = sum(aha_categories.values()) or 1
    aha_table = [
        {
            "category": cat,
            "wins_citing": count,
            "pct_of_wins": round(count / aha_total, 3),
            "examples": aha_examples[cat],
        }
        for cat, count in aha_categories.most_common()
    ]

    # ─── Pipeline ($) by stage ────────────────────────────────────
    pipeline_stages: dict[str, dict] = {}
    won_total_value = 0.0
    won_total_count = 0
    open_pipeline_value = 0.0
    open_pipeline_count = 0
    for c in calls:
        stage = c.deal_stage or "unstaged"
        value = c.deal_value or 0
        if stage not in pipeline_stages:
            pipeline_stages[stage] = {"stage": stage, "count": 0, "total_value": 0.0,
                                       "has_value": 0, "currency": c.deal_currency or "USD"}
        s = pipeline_stages[stage]
        s["count"] += 1
        if value:
            s["total_value"] += value
            s["has_value"] += 1
        # Roll-up counters
        if c.deal_outcome == "won" and value:
            won_total_value += value
            won_total_count += 1
        if c.deal_outcome in (None, "open"):
            open_pipeline_value += value or 0
            if c.deal_outcome == "open":
                open_pipeline_count += 1
    STAGE_ORDER = ["prospecting", "qualified", "demo_scheduled", "demo_completed",
                   "proposal", "negotiation", "verbal_commit", "closed_won",
                   "closed_lost", "no_decision", "unstaged"]
    pipeline_table = []
    for stage in STAGE_ORDER:
        if stage in pipeline_stages:
            s = pipeline_stages[stage]
            pipeline_table.append({
                "stage": s["stage"],
                "count": s["count"],
                "deals_with_value": s["has_value"],
                "total_value": round(s["total_value"], 2),
            })

    # ─── Headlines ────────────────────────────────────────────────
    loss_signals = 0
    blocker_features = 0
    at_risk_value = 0.0   # open-stage deal value where loss-risk signals fired
    for c, ins in insights_blob:
        lr = ins.get("loss_risk_signals") or {}
        had_risk = False
        for k in ("no_reference_customer", "support_quality_concern", "pricing_concern", "product_gap"):
            if (lr.get(k) or {}).get("present"):
                loss_signals += 1
                had_risk = True
        if had_risk and c.deal_outcome != "won" and c.deal_value:
            at_risk_value += c.deal_value
        for fr in (ins.get("feature_requests") or []):
            if fr.get("urgency") == "blocker":
                blocker_features += 1

    avg_score = round(mean(c.scorecard.weighted_final for c, _ in insights_blob if c.scorecard), 2) if insights_blob else 0
    high_maturity = sum(1 for c, ins in insights_blob
                        if (ins.get("maturity") or {}).get("category", "").lower().startswith("high"))

    return {
        "headlines": {
            "calls_analyzed": total_calls,
            "loss_risk_signals": loss_signals,
            "blocker_feature_mentions": blocker_features,
            "high_maturity_prospects": high_maturity,
            "team_avg_score": avg_score,
            "wins_recent_count": len(wins_recent),
            # $-weighted
            "won_total_value": round(won_total_value, 2),
            "won_total_count": won_total_count,
            "open_pipeline_value": round(open_pipeline_value, 2),
            "at_risk_value": round(at_risk_value, 2),
        },
        "pipeline_by_stage": pipeline_table,
        "wins": wins_recent,
        "buying_committee": committee_table,
        "deal_velocity": velocity_cohorts,
        "incumbent_displacement": incumbent_table,
        "discovery_source": source_table,
        "aha_patterns": aha_table,
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
