"""
Aggregate a month of per-call insights + scorecards into the CEO executive summary.
"""

from __future__ import annotations

import json
from collections import Counter
from statistics import mean
from typing import List, Optional

from prompts import exec_summary_prompt
from src.analysis.llm_client import LLMClient


def _mock_exec_summary(month_label: str, insights: list, scorecards: list) -> dict:
    se_scores = {}
    for s in scorecards:
        se_scores.setdefault(s["se_name"], []).append(s["weighted_final"])
    se_avg = {n: round(mean(v), 2) for n, v in se_scores.items()}
    sorted_se = sorted(se_avg.items(), key=lambda x: x[1], reverse=True)
    best = sorted_se[0] if sorted_se else ("—", 0)
    worst = sorted_se[-1] if sorted_se else ("—", 0)

    cx_mix_counter = Counter(i["cx_maturity"]["category"] for i in insights)
    total = sum(cx_mix_counter.values()) or 1
    cx_mix = {k: round(v / total, 2) for k, v in cx_mix_counter.items()}

    feature_selling = sum(
        1 for i in insights if i["se_selling_style"]["verdict"] == "feature_seller"
    ) / max(len(insights), 1)

    ae_interrupt_avg = round(
        mean(i["ae_behavior"]["interruption_count"] for i in insights) if insights else 0, 1
    )

    competitor_counter = Counter()
    for i in insights:
        for c in i["competitors_mentioned"]:
            competitor_counter[c["name"]] += 1
    top_comps = [
        {"name": n, "mentions": m, "win_rate_proxy": 0.42}
        for n, m in competitor_counter.most_common(3)
    ]

    return {
        "headline": (
            f"{best[0]} led the team at {best[1]}/5; "
            f"35% of demos slipped into feature-selling and AEs averaged "
            f"{ae_interrupt_avg} interruptions per call."
        ),
        "month_metrics": {
            "avg_se_score": round(mean(se_avg.values()), 2) if se_avg else 0,
            "best_se":  {"name": best[0], "score": best[1]},
            "worst_se": {"name": worst[0], "score": worst[1]},
            "cx_maturity_mix": cx_mix,
            "feature_selling_pct_of_demos": round(feature_selling, 2),
            "ae_interruption_avg_per_call": ae_interrupt_avg,
        },
        "top_5_product_gaps": [
            {"rank": 1, "gap": "Real-time Slack alerts on detractor responses",
             "evidence_calls": [i["call_id"] for i in insights[:2]],
             "deals_at_risk_estimate": "~$240K ARR across 3 deals"},
            {"rank": 2, "gap": "Bi-directional Salesforce sync for renewal-stage variables",
             "evidence_calls": [insights[0]["call_id"]] if insights else [],
             "deals_at_risk_estimate": "~$180K ARR"},
            {"rank": 3, "gap": "Custom dashboard widgets by ARR tier / segment",
             "evidence_calls": [], "deals_at_risk_estimate": "~$95K ARR"},
            {"rank": 4, "gap": "Sample CRM-variable data inside trial workspaces",
             "evidence_calls": [], "deals_at_risk_estimate": "Trial → demo conversion drag"},
            {"rank": 5, "gap": "Public industry reference customers (fintech, healthcare)",
             "evidence_calls": [], "deals_at_risk_estimate": "~$120K ARR blocked on references"},
        ],
        "top_5_process_gaps": [
            {"rank": 1, "gap": "SEs not customizing demo env with prospect logo/data",
             "evidence_calls": [], "recommended_owner": "Sales Enablement"},
            {"rank": 2, "gap": "AE interruption pattern derailing value delivery in 40%+ of calls",
             "evidence_calls": [], "recommended_owner": "Sales Leadership"},
            {"rank": 3, "gap": "No structured pre-call brief between AE and SE",
             "evidence_calls": [], "recommended_owner": "RevOps"},
            {"rank": 4, "gap": "Pricing objection handling inconsistent across SE team",
             "evidence_calls": [], "recommended_owner": "Sales Enablement"},
            {"rank": 5, "gap": "CX-maturity classification not used to qualify deals",
             "evidence_calls": [], "recommended_owner": "SE Leadership"},
        ],
        "ae_quality_risks": [
            {"ae_name": "Priya Menon", "pattern": "Interrupts SE on average 3.2x per call, primarily during value-delivery moments",
             "calls": [i["call_id"] for i in insights if i["ae_name"] == "Priya Menon"][:3],
             "recommendation": "1:1 coaching + listen-back of 2 recorded calls; pair with strongest SE for next 3 demos"},
        ],
        "competitive_intel": {
            "most_mentioned_competitors": top_comps,
            "where_we_lose": "Price-led losses to Qualtrics in mid-market; capability losses to Medallia at enterprise tier where journey orchestration is required.",
        },
        "ceo_top_5_actions": [
            "Greenlight real-time Slack-alerts feature for Q3 — blocking ~$240K ARR",
            "Direct conversation with Sales Leader on AE-interruption pattern; recurring derailment",
            "Approve fintech & healthcare reference-customer recruitment program",
            "Allocate ProdMkt cycle to publishable SOC2 Type II + segment-by-ARR dashboard widget",
            "Fund Sales Enablement to build prospect-customization templates for SE demos",
        ],
    }


def generate_exec_summary(
    month_label: str,
    insights: List[dict],
    scorecards: List[dict],
    llm: Optional[LLMClient] = None,
) -> dict:
    llm = llm or LLMClient()
    user = exec_summary_prompt.USER_TEMPLATE.format(
        month_label=month_label,
        n_calls=len(insights),
        n_ses=len({s["se_name"] for s in scorecards}),
        n_aes=len({i["ae_name"] for i in insights}),
        insights_json=json.dumps(insights, indent=2),
        scorecards_json=json.dumps(scorecards, indent=2),
    )
    return llm.chat_json(
        exec_summary_prompt.SYSTEM, user,
        mock_response=_mock_exec_summary(month_label, insights, scorecards),
    )
