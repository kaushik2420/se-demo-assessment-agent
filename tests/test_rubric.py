from src.utils.rubric import RUBRIC, weighted_total, total_weight


def test_weights_sum_to_100():
    assert abs(total_weight() - 100.0) < 0.001


def test_weighted_total_matches_excel_formula():
    """=(weight/100)*avg(sub_scores) summed across criteria."""
    # all 5s → final = 5.0
    all_fives = {c.name: {s.name: 5.0 for s in c.subs} for c in RUBRIC}
    assert weighted_total(all_fives) == 5.0

    # all 0s → 0
    all_zeros = {c.name: {s.name: 0.0 for s in c.subs} for c in RUBRIC}
    assert weighted_total(all_zeros) == 0.0

    # all 3s → 3.0
    all_threes = {c.name: {s.name: 3.0 for s in c.subs} for c in RUBRIC}
    assert weighted_total(all_threes) == 3.0


def test_weighted_total_respects_criterion_weights():
    """Solution Skills (30%) should dominate; Audience Engagement (5%) barely moves the needle."""
    base = {c.name: {s.name: 3.0 for s in c.subs} for c in RUBRIC}
    base["Solution Skills"] = {s.name: 5.0 for s in next(c for c in RUBRIC if c.name == "Solution Skills").subs}
    score_with_strong_sol = weighted_total(base)

    base2 = {c.name: {s.name: 3.0 for s in c.subs} for c in RUBRIC}
    base2["Audience Engagement"] = {s.name: 5.0 for s in next(c for c in RUBRIC if c.name == "Audience Engagement").subs}
    score_with_strong_eng = weighted_total(base2)

    assert score_with_strong_sol > score_with_strong_eng
