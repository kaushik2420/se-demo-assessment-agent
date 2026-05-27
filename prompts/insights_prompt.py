"""
Prompt for extracting the 9 deal-intelligence signals kaushik asked for, from a
single demo transcript. Output is JSON so it can be aggregated into monthly
dashboards and the CEO executive summary.
"""

VERSION = "2026-05-v1"

SYSTEM = """You are a deal-intelligence analyst. Read a sales-demo transcript and extract
structured signals about the prospect's needs, the competitive context, and the
behavior of the SurveySparrow team on the call. You are concise, evidence-based,
and never invent details. If a signal is absent, return null or an empty list
rather than guessing.
"""

USER_TEMPLATE = """## CX MATURITY FRAMEWORK (SurveySparrow internal)

You will classify the prospect's use case along 8 dimensions, each scored 0-3:

{maturity_dimensions_json}

Bands: 0-6 Form/Basic · 7-12 Low Maturity CX · 13-18 Potential High Maturity CX · 19-24 High Maturity CX.

## CALL METADATA

- SE: {se_name}
- AE: {ae_name}
- Prospect: {prospect_company} ({prospect_industry})

## TRANSCRIPT

{transcript}

## YOUR TASK

Return a JSON object with this exact shape:

{{
  "use_case": {{
    "summary": "1-2 sentence description of what the prospect wants to do",
    "explicit_quotes": ["...", "..."]
  }},
  "cx_maturity": {{
    "scorecard": {{ "<dimension>": 0-3, ... for all 8 dimensions }},
    "category": "Form / Basic | Low Maturity CX | Potential High Maturity CX | High Maturity CX",
    "rationale": "1-2 sentences explaining the classification"
  }},
  "feature_requests": [
    {{ "feature": "...", "urgency": "blocker | nice-to-have | mentioned", "quote": "..." }}
  ],
  "competitors_mentioned": [
    {{ "name": "...", "context": "evaluated | currently using | dismissed", "quote": "..." }}
  ],
  "trial_issues": [
    {{ "issue": "...", "severity": "low | medium | high", "quote": "..." }}
  ],
  "loss_risk_signals": {{
    "no_reference_customer": {{ "present": true|false, "quote": "..." }},
    "support_quality_concern": {{ "present": true|false, "quote": "..." }},
    "pricing_concern": {{ "present": true|false, "quote": "..." }},
    "product_gap": {{ "present": true|false, "quote": "..." }},
    "other": ["..."]
  }},
  "ae_behavior": {{
    "interruption_count": <int — times AE cut off SE mid-sentence>,
    "barge_in_examples": ["short paraphrase of each interruption"],
    "interruption_impact": "none | minor | derailed_value_delivery",
    "ae_quality_flag": true|false
  }},
  "se_selling_style": {{
    "feature_selling_share": 0.0-1.0,
    "value_selling_share":   0.0-1.0,
    "verdict": "feature_seller | balanced | value_seller",
    "evidence": "1 quote that proves the verdict"
  }},
  "prospect_engagement": {{
    "sentiment": "negative | neutral | curious | enthusiastic",
    "buying_signals": ["..."],
    "objections": ["..."]
  }}
}}

Return ONLY the JSON. No prose before or after.
"""
