"""
score.py - Compose feature components into the final, explainable score.

This module holds the ONE tunable knob: `WEIGHTS`. Phases 3-4 tune these against
the hand-labeled validation set; until then they are exactly the values the
prototype was validated with (do not tune here yet).

The scoring model (PLAN section 0), every term explainable:

    final = max(0, fit - penalties)
            * behavior_mult * location_fit * impossibility * seniority_gate

where `fit` is a weighted sum of the positive feature components. Penalties are
subtracted (the JD's explicit disqualifiers); behavior, location, impossibility
and seniority are multiplicative *gates* so a perfect-on-paper but unavailable,
mislocated, internally impossible, or well-over-band candidate collapses
regardless of fit.
"""

from __future__ import annotations

import math

# The fit weight vector - the single source of tunable truth. Keys are feature
# names produced by features.extract_features. Boolean components (shipped_system,
# eval_signal) are treated as 1.0/0.0. Values are deliberately round and
# defensible; each maps to a JD requirement (see PLAN section 0).
WEIGHTS = {
    "applied_ml_years": 2.2,   # dominant: real ML years at product companies
    "core_skill_score": 1.5,   # core IR/embeddings/ranking skills
    "nice_skill_score": 0.4,   # supporting ML skills (discounted)
    "band_fit": 1.2,           # right seniority band (5-9 yrs sweet spot)
    "product_ratio": 0.8,      # share of career at product (vs services) cos
    "shipped_system": 1.0,     # JD headline: "shipped a ranking/search system"
    "eval_signal": 0.6,        # JD must-have: evaluation frameworks (NDCG/MRR/AB)
}

# applied_ml_years is the dominant term, so raw years let a 15-year profile run
# away with it even though the JD wants ~4-5. We saturate it: full credit up to
# the cap, then a shallow slope so additional years add real but diminishing
# value. This keeps the term from being a pure seniority proxy.
ML_YEARS_CAP = 5.0
ML_YEARS_OVER_SLOPE = 0.3


def _saturate_ml_years(x: float) -> float:
    if x <= ML_YEARS_CAP:
        return x
    return ML_YEARS_CAP + ML_YEARS_OVER_SLOPE * (x - ML_YEARS_CAP)


# core_skill_score is a SUM over matched core skills with no cap, so it can grow into
# the single largest fit term and reward *breadth* of a listed skill set over depth -
# inverting the career-over-skills thesis (DECISIONS #9, eval/AUDIT.md §5). Saturate it
# with diminishing returns (asymptote CORE_SKILL_SAT), mirroring the ML-years cap: the
# first few genuine core skills earn near-full credit; extra listed skills add little.
CORE_SKILL_SAT = 6.0


def _saturate_core(x: float) -> float:
    return CORE_SKILL_SAT * (1.0 - math.exp(-x / CORE_SKILL_SAT))


def fit_score(f: dict) -> float:
    """Weighted sum of the positive fit components (pre-penalty, pre-gates)."""
    total = 0.0
    for key, w in WEIGHTS.items():
        v = f[key]
        if key == "applied_ml_years":
            v = _saturate_ml_years(v)
        elif key == "core_skill_score":
            v = _saturate_core(v)
        total += w * (1.0 if v is True else (0.0 if v is False else v))
    return total


def score(f: dict) -> float:
    """Final score: max(0, fit - penalties) * behavior * location * impossibility."""
    fit = fit_score(f)
    return (
        max(0.0, fit - f["penalties"])
        * f["behavior_mult"]
        * f["location_fit"]
        * f["impossibility"]
        * f["seniority_gate"]
    )
