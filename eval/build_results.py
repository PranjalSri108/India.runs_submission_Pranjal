"""
build_results.py - single source of truth for the demo header numbers.

Scores the full pool ONCE with the current src/score.py weights and writes
eval/results.json: the ranking-quality metrics (recomputed every run, so they can
never drift from the live scoring), the rule-compliance facts (honeypots in the
final top-100, distinct scores, runtime, validator pass), and the recorded
pre-tuning baseline for the quality metrics.

The baseline column is *history* - it was measured on the untuned scorer and
cannot be recomputed from the current weights - so it lives here as a constant,
sourced from the README "Results" table.

This is presentation tooling: it never writes submission.csv and is not on the
submission reproduce path. Re-run it whenever the scoring changes:

  python eval/build_results.py
"""

from __future__ import annotations

import json
import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from eval.validate_ranker import (  # noqa: E402
    DEFAULT_LABELS, kendall_tau_b, load_labels, ndcg_at_k,
)
from src.features import extract_features  # noqa: E402
from src.io_utils import iter_candidates  # noqa: E402
from src.rank import TOP_N, honeypot_scan  # noqa: E402
from src.score import score  # noqa: E402
from validate_submission import validate_submission  # noqa: E402

RESULTS_PATH = os.path.join(_REPO_ROOT, "eval", "results.json")
SUBMISSION_PATH = os.path.join(_REPO_ROOT, "submission.csv")

# Recorded validation history: NDCG@10/@50 and Kendall tau-b of the UNTUNED
# scorer on the 60-profile set, before the saturation/gate/assessment changes.
# Source: README.md "Results" table, "Baseline" column. Not recomputable from the
# current weights, so it is stored, not derived.
BASELINE = {"ndcg10": 0.871, "ndcg50": 0.952, "tau": 0.722}

# How many honeypots the dataset seeds (spec section 7: "a small number (~80)").
HONEYPOTS_SEEDED_APPROX = 80
RUNTIME_BUDGET_S = 300  # spec: <= 5 minutes


def main():
    labels = load_labels(DEFAULT_LABELS)

    t0 = time.time()
    scored = []
    for c in iter_candidates():
        f = extract_features(c)
        scored.append((round(score(f), 6), c["candidate_id"], f))
    runtime_s = time.time() - t0

    scored.sort(key=lambda r: (-r[0], r[1]))
    top = scored[:TOP_N]
    honeypots_top = len(honeypot_scan(top))
    distinct_scores = len({r[0] for r in top})

    # Judged-pool metrics: order the labeled candidates by the current score.
    score_by_id = {cid: sc for sc, cid, _ in scored}
    judged = [(cid, tier, score_by_id[cid]) for cid, tier in labels.items()
              if cid in score_by_id]
    judged.sort(key=lambda r: -r[2])
    ordered_tiers = [t for _, t, _ in judged]
    ndcg10 = ndcg_at_k(ordered_tiers, 10)
    ndcg50 = ndcg_at_k(ordered_tiers, 50)
    tau = kendall_tau_b([s for _, _, s in judged], [t for _, t, _ in judged])

    validator_errors = validate_submission(SUBMISSION_PATH)

    results = {
        "generated_by": "eval/build_results.py",
        "validation": {
            "n_labels": len(judged),
            "set": "60-profile hand-labeled validation set",
            "note": "local tuning proxy, not the hidden competition score",
        },
        "quality": {
            "ndcg10": {"label": "NDCG@10", "sub": "top-10 ranking quality",
                       "baseline": BASELINE["ndcg10"], "current": round(ndcg10, 3)},
            "ndcg50": {"label": "NDCG@50", "sub": "top-50 ranking quality",
                       "baseline": BASELINE["ndcg50"], "current": round(ndcg50, 3)},
            "tau": {"label": "Kendall tau", "sub": "rank agreement with human labels",
                    "baseline": BASELINE["tau"], "current": round(tau, 3)},
        },
        "constraints": {
            "honeypots_top100": honeypots_top,
            "honeypots_seeded_approx": HONEYPOTS_SEEDED_APPROX,
            "runtime_s": round(runtime_s, 1),
            "runtime_budget_s": RUNTIME_BUDGET_S,
            "distinct_scores": distinct_scores,
            "top_n": TOP_N,
            "validator_passed": not validator_errors,
        },
    }

    with open(RESULTS_PATH, "w") as fh:
        json.dump(results, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"wrote {RESULTS_PATH}")
    print(f"  NDCG@10 {BASELINE['ndcg10']:.3f} -> {ndcg10:.3f}")
    print(f"  NDCG@50 {BASELINE['ndcg50']:.3f} -> {ndcg50:.3f}")
    print(f"  tau-b   {BASELINE['tau']:+.3f} -> {tau:+.3f}")
    print(f"  honeypots in top-{TOP_N}: {honeypots_top} of ~{HONEYPOTS_SEEDED_APPROX}")
    print(f"  distinct scores: {distinct_scores}/{TOP_N}")
    print(f"  runtime: {runtime_s:.1f}s (budget {RUNTIME_BUDGET_S}s)")
    print(f"  validator passed: {not validator_errors}")


if __name__ == "__main__":
    main()
