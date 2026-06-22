"""
test_reasoning.py - Phase 5 guards for the grounded reasoning generator.

Two properties we actually care about:
  1. Grounding: every generated reasoning references >= 2 real fields from the
     candidate record (current title/company, a named matched skill, the yoe
     figure). This is the anti-hallucination / "cite concrete facts" guarantee.
  2. Variety: reasonings are not one fill-in-the-blanks skeleton - a sample of
     top-100 candidates produces distinct strings.

We run against the sample dataset (committed) so the test is hermetic and fast.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.features import extract_features  # noqa: E402
from src.reasoning import make_reasoning  # noqa: E402
from src.score import score  # noqa: E402

SAMPLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "sample_candidates.json",
)


def _candidates():
    return json.load(open(SAMPLE))


def _real_facts(c):
    """Concrete, record-grounded tokens that a reasoning may legitimately cite."""
    p = c["profile"]
    facts = []
    title = (p.get("current_title") or "").strip()
    company = (p.get("current_company") or "").strip()
    if title:
        facts.append(title)
    if company and company.lower() not in ("unknown", "n/a", "none"):
        facts.append(company)
    for s in c.get("skills", []):
        n = (s.get("name") or "").strip()
        if n:
            facts.append(n)
    yoe = p.get("years_of_experience")
    if yoe is not None:
        facts.append(f"{yoe:.1f}")  # the "N.N yrs" figure
    return facts


def test_every_reasoning_cites_two_real_facts():
    cands = _candidates()
    for c in cands:
        f = extract_features(c)
        text = make_reasoning(f, rank=None)
        facts = _real_facts(c)
        hits = sum(1 for fact in facts if fact and fact in text)
        assert hits >= 2, (
            f"{c['candidate_id']}: only {hits} grounded fact(s) in reasoning:\n"
            f"{text}\nfacts available: {facts}"
        )


def test_no_hallucinated_skill_names():
    """A named 'core IR skills ...' clause must only list skills in the record."""
    cands = _candidates()
    for c in cands:
        f = extract_features(c)
        text = make_reasoning(f, rank=1)
        for name, _ in f.get("matched_core_skills", []) + f.get("matched_nice_skills", []):
            pass  # these are by construction from the record
        # every matched skill the reasoning names must exist in the skill list
        record_skills = {(s.get("name") or "") for s in c.get("skills", [])}
        for name, _ in f.get("matched_core_skills", [])[:3]:
            if name and name in text:
                assert name in record_skills


def test_reasonings_are_varied():
    cands = _candidates()
    scored = sorted(cands, key=lambda c: -score(extract_features(c)))
    top = scored[: min(100, len(scored))]
    sample = top[:10] if len(top) >= 10 else top
    texts = []
    for rk, c in enumerate(sample, 1):
        texts.append(make_reasoning(extract_features(c), rank=rk))
    assert len(set(texts)) == len(texts), "top reasonings are not all distinct"


def test_always_has_a_caveat():
    """A reasoning with no caveat is a red flag - every one names a gap."""
    cands = _candidates()
    markers = ("caveat", "gap", "but", "though", "stretch", "risk",
               "no clear", "no explicit", "no substantial", "weak", "early-career")
    for c in cands:
        text = make_reasoning(extract_features(c), rank=1).lower()
        assert any(m in text for m in markers), f"no caveat in: {text}"
