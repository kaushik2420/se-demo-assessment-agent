"""
Prompt for extracting the 9 deal-intelligence signals kaushik asked for, from a
single demo transcript. Output is JSON so it can be aggregated into monthly
dashboards and the CEO executive summary.
"""

VERSION = "2026-06-v2"

SYSTEM = """You are a deal-intelligence analyst. Read a sales-demo transcript and extract
structured signals about the prospect's needs, the competitive context, and the
behavior of the SurveySparrow team on the call. You are concise, evidence-based,
and never invent details. If a signal is absent, return null or an empty list
rather than guessing.

You know SurveySparrow's product lineup:
- SurveySparrow → CX/feedback platform (NPS, CSAT, CES, customer feedback, surveys, journeys)
- ThriveSparrow → EX platform (employee engagement, eNPS, 360 reviews, recognition, pulse surveys)
- SparrowDesk → Helpdesk / support (ticketing, CSAT-on-tickets, knowledge base)
Identify which product the conversation is primarily about. If the prospect
spans multiple, pick the primary one; mention the others in the notes field.
"""

USER_TEMPLATE = """## MATURITY FRAMEWORK

You will classify the prospect's program maturity along 8 dimensions, each scored 0-3:

{maturity_dimensions_json}

Bands: 0-6 Form / Basic · 7-12 Low Maturity · 13-18 Potential High Maturity · 19-24 High Maturity.

Decide the SCOPE of the maturity framework based on the product the prospect is
buying:
- "CX" — for SurveySparrow conversations (customer feedback / NPS / journeys)
- "EX" — for ThriveSparrow conversations (employee engagement / eNPS / 360s)
- "CX" — for SparrowDesk conversations (treat support CSAT as CX)

## CALL METADATA

- SE: {se_name}
- AE: {ae_name}
- Prospect: {prospect_company} ({prospect_industry})

## TRANSCRIPT

{transcript}

## YOUR TASK

Return a JSON object with this exact shape:

{{
  "product": {{
    "primary": "SurveySparrow | ThriveSparrow | SparrowDesk | Unknown",
    "secondary": ["..."],
    "evidence": "1-2 quotes that grounded the product determination"
  }},
  "use_case": {{
    "summary": "1-2 sentence description of what the prospect wants to do",
    "explicit_quotes": ["...", "..."]
  }},
  "maturity": {{
    "scope": "CX | EX",
    "scorecard": {{ "<dimension>": 0-3, ... for all 8 dimensions }},
    "category": "Form / Basic | Low Maturity | Potential High Maturity | High Maturity",
    "rationale": "1-2 sentences explaining the classification"
  }},
  "features_discussed": [
    {{ "feature": "an existing capability the prospect explored, asked about, or that the SE demoed",
       "context": "demoed | mentioned | asked_about", "quote": "..." }}
  ],
  "feature_requests": [
    {{ "feature": "ONLY include if prospect explicitly said it is missing, asked for it to be added, or it was flagged as a gap",
       "urgency": "blocker | nice-to-have | mentioned",
       "quote": "the exact phrasing showing it's a NEW ask or a gap" }}
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

CRITICAL distinction (re-read before answering):
- `features_discussed` = capabilities ALREADY in our product that came up
  (the SE showed them, or the prospect asked "do you support X" and we do).
- `feature_requests` = things we DON'T have that the prospect wants. Only put
  an item here if the transcript shows the prospect asked for something we
  lack, OR our team admitted it's not available, OR it was explicitly framed
  as a gap / enhancement / roadmap item. When in doubt, put it in
  `features_discussed`, not `feature_requests`.

Return ONLY the JSON. No prose before or after.
"""
