"""
CX Maturity classifier — encodes 'SurveySparrow_CX_Use_Case_Maturity_Classification.docx'.

Returns one of four categories with a 0-24 scorecard (8 dimensions × 0-3).

We expose two surfaces:
  - `MATURITY_SIGNALS`: structured criteria to inject into the Claude prompt
  - `classify_from_scorecard(scorecard)`: deterministic mapping after Claude scores
"""

from typing import Dict, Literal

Category = Literal["Form / Basic", "Low Maturity CX", "Potential High Maturity CX", "High Maturity CX"]

MATURITY_DIMENSIONS = [
    "Business objective",
    "Journey context",
    "Data richness",
    "Segmentation",
    "Workflow / action",
    "Governance",
    "Analytics depth",
    "Integration depth",
]

# 0-3 anchors for each dimension (per the doc, section 6)
DIMENSION_ANCHORS = {
    "Business objective": {
        0: "Collect information",
        1: "Measure satisfaction",
        2: "Improve a touchpoint",
        3: "Drive a business outcome (retention, revenue, adoption)",
    },
    "Journey context": {
        0: "None",
        1: "Single generic touchpoint",
        2: "Multiple identifiable touchpoints",
        3: "Full journey map and lifecycle view",
    },
    "Data richness": {
        0: "Only answers",
        1: "Answers + basic contact data",
        2: "Answers + contact + transactional variables",
        3: "Rich customer, transactional, operational + metadata",
    },
    "Segmentation": {
        0: "None",
        1: "Basic filters",
        2: "Meaningful segments",
        3: "Role-based, hierarchy-based, outcome-linked",
    },
    "Workflow / action": {
        0: "Manual or none",
        1: "Basic alerts",
        2: "Escalation potential",
        3: "Closed-loop workflows with SLAs and ownership",
    },
    "Governance": {
        0: "Admin-owned",
        1: "CX/Support-owned",
        2: "Cross-functional review possible",
        3: "Executive cadence and program governance",
    },
    "Analytics depth": {
        0: "Exports only",
        1: "Basic dashboards",
        2: "Drill-down dashboards",
        3: "Predictive / AI insights, theme tracking, business impact",
    },
    "Integration depth": {
        0: "None",
        1: "CSV import / export",
        2: "One or two system integrations",
        3: "CRM / support / commerce / DWH / BI ecosystem",
    },
}


def classify_from_scorecard(scorecard: Dict[str, int]) -> tuple[Category, int]:
    """
    scorecard: {dimension_name: 0|1|2|3}
    Returns (category, total).
    Bands per the doc: 0-6 Form/Basic, 7-12 Low, 13-18 Potential, 19-24 High.
    """
    total = sum(scorecard.get(d, 0) for d in MATURITY_DIMENSIONS)
    if total <= 6:
        return "Form / Basic", total
    if total <= 12:
        return "Low Maturity CX", total
    if total <= 18:
        return "Potential High Maturity CX", total
    return "High Maturity CX", total
