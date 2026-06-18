"""
honeypot.py — Impossibility gate: honeypot detection via internal contradiction.

The pool contains ~80 honeypots: profiles engineered to look attractive to a
keyword/embedding ranker but that are internally *impossible*. We never
blocklist specific IDs (the JD says a good system avoids honeypots naturally);
instead we score each profile on how internally consistent it is and multiply
the final score by that, so a contradictory profile collapses regardless of how
good it looks on paper.

`impossibility_score` returns a multiplier in [0,1]: 1.0 = fully plausible,
->0.0 = internally impossible.

Design note — ratio, not additive slack (tuned on the full 100K pool)
--------------------------------------------------------------------
The validated prototype's Check A flagged any skill whose duration exceeded
`yoe*12 + 18` months. On the full pool that fired on 5,429 candidates (5.4%) —
mostly senior people merely a few months over, because a skill can legitimately
be *used* longer than one's *professional* tenure (school, side projects). The
real honeypot signature is scale-relative: the known honeypots each claim a
skill for ~2.5x their entire professional life. So Check A is now a **ratio**
(skill_dur / career_months) with a **graduated** penalty:

  - ratio <= 1.5  -> no penalty            (plausible pre-career use)
  - ratio 1.5..2.5 -> penalty ramps 0..0.95 (marginal cases barely dinged)
  - ratio >= 2.5  -> penalty 0.95          (true honeypot collapses to ~0.05)

This replaces a flat 0.4 haircut that was simultaneously too gentle for a real
honeypot scoring high and too harsh for a borderline genuine fit. Behavior here
intentionally diverges from the prototype (see tests/test_honeypot.py).
"""

from __future__ import annotations

# Check A ratio thresholds (skill duration months / professional months).
RATIO_FREE = 1.5   # at/below: plausible (pre-career/education use), no penalty
RATIO_FULL = 2.5   # at/above: internally impossible, near-total collapse
MAX_A_PENALTY = 0.95  # worst-case Check A haircut -> score floor ~0.05


def _ratio_penalty(worst_ratio: float) -> float:
    """Graduated Check A penalty from the worst skill-duration ratio."""
    if worst_ratio <= RATIO_FREE:
        return 0.0
    frac = (worst_ratio - RATIO_FREE) / (RATIO_FULL - RATIO_FREE)
    return MAX_A_PENALTY * min(1.0, frac)


def impossibility_score(c: dict) -> float:
    """Return value in [0,1]: 1 = fully plausible, ->0 = internally impossible."""
    p = c["profile"]
    yoe = p.get("years_of_experience", 0) or 0
    career_months = yoe * 12
    budget = career_months + 18  # +18mo slack for rounding/overlap (Checks B, C)

    penalty = 0.0

    # A) Graduated: worst skill duration relative to the whole career.
    #    Also a soft keyword-stuffing signal: advanced/expert with ~no practice.
    worst_ratio = 0.0
    for s in c.get("skills", []):
        d = s.get("duration_months") or 0
        if d > 0:
            ratio = d / max(career_months, 1.0)  # guard div-by-zero for ~0 yoe
            worst_ratio = max(worst_ratio, ratio)
        if s.get("proficiency") in ("advanced", "expert") and 0 < d < 6:
            penalty += 0.1
    penalty += _ratio_penalty(worst_ratio)

    # B) A single job longer than the entire claimed career (hard contradiction).
    for j in c.get("career_history", []):
        if (j.get("duration_months") or 0) > budget:
            penalty += 0.6

    # C) Career-month total wildly exceeds plausible experience (allowing overlap).
    total = sum(j.get("duration_months") or 0 for j in c.get("career_history", []))
    if total > budget * 1.8:
        penalty += 0.3

    return max(0.0, 1.0 - penalty)
