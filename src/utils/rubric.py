"""
Scoring rubric — derived from 'Demo of the month evaluations.xlsx' (kaushik's eval framework).
Weights sum to 100. Each sub-criterion is scored 0-5; sub-scores are averaged within a
criterion, multiplied by the criterion weight / 100, then summed for the final score (out of 5).
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class SubCriterion:
    name: str
    description: str  # what to look for in the transcript


@dataclass
class Criterion:
    name: str
    weight: float  # percentage out of 100
    subs: List[SubCriterion]
    description: str


RUBRIC: List[Criterion] = [
    Criterion(
        name="Communication",
        weight=15.0,
        description="Verbal clarity and ability to keep the prospect leaning in",
        subs=[
            SubCriterion("Tone", "Warm, confident, paced; not monotone or rushed"),
            SubCriterion("Engaging Level", "Storytelling, analogies, questions that re-engage attention"),
        ],
    ),
    Criterion(
        name="Presentation",
        weight=10.0,
        description="Structure and flow of what is shown on screen",
        subs=[
            SubCriterion("Relevance", "Every artifact shown ties back to a stated prospect need"),
            SubCriterion("Cohesion", "Narrative arc: discovery → value → product → next step"),
        ],
    ),
    Criterion(
        name="Audience Engagement",
        weight=5.0,
        description="Two-way conversation; prospect is reacting, not just watching",
        subs=[
            SubCriterion("Personalization", "Uses prospect name, company, industry-specific examples"),
            SubCriterion("Interactivity", "Asks confirming questions; invites the prospect to drive"),
        ],
    ),
    Criterion(
        name="Solution Skills",
        weight=30.0,
        description="Core SE craft: shaping the product to the buyer's problem",
        subs=[
            SubCriterion("Customization", "Demo flow is tailored, not a canned tour"),
            SubCriterion("Solution-Focused", "Frames features as outcomes, not capabilities"),
        ],
    ),
    Criterion(
        name="Consultative Approach",
        weight=15.0,
        description="Acting as an advisor — surfacing what the prospect didn't ask for but needs",
        subs=[
            SubCriterion("Proactiveness", "Volunteers insights, industry benchmarks, peer practices"),
            SubCriterion("Recommendations", "Gives a clear point of view on the right path"),
            SubCriterion("Highlighting Key Points", "Summarizes and anchors take-aways for the buyer"),
        ],
    ),
    Criterion(
        name="Touchbase on Pain Points",
        weight=5.0,
        description="Surfacing and addressing the underlying pains, not just stated requirements",
        subs=[
            SubCriterion("Addressing Pain Points", "Loops back to pains throughout the demo, not just at start"),
            SubCriterion("Solution Understanding", "Connects each pain to a specific resolution path"),
        ],
    ),
    Criterion(
        name="Craftsmanship",
        weight=20.0,
        description="Polish of the demo artifact itself — pre-built environments, sample data, dashboards",
        subs=[
            SubCriterion("Personalization", "Demo env uses prospect's logo, vertical-relevant data"),
            SubCriterion("Customization", "Custom dashboards, role-played personas, working integrations"),
        ],
    ),
]


def total_weight() -> float:
    return sum(c.weight for c in RUBRIC)


def criterion_score(sub_scores: Dict[str, float]) -> float:
    """Average of sub-scores, returned on the 0-5 scale."""
    if not sub_scores:
        return 0.0
    return sum(sub_scores.values()) / len(sub_scores)


def weighted_total(scores_by_criterion: Dict[str, Dict[str, float]]) -> float:
    """
    scores_by_criterion: {criterion_name: {sub_name: 0-5 score}}
    Returns final score out of 5, matching the Excel formula =(weight/100)*avg(sub_scores).
    """
    total = 0.0
    for crit in RUBRIC:
        subs = scores_by_criterion.get(crit.name, {})
        total += (crit.weight / 100.0) * criterion_score(subs)
    return round(total, 2)


assert abs(total_weight() - 100.0) < 0.001, "Rubric weights must sum to 100"
