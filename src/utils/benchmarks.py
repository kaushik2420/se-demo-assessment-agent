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

# Final weighted-score percentiles across SaaS SEs (0-5 scale).
# Anchor points only — percentile_of() linearly interpolates between them so
# every 0.05 of score shifts the percentile by a meaningful amount.
INDUSTRY_FINAL_PERCENTILES = {
    25: 2.8,
    50: 3.4,
    75: 3.9,
    90: 4.3,
    95: 4.5,
}

# Internal: (percentile, score) anchors sorted ascending by score, plus floor
# and ceiling sentinels for interpolation past the anchor range.
_PCT_ANCHORS = [
    (1,  0.0),   # floor
    (10, 2.0),   # rough bottom-decile anchor
    (25, 2.8),
    (50, 3.4),
    (75, 3.9),
    (90, 4.3),
    (95, 4.5),
    (99, 5.0),   # ceiling
]


def percentile_of(final_score: float) -> int:
    """Industry percentile for a final score, via linear interpolation.

    Previously this was a 5-band step function: any score between 2.8 (P25)
    and 3.4 (P50) returned 25. That misled SEs into thinking a 3.1 was
    "bottom quartile" when it should be roughly P33. Linear interpolation
    fixes the off-by-band feel.

    Worked examples:
      score 3.0  → P33   (between P25=2.8 and P50=3.4)
      score 3.1  → P37
      score 3.25 → P44
      score 3.4  → P50   (anchor)
      score 3.55 → P57
      score 4.0  → P78
      score 4.4  → P92
      score 1.8  → P9    (below P10 anchor, interpolated toward floor)
    """
    s = max(0.0, min(5.0, float(final_score)))
    for i in range(len(_PCT_ANCHORS) - 1):
        lo_pct, lo_score = _PCT_ANCHORS[i]
        hi_pct, hi_score = _PCT_ANCHORS[i + 1]
        if lo_score <= s <= hi_score:
            if hi_score == lo_score:
                return int(round(hi_pct))
            t = (s - lo_score) / (hi_score - lo_score)
            return int(round(lo_pct + t * (hi_pct - lo_pct)))
    # Fallback (score outside [0, 5] after clamp — shouldn't reach here)
    return _PCT_ANCHORS[-1][0] if s >= 5.0 else _PCT_ANCHORS[0][0]


def gap_vs_industry(criterion: str, score: float) -> float:
    """Positive = above median, negative = below median."""
    return round(score - INDUSTRY_MEDIAN_BY_CRITERION.get(criterion, 3.5), 2)
