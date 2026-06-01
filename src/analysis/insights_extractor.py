"""
Extract the 9 deal-intelligence signals from a transcript.
"""

from __future__ import annotations

import json
from typing import Optional

from prompts import insights_prompt
from src.analysis.llm_client import LLMClient
from src.analysis.scoring_engine import CallContext
from src.utils.cx_maturity import MATURITY_DIMENSIONS, DIMENSION_ANCHORS, classify_from_scorecard


def _maturity_dims_for_prompt() -> str:
    return json.dumps(
        [
            {"dimension": d, "anchors": DIMENSION_ANCHORS[d]}
            for d in MATURITY_DIMENSIONS
        ],
        indent=2,
    )


def _mock_insights(ctx: CallContext) -> dict:
    # Slight variation per SE
    high_maturity = "journey" in ctx.stated_use_case.lower() or "retention" in ctx.stated_use_case.lower()
    scorecard = (
        {d: 2 for d in MATURITY_DIMENSIONS} if high_maturity
        else {d: 1 for d in MATURITY_DIMENSIONS}
    )
    if high_maturity:
        scorecard["Business objective"] = 3
        scorecard["Workflow / action"] = 3
    category, _ = classify_from_scorecard(scorecard)

    return {
        "product": {
            "primary": "SurveySparrow",
            "secondary": [],
            "evidence": "Discussion centered on NPS, customer feedback, journey-based surveys.",
        },
        "use_case": {
            "summary": (
                "Prospect wants relationship NPS across customer base with renewal-risk "
                "alerts to CSMs and quarterly exec review."
            ) if high_maturity else (
                "Prospect wants a one-off post-event satisfaction form with CSV export."
            ),
            "explicit_quotes": [
                f"We need to know which accounts are at risk before renewal" if high_maturity
                else "We just need a form for our annual user conference",
            ],
        },
        "maturity": {
            "scope": "CX",
            "scorecard": scorecard,
            "category": category,
            "rationale": (
                "Multi-touchpoint program with CRM-linked workflow ownership."
                if high_maturity
                else "Single touchpoint, no segmentation, no action loop discussed."
            ),
        },
        "features_discussed": [
            {"feature": "Relationship NPS with longitudinal tracking",
             "context": "demoed", "quote": "SE walked through quarterly NPS pulse setup"},
            {"feature": "Conditional logic for branching surveys",
             "context": "asked_about", "quote": "Can we route to different questions by ARR tier?"},
        ],
        "feature_requests": [
            {"feature": "Salesforce two-way sync for renewal-stage variables",
             "urgency": "blocker", "quote": "If it doesn't push back to SFDC opportunity, it's a no-go"},
            {"feature": "Custom NPS-by-segment dashboard widget — currently can only slice by team",
             "urgency": "nice-to-have", "quote": "Would be nice to slice by ARR tier — SE said not available today"},
        ],
        "competitors_mentioned": [
            {"name": "Qualtrics", "context": "evaluated", "quote": "We're comparing you with Qualtrics on price"},
            {"name": "Medallia", "context": "dismissed", "quote": "Medallia is overkill for us"},
        ],
        "trial_issues": [
            {"issue": "Trial workspace did not include sample CRM-variable data",
             "severity": "medium",
             "quote": "We couldn't really test the segmentation in trial"},
        ],
        "loss_risk_signals": {
            "no_reference_customer": {"present": True,
                "quote": "Do you have anyone in fintech I can talk to?"},
            "support_quality_concern": {"present": False, "quote": ""},
            "pricing_concern": {"present": True,
                "quote": "Qualtrics gave us a much lower price on the same volume"},
            "product_gap": {"present": True,
                "quote": "We need real-time Slack alerts on detractors"},
            "other": ["Procurement requires SOC2 Type II report up front"],
        },
        "ae_behavior": {
            "interruption_count": 3,
            "barge_in_examples": [
                "AE cut SE off mid-demo of dashboards to pivot to pricing",
                "AE interrupted SE's discovery question to talk about the deal timeline",
                "AE talked over SE during competitor objection handling",
            ],
            "interruption_impact": "derailed_value_delivery",
            "ae_quality_flag": True,
        },
        "se_selling_style": {
            "feature_selling_share": 0.35,
            "value_selling_share": 0.65,
            "verdict": "balanced",
            "evidence": "SE tied dashboard demo to 'fewer surprise churns at renewal' — value framing",
        },
        "prospect_engagement": {
            "sentiment": "curious",
            "buying_signals": [
                "Asked about implementation timeline",
                "Wanted to loop in CFO for next call",
            ],
            "objections": [
                "Price vs Qualtrics",
                "Concerns about migration from current tool",
            ],
        },
    }


def extract_insights(ctx: CallContext, llm: Optional[LLMClient] = None) -> dict:
    llm = llm or LLMClient()
    user = insights_prompt.USER_TEMPLATE.format(
        maturity_dimensions_json=_maturity_dims_for_prompt(),
        se_name=ctx.se_name,
        ae_name=ctx.ae_name,
        prospect_company=ctx.prospect_company,
        prospect_industry=ctx.prospect_industry,
        transcript=ctx.transcript,
    )
    raw = llm.chat_json(insights_prompt.SYSTEM, user, mock_response=_mock_insights(ctx))
    raw["call_id"] = ctx.call_id
    raw["se_name"] = ctx.se_name
    raw["ae_name"] = ctx.ae_name
    raw["prompt_version"] = insights_prompt.VERSION
    return raw
