from src.utils.cx_maturity import MATURITY_DIMENSIONS, classify_from_scorecard


def test_form_basic_band():
    sc = {d: 0 for d in MATURITY_DIMENSIONS}
    cat, total = classify_from_scorecard(sc)
    assert cat == "Form / Basic" and total == 0


def test_high_maturity_band():
    sc = {d: 3 for d in MATURITY_DIMENSIONS}
    cat, total = classify_from_scorecard(sc)
    assert cat == "High Maturity CX" and total == 24


def test_boundary_low_to_potential():
    sc = {d: 1 for d in MATURITY_DIMENSIONS}  # total 8 → Low
    assert classify_from_scorecard(sc)[0] == "Low Maturity CX"
    sc["Business objective"] = 3   # +2
    sc["Workflow / action"] = 3    # +2
    sc["Governance"] = 3           # +2  → total 14 → Potential
    assert classify_from_scorecard(sc)[0] == "Potential High Maturity CX"
