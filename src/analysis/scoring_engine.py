"""
Score a single call against the SE rubric using Claude.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict

from prompts import scoring_prompt
from src.analysis.llm_client import LLMClient
from src.utils.rubric import RUBRIC, weighted_total
from src.utils.benchmarks import percentile_of, gap_vs_industry
from src.utils.call_types import CallType, get_profile, weighted_total_for_type


@dataclass
class CallContext:
    se_name: str
    ae_name: str
    prospect_company: str
    prospect_industry: str
    stated_use_case: str
    duration_min: int
    transcript: str
    call_id: str
    call_type: str = CallType.DEMO.value  # demo | followup_demo | followup_query | poc | closure | other


def _rubric_for_prompt() -> str:
    return json.dumps(
        [
            {
                "criterion": c.name,
                "weight_pct": c.weight,
                "description": c.description,
                "sub_criteria": [{"name": s.name, "look_for": s.description} for s in c.subs],
            }
            for c in RUBRIC
        ],
        indent=2,
    )


def _mock_scores(ctx: CallContext) -> dict:
    """Deterministic-ish mock so the demo runs without API key."""
    # Slight per-call variation based on stated_use_case hash
    seed = (sum(ord(c) for c in ctx.se_name) % 7) / 10  # 0.0 .. 0.6
    base = 3.2 + seed
    def s(x): return round(min(5.0, max(0.0, x)), 1)
    scores = {}
    for c in RUBRIC:
        scores[c.name] = {}
        for i, sub in enumerate(c.subs):
            variation = (i * 0.3) - 0.4
            scores[c.name][sub.name] = {
                "score": s(base + variation),
                "evidence": f"[demo] paraphrase of moment relevant to {sub.name}",
                "low_confidence": False,
            }
    return {
        "scores": scores,
        "qualitative": {
            "top_3_strengths": [
                "Strong rapport opening — used prospect's industry-specific anecdote",
                "Tied dashboards back to renewal-risk outcome the prospect cared about",
                "Asked confirming question before deep-diving every module",
            ],
            "top_3_gaps": [
                "Drifted into feature tour during 'Workflows' segment (~7 min)",
                "Did not anchor on the pricing concern raised at minute 4",
                "Generic demo env — no prospect logo or vertical data",
            ],
            "one_coaching_action": (
                "Before next demo, build a 30-min pre-call ritual: pull prospect's "
                "industry KPI, mock dashboard with their logo, scripted bridge from "
                "each pain → specific dashboard."
            ),
        },
    }


def score_call(ctx: CallContext, llm: LLMClient | None = None) -> dict:
    """Returns full scoring blob (scores, weighted_total, percentile, qualitative)."""
    llm = llm or LLMClient()
    profile = get_profile(ctx.call_type)

    # Build prompt with call-type-specific weights and addendum
    rubric_with_weights = _rubric_for_prompt_with_weights(profile.weights)
    user = scoring_prompt.USER_TEMPLATE.format(
        rubric_json=rubric_with_weights,
        se_name=ctx.se_name,
        ae_name=ctx.ae_name,
        prospect_company=ctx.prospect_company,
        prospect_industry=ctx.prospect_industry,
        stated_use_case=ctx.stated_use_case,
        duration_min=ctx.duration_min,
        transcript=ctx.transcript,
    )
    # Inject the call-type addendum into the system prompt so Claude knows
    # what "good" looks like for this specific call type
    system = scoring_prompt.SYSTEM + f"\n\nCALL TYPE: {profile.label}\n{profile.prompt_addendum}"

    raw = llm.chat_json(system, user, mock_response=_mock_scores(ctx))

    # Build sub_scores while honoring `not_assessable: true` — those sub-criteria
    # are EXCLUDED from the per-criterion average (so weight redistributes to
    # whatever IS assessable from the transcript), rather than getting a penalty
    # score. If an entire criterion is fully not-assessable, the criterion
    # itself drops out of the weighted total and remaining criteria are
    # rescaled to sum to 100% (so the SE isn't penalized for transcript-only).
    sub_scores: Dict[str, Dict[str, float]] = {}
    not_assessable_log: Dict[str, list[str]] = {}
    for crit, subs in raw["scores"].items():
        kept: Dict[str, float] = {}
        skipped: list[str] = []
        for sub, payload in subs.items():
            if payload.get("not_assessable") is True or payload.get("score") is None:
                skipped.append(sub)
                continue
            kept[sub] = payload["score"]
        sub_scores[crit] = kept
        if skipped:
            not_assessable_log[crit] = skipped

    final = weighted_total_for_type(sub_scores, ctx.call_type)

    # Industry benchmark comparison (uses default median, regardless of call type)
    per_crit_score = {
        crit: round(sum(s.values()) / len(s), 2) for crit, s in sub_scores.items() if s
    }
    benchmark_gaps = {
        crit: gap_vs_industry(crit, score) for crit, score in per_crit_score.items()
    }
    return {
        "call_id": ctx.call_id,
        "se_name": ctx.se_name,
        "ae_name": ctx.ae_name,
        "prospect_company": ctx.prospect_company,
        "call_type": ctx.call_type,
        "call_type_label": profile.label,
        "weights_applied": profile.weights,
        "prompt_version": scoring_prompt.VERSION,
        "scores": raw["scores"],
        "per_criterion_score": per_crit_score,
        "not_assessable": not_assessable_log,   # {criterion: [sub_name, ...]}
        "weighted_final": final,
        "industry_percentile": percentile_of(final),
        "industry_gaps": benchmark_gaps,
        "qualitative": raw["qualitative"],
    }


def _rubric_for_prompt_with_weights(weights: Dict[str, float]) -> str:
    """Like _rubric_for_prompt but uses the call-type weight overrides."""
    return json.dumps(
        [
            {
                "criterion": c.name,
                "weight_pct": weights.get(c.name, c.weight),
                "description": c.description,
                "sub_criteria": [{"name": s.name, "look_for": s.description} for s in c.subs],
            }
            for c in RUBRIC
            if weights.get(c.name, c.weight) > 0  # skip criteria zeroed out by call type
        ],
        indent=2,
    )
