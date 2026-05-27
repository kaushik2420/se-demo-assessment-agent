"""
One-off script: analyze the real BTS/Ishrath call by hand-injecting the scores
and insights into the pipeline (since this sandbox has no ANTHROPIC_API_KEY).

In production, this whole block is replaced by:
    llm = LLMClient(live=True)
    scorecard = score_call(ctx, llm=llm)
    insights  = extract_insights(ctx, llm=llm)
"""

from __future__ import annotations

import json
from pathlib import Path

from src.ingestion.manual_upload import load_transcript_file
from src.reports.se_monthly_report import build_se_report
from src.utils.benchmarks import gap_vs_industry, percentile_of
from src.utils.rubric import RUBRIC, weighted_total

ROOT = Path(__file__).parent
TRANSCRIPT = ROOT / "sample_data" / "real_bts_call_transcript.txt"
OUT_DIR = ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)


# ============================================================================
# Hand-crafted scores (acting as Claude would, based on close reading of the
# transcript). Each score includes evidence quoted from the actual call.
# ============================================================================

SCORES = {
    "Communication": {
        "Tone": {
            "score": 3.5,
            "evidence": "Warm, patient throughout. 'I've never seen anybody who is able to pick up a product like this quickly… you cut down basically a lot of my job'",
            "low_confidence": False,
        },
        "Engaging Level": {
            "score": 2.5,
            "evidence": "Mostly transactional Q&A. Heavy filler ('right?', 'you know'). One nice analogy on multilingual translation ('wear multiple hats' in Spanish)",
            "low_confidence": False,
        },
    },
    "Presentation": {
        "Relevance": {
            "score": 3.0,
            "evidence": "Generally relevant; jumped to his own client's reporting screen mid-flow without warning",
            "low_confidence": False,
        },
        "Cohesion": {
            "score": 2.5,
            "evidence": "Said 'let's set the agenda now' ~15 minutes into the call, after demo had already begun. End-of-call summary was a long uninterrupted monologue",
            "low_confidence": False,
        },
    },
    "Audience Engagement": {
        "Personalization": {
            "score": 4.0,
            "evidence": "Used names constantly, addressed each attendee individually: 'Mahima, I'm really really glad you brought it up because I missed it'",
            "low_confidence": False,
        },
        "Interactivity": {
            "score": 3.5,
            "evidence": "Frequent 'any questions Christian?' checks; but mostly reactive — Christian drove most of the agenda. One real probing question: 'How do you see this getting related to the previous system?'",
            "low_confidence": False,
        },
    },
    "Solution Skills": {
        "Customization": {
            "score": 2.0,
            "evidence": "No prep for BTS specifically — no BTS logo, no preloaded multi-client demo workspace despite knowing this is the consulting firm's central use case",
            "low_confidence": False,
        },
        "Solution-Focused": {
            "score": 1.5,
            "evidence": "Subaccount/multi-client feature (the CORE of BTS's use case) came up only at minute ~50 because Mahima asked. Ishrath admitted: 'you brought it up because I missed it'",
            "low_confidence": False,
        },
    },
    "Consultative Approach": {
        "Proactiveness": {
            "score": 2.5,
            "evidence": "Volunteered email integration and SSO options. Did NOT proactively raise multi-client architecture — the biggest architectural decision for an HR consulting firm",
            "low_confidence": False,
        },
        "Recommendations": {
            "score": 3.0,
            "evidence": "Clear close: 'I would advise you and the team to try playing around with all the settings and try replicating the similar settings that you had with a different project'",
            "low_confidence": False,
        },
        "Highlighting Key Points": {
            "score": 2.5,
            "evidence": "End-of-call recap covered ground but was a 3-minute monologue without anchoring 2-3 specific 'today we agreed X' takeaways",
            "low_confidence": False,
        },
    },
    "Touchbase on Pain Points": {
        "Addressing Pain Points": {
            "score": 1.5,
            "evidence": "No discovery questions surfaced. Never asked 'what was the biggest friction with your previous tool?' or 'what does delivering 360s for clients look like today?'",
            "low_confidence": False,
        },
        "Solution Understanding": {
            "score": 2.5,
            "evidence": "Subaccount answer was strong when it finally came: 'if you have 10 clients, 100 clients in the future… BTS does not have any friction'. But arrived 50 minutes late",
            "low_confidence": False,
        },
    },
    "Craftsmanship": {
        "Personalization": {
            "score": 1.5,
            "evidence": "Demo env had no BTS branding, no sample BTS consulting-firm data, no client-management workspace pre-staged",
            "low_confidence": False,
        },
        "Customization": {
            "score": 2.0,
            "evidence": "Pulled up his own existing client example reactively to demonstrate competency instructions instead of pre-staging a BTS-style example",
            "low_confidence": False,
        },
    },
}

QUALITATIVE = {
    "top_3_strengths": [
        "Exceptional patience and warmth — created psychological safety for Christian to admit navigation struggles ('I've never seen anybody pick up a product like this quickly' was a beautifully timed reassurance)",
        "Named every attendee throughout; handled Mahima rejoining mid-call and Aqsa dropping without losing flow",
        "Closed cleanly with a structured 'here's how you'd actually run this end-to-end' walkthrough that gave the team a mental model for the pilot",
    ],
    "top_3_gaps": [
        "Missed the most important architectural question for an HR consulting firm: subaccount / multi-client management. Mahima had to surface it at minute ~50, and Ishrath openly acknowledged he had missed it. This should have been the opening 10 minutes of the call.",
        "Zero discovery. Never asked 'what's broken in your current process?' or 'what made you start looking?'. Treated the call as feature-walkthrough, missing the chance to surface competitor name, deal motivation, and decision criteria.",
        "Demo environment was generic — no BTS logo, no consulting-firm sample data, no pre-built multi-client workspace. For a hand-holding session with the actual buyers in the room, this is a missed personalization win.",
    ],
    "one_coaching_action": (
        "Before every BTS interaction from now on, spend 20 minutes pre-call setting up a 'BTS Demo Workspace' that already has: "
        "(1) two sample client subaccounts ('Client A', 'Client B') seeded with realistic 360 surveys, "
        "(2) BTS logo applied, "
        "(3) one approval workflow pre-wired. "
        "Open every call by demoing the subaccount switcher — it's their primary use case, not an afterthought."
    ),
}

# ============================================================================
# Hand-crafted 9-insight extraction
# ============================================================================

INSIGHTS = {
    "use_case": {
        "summary": "BTS is an HR consulting firm migrating from a previous 360-survey tool. They need ThriveSparrow for two parallel use cases: (a) internal BTS 360 performance reviews, and (b) a multi-tenant delivery platform where each of their consulting clients gets a separate subaccount.",
        "explicit_quotes": [
            "How basically my question is how all the clients would be organized on ThriveSparrow platform?",
            "If I'm building a survey for one client, would it be on the client's URL thing, or would it be in BTS ThriveSparrow thing?",
        ],
    },
    "cx_maturity": {
        "scorecard": {
            "Business objective": 2,
            "Journey context": 2,
            "Data richness": 2,
            "Segmentation": 2,
            "Workflow / action": 1,
            "Governance": 2,
            "Analytics depth": 2,
            "Integration depth": 1,
        },
        "category": "Potential High Maturity CX",
        "rationale": "Total 14/24 → Potential High Maturity. This is an Employee Experience (360 review) use case with multi-client/subaccount architecture potential — it can mature into a high-value standardized CX platform if BTS adopts SurveySparrow as their consulting delivery layer. Workflow/action and integration depth are the maturity gaps.",
    },
    "feature_requests": [
        {"feature": "Two-page welcome flow (intro + definitions/instructions before survey questions)",
         "urgency": "nice-to-have",
         "quote": "Is it possible to have two welcome pages? On the second page we give definitions and basic instructions, then from the third page the actual survey starts"},
        {"feature": "Free-text content blocks BETWEEN questions (currently only allowed above competencies)",
         "urgency": "mentioned",
         "quote": "Is there an opportunity to add just free text and not have it necessarily be a question, but maybe it's instructions or just information for the test taker?"},
        {"feature": "Custom 'from' email domain (e.g. hr@bts.com instead of ThriveSparrow default)",
         "urgency": "blocker",
         "quote": "It's also best practice to integrate it with one of your email addresses… instead of having it go from ThriveSparrow by default, which might have some restrictions within the company, which will put them in spam"},
        {"feature": "SSO integration for BTS users",
         "urgency": "nice-to-have",
         "quote": "In case you wanted it to be integrated within your SSO systems, we could explore that functionality as well"},
        {"feature": "Option to disable the default cartoon avatar in evaluator-invitation emails",
         "urgency": "mentioned",
         "quote": "If you have it where it's one invite to the evaluator and they're evaluating multiple people, it's pulling in this picture or this icon. Can that be disabled?"},
        {"feature": "Per-role minimum-evaluator thresholds (differentiated by role, not global)",
         "urgency": "mentioned",
         "quote": "If I click on that 'enforce minimum evaluation', that's gonna apply to all evaluators. There's not a way to apply it to some and not others, correct?"},
    ],
    "competitors_mentioned": [
        {"name": "Previous tool (name not surfaced)",
         "context": "currently using",
         "quote": "How do you see this getting related to the previous system that you've used before ThriveSparrow?" }
    ],
    "trial_issues": [
        {"issue": "Original trial signup blocked because BTS colleague (Emmanuel from Milan office) had already created an account with a corporate email — required reschedule and backend cleanup",
         "severity": "high",
         "quote": "From BTS has apparently signed up, and they've used one of your company-level email addresses. That's the main reason why it wasn't letting us through to sign up again"},
        {"issue": "Activation emails landed in spam (Mimecast filtering). Jamal hadn't set up his account by call time because he never saw the email",
         "severity": "high",
         "quote": "It landed in spam, and I had to release it from one of the Mimecast emails"},
        {"issue": "Custom email domain integration gated behind paid tier — not testable in trial",
         "severity": "medium",
         "quote": "In terms of integrating a custom email, we need to add a functionality in the backend, which we do not provide during the trial period"},
        {"issue": "Navigation friction — Christian repeatedly couldn't locate settings ('where do I define the minimums?', 'where would I do this?')",
         "severity": "medium",
         "quote": "Little things like that where I understand what it's saying, but I'm not sure where to go"},
    ],
    "loss_risk_signals": {
        "no_reference_customer": {"present": False, "quote": ""},
        "support_quality_concern": {"present": False, "quote": ""},
        "pricing_concern": {"present": False, "quote": ""},
        "product_gap": {"present": True,
         "quote": "Free-text content between questions not supported natively; two-page welcome flow only achievable via workaround treating it as an empty section"},
        "other": [
            "Trial-onboarding friction (duplicate-signup block + Mimecast spam) — silent risk that erodes early-stage prospect confidence",
            "Customer's most important architectural question (multi-client subaccount) was missed by the SE until prospect asked — flags a discovery-process weakness, not a product gap",
        ],
    },
    "ae_behavior": {
        "interruption_count": 1,
        "barge_in_examples": [
            "One small mid-flow correction while Ishrath was navigating UI ('Just the left a little bit') — helpful, not derailing",
        ],
        "interruption_impact": "none",
        "ae_quality_flag": False,
    },
    "se_selling_style": {
        "feature_selling_share": 0.75,
        "value_selling_share": 0.25,
        "verdict": "feature_seller",
        "evidence": "Roughly 75% of Ishrath's airtime was 'you can click here, you can configure that'. The 25% of value framing was concentrated in the subaccount discussion at the end ('ensure BTS does not have any friction… be it 10 clients, 100 clients in the future'). Context: this is a pilot-onboarding call, so heavier feature walkthrough is partially appropriate.",
    },
    "prospect_engagement": {
        "sentiment": "curious",
        "buying_signals": [
            "Christian gave Ishrath admin access to the BTS workspace at end of call",
            "Jamal committed to sending a test-user list to send surveys to",
            "Follow-up call locked in for week of June 4",
            "Mahima asked architectural multi-client question — signals serious evaluation intent for the bigger consulting use case",
        ],
        "objections": [
            "Navigation discoverability — repeated 'I don't know where X is' from Christian",
            "Two-welcome-page limitation flagged by Mahima as a deviation from their existing process",
            "Trial-environment limitations (no custom email branding) raised by Christian",
        ],
    },
}


# ============================================================================
# Build the scorecard the same shape extract_insights / score_call would
# ============================================================================

call_id = "call_2026_05_avoma_0fb0f744_bts"
se_name = "Ishrath Ahamed"
ae_name = "River England"
prospect = "BTS"

sub_scores = {crit: {sub: payload["score"] for sub, payload in subs.items()}
              for crit, subs in SCORES.items()}
per_crit_score = {crit: round(sum(s.values()) / len(s), 2) for crit, s in sub_scores.items()}
final = weighted_total(sub_scores)
benchmark_gaps = {crit: gap_vs_industry(crit, s) for crit, s in per_crit_score.items()}

scorecard = {
    "call_id": call_id,
    "se_name": se_name,
    "ae_name": ae_name,
    "prospect_company": prospect,
    "prompt_version": "real-2026-05-v1-hand-analyzed",
    "scores": SCORES,
    "per_criterion_score": per_crit_score,
    "weighted_final": final,
    "industry_percentile": percentile_of(final),
    "industry_gaps": benchmark_gaps,
    "qualitative": QUALITATIVE,
}

insights = dict(INSIGHTS)
insights["call_id"] = call_id
insights["se_name"] = se_name
insights["ae_name"] = ae_name
insights["prompt_version"] = "real-2026-05-v1-hand-analyzed"

# Persist raw
(OUT_DIR / "real_call_scorecard.json").write_text(json.dumps(scorecard, indent=2))
(OUT_DIR / "real_call_insights.json").write_text(json.dumps(insights, indent=2))

# Generate the SE report
report_path = OUT_DIR / "se_report_ishrath_ahamed_REAL_May_2026.docx"
build_se_report(
    se_name=se_name,
    se_email="ishrath.ahamed@surveysparrow.com",
    month_label="May 2026 (single call analysis)",
    scorecards=[scorecard],
    insights=[insights],
    last_3_months_finals=[scorecard["weighted_final"]],  # only 1 call so far
    output_path=str(report_path),
)

print(f"Final weighted score: {final}/5")
print(f"Industry percentile:  P{percentile_of(final)}")
print(f"Report written:       {report_path}")
print()
print("Per-criterion vs industry median:")
for crit, sc in per_crit_score.items():
    gap = benchmark_gaps[crit]
    sign = "+" if gap >= 0 else ""
    print(f"  {crit:30s}  {sc:.2f}  (gap {sign}{gap})")
