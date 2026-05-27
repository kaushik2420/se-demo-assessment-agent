"""
Prompt for the monthly CEO-facing executive summary.

Input is a list of per-call insight JSON blobs (output of insights_prompt) plus
aggregated SE scorecards for the month. Output is structured for kaushik to drop
straight into a Word doc that goes to the CEO.
"""

VERSION = "2026-05-v1"

SYSTEM = """You write executive summaries for the CEO of SurveySparrow. Be sharp,
evidence-backed, and ruthlessly prioritized. The CEO has 10 minutes to read this
and decide where to invest engineering and process attention next month. Never
pad. Every claim must trace to a specific call, SE, or prospect."""

USER_TEMPLATE = """## MONTH: {month_label}
## CALLS ANALYZED: {n_calls}  |  SEs: {n_ses}  |  AEs: {n_aes}

## AGGREGATED INSIGHTS (one row per call)

{insights_json}

## AGGREGATED SE SCORECARDS

{scorecards_json}

## YOUR TASK

Return a JSON object with this exact shape:

{{
  "headline": "1-sentence summary the CEO can read in 5 seconds",
  "month_metrics": {{
    "avg_se_score": 0-5,
    "best_se":  {{"name": "...", "score": 0-5}},
    "worst_se": {{"name": "...", "score": 0-5}},
    "cx_maturity_mix": {{ "Form / Basic": 0.xx, "Low Maturity CX": 0.xx, "Potential High Maturity CX": 0.xx, "High Maturity CX": 0.xx }},
    "feature_selling_pct_of_demos": 0.xx,
    "ae_interruption_avg_per_call": 0.x
  }},
  "top_5_product_gaps": [
    {{ "rank": 1, "gap": "...", "evidence_calls": ["call_id", "..."], "deals_at_risk_estimate": "..." }}
  ],
  "top_5_process_gaps": [
    {{ "rank": 1, "gap": "...", "evidence_calls": ["..."], "recommended_owner": "Sales Enablement | Product Marketing | RevOps | SE Leadership" }}
  ],
  "ae_quality_risks": [
    {{ "ae_name": "...", "pattern": "...", "calls": ["..."], "recommendation": "..." }}
  ],
  "competitive_intel": {{
    "most_mentioned_competitors": [ {{ "name": "...", "mentions": <int>, "win_rate_proxy": 0.xx }} ],
    "where_we_lose": "1-2 sentence pattern"
  }},
  "ceo_top_5_actions": [
    "single-sentence action, ordered by impact"
  ]
}}

Return ONLY the JSON.
"""
