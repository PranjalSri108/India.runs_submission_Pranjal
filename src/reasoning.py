"""
reasoning.py — Generate a candidate's explanation from its real feature values.

Phase 5 of PLAN.md. The whole thesis of this ranker is explainability, so the
reasoning must be GROUNDED, not a template: every sentence is built from the
candidate's own extracted features (src/features.extract_features), and it never
references a skill, employer, or fact that isn't in the record.

What every reasoning does:
  - cites >= 2 concrete facts (applied-ML years, current title/company, named
    matched skills, the strongest behavioral signal);
  - connects to the brief (a ranking/search/rec Senior AI Engineer role) — why
    they fit, or for lower ranks why they're a stretch;
  - names the single biggest gap honestly (over-band, padded skills, junior,
    consulting-heavy, weak availability). A reasoning with no caveat is a tell.

Structure VARIES by what dominates the candidate, so a deep-IR ideal fit reads
differently from an available-but-junior one — it is not one fill-in skeleton.
Tone tracks rank: top-10 confident, mid-pack measured, deep cautious.
"""

from __future__ import annotations

from .features import TODAY, _parse_date


def _r1(x):
    return f"{x:.1f}"


def _pick(cid, options):
    """Deterministic per-candidate choice (varies wording without RNG state)."""
    return options[hash(cid) % len(options)]


def _cap(s):
    """Uppercase only the first character (preserves acronyms like IC/NLP)."""
    return s[0].upper() + s[1:] if s else s


# --- fact phrases: each returns text built only from the record, or None ------

def _role_fact(f):
    p = f["_profile"]
    title = (p.get("current_title") or "").strip() or "their current role"
    company = (p.get("current_company") or "").strip()
    if company and company.lower() not in ("unknown", "n/a", "none"):
        return f"currently {title} at {company}"
    return f"currently in a {title} role"


def _ml_fact(f):
    aml = f["applied_ml_years"]
    if aml >= 0.5:
        return f"{_r1(aml)} yrs of applied ML at product companies"
    return None


def _skill_fact(f):
    core = [n for n, _ in f.get("matched_core_skills", []) if n]
    nice = [n for n, _ in f.get("matched_nice_skills", []) if n]
    if core:
        return "core IR skills " + ", ".join(core[:3])
    if nice:
        return "supporting ML skills " + ", ".join(nice[:3])
    return None


def _behavior(f):
    """Return (phrase, is_positive) for the single most salient signal."""
    sig = f["_signals"]
    resp = sig.get("recruiter_response_rate", 0.5)
    open_to_work = sig.get("open_to_work_flag", False)
    relocate = sig.get("willing_to_relocate", False)
    la = _parse_date(sig.get("last_active_date"))
    idle = (TODAY - la).days if la else None

    # negatives first — availability problems are decision-relevant
    if not open_to_work:
        return ("not currently marked open-to-work", False)
    if idle is not None and idle > 180:
        return (f"inactive for ~{idle} days", False)
    if resp < 0.2:
        return (f"a low {resp:.0%} recruiter-response rate", False)
    # positives
    if resp >= 0.6:
        rel = " and open to relocating" if relocate else ""
        return (f"open to work with a {resp:.0%} recruiter-response rate{rel}", True)
    if relocate:
        return ("open to work and willing to relocate", True)
    return ("open to work", True)


def _gap(f):
    """The single biggest honest caveat. Always returns something."""
    aml = f["applied_ml_years"]
    yoe = f["yoe"]
    if f["impossibility"] < 0.5:
        return ("the profile is internally inconsistent — skill/role durations "
                "exceed the stated career length")
    if aml < 0.5 and f["core_skill_score"] >= 1.5:
        return ("the IR/ML skills aren't backed by the career, which is non-ML — "
                "the skill list reads as decoration")
    if aml < 0.5:
        return "no substantial hands-on ML at a product company"
    if f["seniority_gate"] < 0.85:
        return (f"at {_r1(yoe)} yrs they're well over the 6-8 sweet spot — the "
                "risk is drift from hands-on IC into lead/architecture work")
    if f["product_ratio"] < 0.4:
        return ("most of the career is at services/consulting firms rather than "
                "product companies")
    if f["behavior_mult"] < 0.7:
        return "availability is weak (" + _behavior(f)[0] + ")"
    if yoe < 5:
        return "still early-career — below the 6-8 yrs the brief targets"
    if not f["shipped_system"]:
        return "no clear evidence of having shipped a ranking/search/rec system"
    if not f["eval_signal"]:
        return "no explicit evaluation-framework signal (NDCG/MRR/A-B testing)"
    return "skill durations are modest relative to a true 6-8 yr IR veteran"


def _connect(strength):
    if strength == "strong":
        return "a credible plug-in fit for a ranking/search/rec Senior AI Engineer brief"
    if strength == "mid":
        return "a partial fit for the ranking/search/rec brief"
    return "a stretch for this senior IR brief"


def _archetype(f):
    aml = f["applied_ml_years"]
    if f["impossibility"] < 0.5:
        return "impossible"
    if aml < 0.5 and f["core_skill_score"] >= 1.5:
        return "stuffer"
    if f["seniority_gate"] < 0.8 and aml >= 1.0:
        return "over_band"
    if aml >= 1.0 and f["product_ratio"] < 0.4:
        return "consulting"
    if aml >= 1.5 and f["behavior_mult"] < 0.7:
        return "stale"
    if f["yoe"] < 5 and aml < 3:
        return "junior"
    if aml < 1.0:
        return "adjacent"
    if (aml >= 3 and f["shipped_system"] and f["core_skill_score"] >= 2
            and f["seniority_gate"] >= 0.9 and f["behavior_mult"] >= 0.85):
        return "ideal"
    return "solid"


def _lead(cid, rank):
    """Tone-setting opener that tracks rank."""
    if rank is not None and rank <= 10:
        return _pick(cid, ["A strong match", "A standout fit", "A top-tier fit"])
    if rank is not None and rank <= 50:
        return _pick(cid, ["A solid fit", "A credible fit", "A plausible fit"])
    return _pick(cid, ["A marginal fit", "A stretch", "A weak fit"])


def make_reasoning(f, rank=None):
    """Build a grounded, varied, caveated explanation for one candidate.

    `f` is the dict from features.extract_features; `rank` (1-based) tunes tone.
    """
    cid = f["candidate_id"]
    role = _role_fact(f)
    ml = _ml_fact(f)
    skills = _skill_fact(f)
    sig_phrase, sig_pos = _behavior(f)
    gap = _gap(f)
    arch = _archetype(f)
    lead = _lead(cid, rank)

    shipped_eval = []
    if f["shipped_system"]:
        shipped_eval.append("has shipped a production ranking/search system")
    if f["eval_signal"]:
        shipped_eval.append("shows evaluation-framework signal (NDCG/MRR/A-B)")
    se = " and ".join(shipped_eval)

    # Each archetype assembles its own structure / ordering.
    if arch == "ideal":
        body = f"{lead} for the brief: {role}, with {ml}"
        if skills:
            body += f" and {skills}"
        body += "."
        if se:
            body += f" {_cap(se)}."
        body += f" {_cap(sig_phrase)}."
        body += f" The only real caveat: {gap}."

    elif arch == "over_band":
        body = (f"Deep experience, but over the band: {role} with "
                f"{_r1(f['yoe'])} yrs total and {ml}")
        if skills:
            body += f", plus {skills}"
        body += f". {_cap(gap)}."
        body += f" {_cap(sig_phrase)}."
        body += f" Genuine ML depth, but {_connect('mid')} given the seniority."

    elif arch == "stuffer":
        lead_s = skills or "an ML-heavy skill list"
        body = (f"{_cap(lead_s)} look relevant on paper, but the career "
                f"doesn't support them: {role}")
        if ml:
            body += f", with only {ml}"
        body += f". {_cap(gap)}."
        body += f" {_cap(sig_phrase)}, but {_connect('weak')}."

    elif arch == "consulting":
        body = f"{role} with {ml}"
        if skills:
            body += f" and {skills}"
        body += f", but {f['product_ratio']:.0%} of the career is product-company work — {gap}."
        body += f" Borderline ML credibility; {_connect('mid')}."
        body += f" {_cap(sig_phrase)}."

    elif arch == "stale":
        body = f"Strong on paper — {role}, {ml}"
        if skills:
            body += f", {skills}"
        body += (f" — but availability is the problem: {sig_phrase}. "
                 f"A strong-fit candidate who may not be reachable, which caps "
                 f"the practical value; {_connect('mid')}.")

    elif arch == "junior":
        body = f"{lead}: early-career. {_cap(role)} with {_r1(f['yoe'])} yrs total"
        body += f" and {ml}." if ml else ", with no substantial applied-ML track record yet."
        if skills:
            body += f" Shows {skills}."
        body += f" {_cap(sig_phrase)}."
        body += f" The gap is seniority — {gap} — so {_connect('weak')}, more a development bet."

    elif arch == "adjacent":
        body = f"{lead}: a technical profile adjacent to the brief. {_cap(role)}"
        body += f", but {gap}."
        if skills:
            body += f" Has {skills}, though the career is not ML/IR."
        body += f" {_cap(sig_phrase)}. {_cap(_connect('weak'))}."

    elif arch == "impossible":
        body = (f"Flagged: {role}, but {gap}. "
                f"The internal contradiction is disqualifying regardless of the "
                f"skill list — {_connect('weak')}.")

    else:  # solid
        body = f"{lead}: {role} with {ml}"
        if skills:
            body += f" and {skills}"
        body += "."
        if se:
            body += f" {_cap(se)}."
        body += f" {_cap(sig_phrase)}."
        body += f" Main gap: {gap}. {_cap(_connect('mid'))}."

    return body


if __name__ == "__main__":
    from .features import extract_features
    from .io_utils import iter_candidates
    from .score import score

    rows = []
    for c in iter_candidates():
        f = extract_features(c)
        rows.append((score(f), f))
    rows.sort(key=lambda r: -r[0])
    for rk, (_, f) in enumerate(rows[:15], 1):
        print(f"#{rk}  {f['candidate_id']}")
        print("   " + make_reasoning(f, rank=rk))
        print()
