"""Phase 1 checkpoint: the 5 known sample honeypots must score <= 0.5,
and the extracted honeypot/classify logic must match the validated prototype.
"""

import json
import os

from src import features  # the validated Phase 2 prototype (reference behavior)
from src.classify import classify_role
from src.honeypot import impossibility_score

_DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
KNOWN_HONEYPOTS = [
    "CAND_0000003", "CAND_0000011", "CAND_0000012",
    "CAND_0000013", "CAND_0000022",
]


def _load_sample():
    with open(os.path.join(_DATA, "sample_candidates.json")) as fh:
        return {c["candidate_id"]: c for c in json.load(fh)}


def test_known_honeypots_score_low():
    sample = _load_sample()
    for cid in KNOWN_HONEYPOTS:
        assert cid in sample, f"{cid} missing from sample"
        score = impossibility_score(sample[cid])
        assert score <= 0.5, f"{cid} scored {score} (> 0.5)"


def test_known_honeypots_collapse():
    """Graduated gate should collapse true honeypots toward zero, not just
    haircut them - they each claim a skill for ~2.5x their whole career."""
    sample = _load_sample()
    for cid in KNOWN_HONEYPOTS:
        score = impossibility_score(sample[cid])
        assert score <= 0.1, f"{cid} scored {score} (expected near-zero collapse)"


# NOTE: impossibility_score intentionally diverges from the prototype here -
# Check A moved from an additive slack (over-firing on 5.4% of the pool) to a
# graduated ratio gate. So there is no honeypot<->prototype parity test.
# classify_role is unchanged, so its parity with the prototype still holds.
def test_classify_matches_prototype():
    sample = _load_sample()
    for c in sample.values():
        for job in c.get("career_history", []):
            assert classify_role(job) == features.classify_role(job)
