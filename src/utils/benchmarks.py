"""
SaaS-industry SE benchmarks.

Sources to seed and refresh quarterly:
  - Gartner SE Excellence (annual)
  - PreSales Collective State of PreSales report
  - SalesHood / Gong public demo benchmarks
  - Bain SaaS GTM benchmark surveys

The values below are reasonable starting estimates for a B2B SaaS SE on the
0-5 scale used by this rubric. Replace with subscription data feeds in prod
(DynamoDB table `ss_se_industry_benchmarks`, refreshed via Lambda).
"""

# Per-criterion industry medians (0-5 scale)
INDUSTRY_MEDIAN_BY_CRITERION = {
    "Communication": 3.8,
    "Presentation": 3.6,
    "Audience Engagement": 3.4,
    "Solution Skills": 3.5,
    "Consultative Approach": 3.2,
    "Touchbase on Pain Points": 3.3,
    "Craftsmanship": 3.0,
}

# Final weighted-score percentiles across SaaS SEs (0-5 scale)
INDUSTRY_FINAL_PERCENTILES = {
    25: 2.8,
    50: 3.4,
    75: 3.9,
    90: 4.3,
    95: 4.5,
}


def percentile_of(final_score: float) -> int:
    """Return the approximate industry percentile for a final score."""
    if final_score >= INDUSTRY_FINAL_PERCENTILES[95]:
        return 95
    if final_score >= INDUSTRY_FINAL_PERCENTILES[90]:
        return 90
    if final_score >= INDUSTRY_FINAL_PERCENTILES[75]:
        return 75
    if final_score >= INDUSTRY_FINAL_PERCENTILES[50]:
        return 50
    if final_score >= INDUSTRY_FINAL_PERCENTILES[25]:
        return 25
    return 10


def gap_vs_industry(criterion: str, score: float) -> float:
    """Positive = above median, negative = below median."""
    return round(score - INDUSTRY_MEDIAN_BY_CRITERION.get(criterion, 3.5), 2)
