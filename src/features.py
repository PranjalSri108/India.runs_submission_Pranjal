"""
features.py — Turn one raw candidate record into interpretable, JD-grounded features.

Design philosophy
-----------------
Every feature here is something you could SAY OUT LOUD in the Stage 5 interview:
"this candidate scored high on applied_ml_years because roles X, Y, Z were ML
roles at product companies." We deliberately avoid opaque signals.

Three buckets of features, mapping to the JD:
  1. FIT       — positive evidence the person can do this job
  2. PENALTY   — the explicit disqualifiers the JD says it actively applies
  3. BEHAVIOR  — is the person actually available/hireable (Redrob signals)
Plus an IMPOSSIBILITY gate that catches honeypots (internally contradictory profiles).

Single source of truth (Phase 2 refactor)
------------------------------------------
Role classification lives in classify.py, the honeypot gate in honeypot.py, and
every vocabulary in vocab.py — this module imports them rather than carrying
copies. The fit weight vector and final composition live in score.py; this
module only EXTRACTS the raw feature components (unrounded), and score.py turns
them into a number. That keeps the one tunable knob in one place.

Key data lesson (from exploring the sample):
  - career_history *descriptions* are partly shuffled noise; do NOT trust them alone.
  - Structured fields (title, industry, company_size, durations) are reliable.
  So we classify roles primarily by TITLE + INDUSTRY (in classify.py), and use
  description text only as a weak corroborating bonus.
"""

from __future__ import annotations

from datetime import date, datetime

from .classify import _any, _lower, classify_role
from .honeypot import impossibility_score
from .vocab import (
    CONSULTING_FIRMS,
    CORE_SKILL_TERMS,
    EVAL_PHRASES,
    NICE_SKILL_TERMS,
    PREFERRED_CITIES,
    SERVICES_INDUSTRIES,
    SHIPPED_SYSTEM_PHRASES,
)

# Re-export so callers/tests that reference these via `features.X` keep working.
__all__ = ["classify_role", "impossibility_score", "extract_features"]

TODAY = date(2026, 6, 18)  # competition "now"; keep consistent with the dataset.


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def extract_features(c):
    """Extract raw, unrounded feature components for one candidate.

    Returns the components score.py composes into the final score, plus the
    profile/signals carried for reasoning generation. Does NOT apply the fit
    weight vector — that is score.py's job (single tunable knob).
    """
    p = c["profile"]
    sig = c.get("redrob_signals", {})
    hist = c.get("career_history", [])
    yoe = p.get("years_of_experience", 0) or 0

    # --- FIT: accumulate ML months at product companies ---------------------
    ml_months_product = 0.0
    ml_months_any = 0.0
    product_months = 0
    total_months = 0
    shipped_system = False
    eval_signal = False
    for j in hist:
        dur = j.get("duration_months") or 0
        total_months += dur
        w, is_product = classify_role(j)
        ml_months_any += w * dur
        if is_product:
            product_months += dur
            ml_months_product += w * dur
        if _any(j.get("description", ""), SHIPPED_SYSTEM_PHRASES):
            shipped_system = True
        if _any(j.get("description", ""), EVAL_PHRASES):
            eval_signal = True

    applied_ml_years = ml_months_product / 12.0
    product_ratio = product_months / total_months if total_months else 0.0

    # --- FIT: relevant skills (proficiency x plausible duration) ------------
    prof_w = {"beginner": 0.3, "intermediate": 0.6, "advanced": 0.85, "expert": 1.0}
    core_skill_score = 0.0
    nice_skill_score = 0.0
    for s in c.get("skills", []):
        name = _lower(s.get("name"))
        d = s.get("duration_months") or 0
        # cap credited duration at the person's actual experience (anti-stuffing)
        credited = min(d, yoe * 12) / 12.0
        weight = prof_w.get(s.get("proficiency"), 0.5) * min(1.0, credited / 3.0)
        if any(t in name for t in CORE_SKILL_TERMS):
            core_skill_score += weight
        elif any(t in name for t in NICE_SKILL_TERMS):
            nice_skill_score += weight * 0.5

    # --- FIT: experience-band fit (5-9 sweet spot, soft falloff) ------------
    if 5 <= yoe <= 9:
        band_fit = 1.0
    elif yoe < 5:
        band_fit = max(0.0, 1 - (5 - yoe) * 0.18)   # ramp down below 5
    else:
        band_fit = max(0.0, 1 - (yoe - 9) * 0.10)    # gentler above 9

    # --- PENALTIES: the JD's explicit disqualifiers -------------------------
    penalties = 0.0
    reasons = []

    # Consulting-ONLY career (allowed if any prior product role exists).
    companies = [_lower(j.get("company")) for j in hist]
    industries = [_lower(j.get("industry")) for j in hist]
    all_services = all(
        (ind in SERVICES_INDUSTRIES) or any(f in comp for f in CONSULTING_FIRMS)
        for comp, ind in zip(companies, industries)
    ) if hist else False
    if all_services:
        penalties += 0.5
        reasons.append("entire career at IT-services/consulting firms")

    # Title-chasing: many short stints (<~20mo) across different companies.
    short_stints = sum(1 for j in hist if 0 < (j.get("duration_months") or 0) < 20)
    distinct_co = len(set(companies))
    if short_stints >= 3 and distinct_co >= 4:
        penalties += 0.2
        reasons.append("frequent short stints (possible title-chasing)")

    # Wrong-domain primary (CV/speech/robotics) without NLP/IR balance.
    cv_terms = ["computer vision", "image", "robotics", "speech", "audio"]
    nlp_terms = ["nlp", "retrieval", "ranking", "search", "recommendation", "language"]
    titles_text = " ".join(_lower(j.get("title")) for j in hist)
    if _any(titles_text, cv_terms) and not _any(titles_text, nlp_terms):
        penalties += 0.25
        reasons.append("CV/speech/robotics focus without NLP/IR")

    # No real ML experience at all -> this is not a fit (most of the pool).
    if applied_ml_years < 0.5:
        penalties += 0.4
        reasons.append("no substantial applied-ML experience at a product company")

    # --- BEHAVIOR: availability / hireability multiplier --------------------
    mult = 1.0
    if not sig.get("open_to_work_flag", False):
        mult *= 0.6
        reasons.append("not marked open-to-work")
    last_active = _parse_date(sig.get("last_active_date"))
    if last_active:
        days_idle = (TODAY - last_active).days
        if days_idle > 180:
            mult *= 0.6
            reasons.append(f"inactive ~{days_idle} days")
        elif days_idle > 90:
            mult *= 0.85
    resp = sig.get("recruiter_response_rate", 0.5)
    if resp < 0.2:
        mult *= 0.7
        reasons.append("very low recruiter response rate")
    interview = sig.get("interview_completion_rate", 0.5)
    if interview < 0.3:
        mult *= 0.85

    # Location fit (soft bonus, since JD strongly prefers India / relocatable).
    loc = _lower(p.get("location")) + " " + _lower(p.get("country"))
    in_india = "india" in loc
    near_hub = any(city in loc for city in PREFERRED_CITIES)
    relocate = sig.get("willing_to_relocate", False)
    location_fit = 1.0 if (near_hub or (in_india and relocate)) else (
        0.85 if in_india else (0.7 if relocate else 0.5))

    impossible = impossibility_score(c)

    # Raw, UNROUNDED components. score.py applies the weight vector and the
    # multiplicative composition; reasoning.py rounds for display.
    return {
        "candidate_id": c["candidate_id"],
        "applied_ml_years": applied_ml_years,
        "core_skill_score": core_skill_score,
        "nice_skill_score": nice_skill_score,
        "band_fit": band_fit,
        "product_ratio": product_ratio,
        "shipped_system": shipped_system,
        "eval_signal": eval_signal,
        "yoe": yoe,
        "penalties": penalties,
        "behavior_mult": mult,
        "location_fit": location_fit,
        "impossibility": impossible,
        "reasons": reasons,
        "_profile": p,            # carried for reasoning generation
        "_signals": sig,
    }


if __name__ == "__main__":
    import json
    import sys

    from .score import score

    cands = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "data/sample_candidates.json"))
    feats = [extract_features(c) for c in cands]
    feats.sort(key=score, reverse=True)
    for f in feats[:15]:
        print(f"{score(f):6.2f}  {f['candidate_id']}  "
              f"mlY={f['applied_ml_years']:>5.2f}  band={f['band_fit']:.2f}  "
              f"imp={f['impossibility']:.2f}  {f['_profile']['current_title']}")
