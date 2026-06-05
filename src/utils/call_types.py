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
    PROCUREMENT       = "procurement"        # vendor security review, IT compliance, procurement walkthrough
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

    CallType.PROCUREMENT: CallTypeProfile(
        label="Procurement / security review",
        weights={
            "Communication": 20.0,             # clarity matters when fielding questionnaires
            "Presentation": 5.0,
            "Audience Engagement": 5.0,
            "Solution Skills": 10.0,           # not a sell — just answer accurately
            "Consultative Approach": 40.0,     # the WHOLE job: technical advisor mode
            "Touchbase on Pain Points": 10.0,
            "Craftsmanship": 10.0,             # references to security docs / certifications
        },
        prompt_addendum=(
            "This is a PROCUREMENT / SECURITY REVIEW / IT COMPLIANCE call. The SE is "
            "in trusted-advisor mode answering questionnaires, walking through SOC 2 / "
            "compliance posture, fielding integration / data-handling / SLA questions. "
            "Do NOT penalize for absent demo content, generic environments, or lack of "
            "value-selling — none of that applies on this call type. Reward accuracy, "
            "honesty (admitting when something isn't supported instead of bluffing), "
            "and pointing the prospect to the right doc / right person when applicable. "
            "Commercial terms / pricing / paperwork = AE's job, not SE's."
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
    """Compute final score using the weight profile for this call type.

    If an entire criterion is unscorable (no sub-criteria assessable from
    transcript — e.g. all of Craftsmanship was visual-only on an audio call),
    that criterion drops out and the REMAINING weights are rescaled to sum
    to 100 so the SE isn't penalized for a transcript-only modality.
    """
    profile = get_profile(call_type)

    # First pass: figure out which criteria are actually scorable
    scorable: Dict[str, tuple[float, float]] = {}  # crit -> (weight, avg_score)
    for crit, weight in profile.weights.items():
        if weight == 0:
            continue
        subs = scores_by_criterion.get(crit, {})
        if not subs:
            continue
        avg = sum(subs.values()) / len(subs)
        scorable[crit] = (weight, avg)

    if not scorable:
        return 0.0

    # Rescale: remaining weights should sum to 100
    weight_sum = sum(w for w, _ in scorable.values())
    total = 0.0
    for _, (weight, avg) in scorable.items():
        rescaled = weight / weight_sum  # already in [0, 1]
        total += rescaled * avg
    return round(total, 2)


# Validate all profiles
for _ct, _prof in PROFILES.items():
    _total = sum(_prof.weights.values())
    assert abs(_total - 100.0) < 0.001, f"Weights for {_ct} sum to {_total}, expected 100"
