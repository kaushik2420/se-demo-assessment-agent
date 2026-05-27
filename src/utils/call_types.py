"""
Call type taxonomy + per-type rubric weight overrides + per-type scoring guidance.

A first-demo call and a closure call should not be scored against the same weights.
For a closure call, "Presentation cohesion" matters far less than "Consultative
recommendations". For a POC, "Craftsmanship" of the demo environment matters more
than for a casual follow-up query call.

Each call type:
  - Has its own weight profile (must sum to 100)
  - Has a prompt addendum that tells Claude what "good" looks like for this type
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class CallType(str, Enum):
    DEMO              = "demo"               # first / primary demo to a prospect
    FOLLOWUP_DEMO     = "followup_demo"      # 2nd, 3rd demo deepening into specific modules
    FOLLOWUP_QUERY    = "followup_query"     # short Q&A / technical clarification call
    POC               = "poc"                # proof-of-concept walkthrough / validation
    CLOSURE           = "closure"            # final commercial / commitment call
    OTHER             = "other"              # default to standard rubric


@dataclass
class CallTypeProfile:
    label: str
    weights: Dict[str, float]      # criterion → weight % (must sum to 100)
    prompt_addendum: str           # extra context for the scoring prompt


# Base weights from the original rubric (Demo of the month evaluations.xlsx)
_BASE_WEIGHTS = {
    "Communication": 15.0,
    "Presentation": 10.0,
    "Audience Engagement": 5.0,
    "Solution Skills": 30.0,
    "Consultative Approach": 15.0,
    "Touchbase on Pain Points": 5.0,
    "Craftsmanship": 20.0,
}


PROFILES: Dict[CallType, CallTypeProfile] = {

    CallType.DEMO: CallTypeProfile(
        label="Demo call",
        weights=_BASE_WEIGHTS.copy(),
        prompt_addendum=(
            "This is a FIRST DEMO. The SE must (a) personalize the demo env with prospect "
            "data/logo where possible, (b) tie every feature shown to a stated pain, and "
            "(c) leave the prospect with a clear next step. Generic feature tours are a "
            "hard cap at 2.5 on Solution Skills and Craftsmanship."
        ),
    ),

    CallType.FOLLOWUP_DEMO: CallTypeProfile(
        label="Follow-up demo",
        weights={
            "Communication": 10.0,
            "Presentation": 10.0,
            "Audience Engagement": 5.0,
            "Solution Skills": 25.0,
            "Consultative Approach": 20.0,
            "Touchbase on Pain Points": 15.0,   # CRITICAL: must address prior pains
            "Craftsmanship": 15.0,
        },
        prompt_addendum=(
            "This is a FOLLOW-UP DEMO. The SE MUST explicitly reference pain points "
            "raised in the previous call(s) — if they don't, that's a 0 on Pain Points, "
            "not a 2.5. Customization must show deeper-than-default work (custom workflows, "
            "real-data examples, integration mockups). Generic re-demos are a fail."
        ),
    ),

    CallType.FOLLOWUP_QUERY: CallTypeProfile(
        label="Follow-up query call",
        weights={
            "Communication": 15.0,
            "Presentation": 10.0,
            "Audience Engagement": 5.0,
            "Solution Skills": 20.0,
            "Consultative Approach": 30.0,      # advisor mode
            "Touchbase on Pain Points": 15.0,
            "Craftsmanship": 5.0,               # demo env matters less
        },
        prompt_addendum=(
            "This is a SHORT FOLLOW-UP QUERY call (typically 15-30 min). Score consultative "
            "advisory behavior heavily — was the SE a trusted technical advisor or just an "
            "FAQ answerer? Craftsmanship is downweighted; pre-built dashboards aren't expected. "
            "But every answer should still tie back to the prospect's business outcome."
        ),
    ),

    CallType.POC: CallTypeProfile(
        label="POC walkthrough",
        weights={
            "Communication": 5.0,
            "Presentation": 5.0,
            "Audience Engagement": 5.0,
            "Solution Skills": 35.0,            # this is THE proof phase
            "Consultative Approach": 15.0,
            "Touchbase on Pain Points": 15.0,
            "Craftsmanship": 20.0,              # demo env must be near-production
        },
        prompt_addendum=(
            "This is a PROOF-OF-CONCEPT walkthrough — the prospect is validating that "
            "SurveySparrow can actually do what the SE promised in earlier demos. Solution "
            "Skills and Craftsmanship dominate. Penalize heavily for any 'that's on the "
            "roadmap' answer that wasn't disclosed up front. Reward bridging features into "
            "the prospect's actual workflow with their actual data."
        ),
    ),

    CallType.CLOSURE: CallTypeProfile(
        label="Closure call",
        weights={
            "Communication": 15.0,
            "Presentation": 10.0,
            "Audience Engagement": 10.0,
            "Solution Skills": 10.0,            # less product walkthrough
            "Consultative Approach": 35.0,      # advisor / dealmaker mode
            "Touchbase on Pain Points": 20.0,   # final loop-back to original pains
            "Craftsmanship": 0.0,               # not relevant
        },
        prompt_addendum=(
            "This is a CLOSURE / commitment call. The SE's job is to (a) loop back to the "
            "original pains and confirm SurveySparrow solves them, (b) surface any remaining "
            "doubts proactively, and (c) help the AE land the close without overpromising. "
            "Score Consultative Approach heavily. Craftsmanship is N/A. Penalize any new "
            "feature tour — this is not the time."
        ),
    ),

    CallType.OTHER: CallTypeProfile(
        label="Other / unclassified",
        weights=_BASE_WEIGHTS.copy(),
        prompt_addendum="Use the default rubric; flag as 'other' for kaushik to recategorize.",
    ),
}


def get_profile(call_type: str | CallType) -> CallTypeProfile:
    """Get the profile for a call type. Defaults to OTHER if unknown."""
    if isinstance(call_type, str):
        try:
            call_type = CallType(call_type)
        except ValueError:
            call_type = CallType.OTHER
    return PROFILES[call_type]


def weighted_total_for_type(scores_by_criterion: Dict[str, Dict[str, float]], call_type: str | CallType) -> float:
    """Compute final score using the weight profile for this call type."""
    profile = get_profile(call_type)
    total = 0.0
    for crit, weight in profile.weights.items():
        if weight == 0:
            continue
        subs = scores_by_criterion.get(crit, {})
        if not subs:
            continue
        avg = sum(subs.values()) / len(subs)
        total += (weight / 100.0) * avg
    return round(total, 2)


# Validate all profiles
for _ct, _prof in PROFILES.items():
    _total = sum(_prof.weights.values())
    assert abs(_total - 100.0) < 0.001, f"Weights for {_ct} sum to {_total}, expected 100"
