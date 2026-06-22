"""
validate_ranker.py - Offline agreement of the ranker vs your hand labels.

Phase 3 of PLAN.md. This is our proxy for the hidden competition metric, used to
tune weights (Phase 4) without burning submissions.

It re-scores the FULL 100K pool with the *current* src/score.py weights (so the
numbers move when you tune), then for the hand-labeled candidates reports:

  - NDCG@10 and NDCG@50  - over the judged pool, i.e. the labeled candidates
    ordered by the current ranker score. (We only label ~60 candidates, not the
    whole top-50, so NDCG here is the standard judged-pool proxy: "did the ranker
    put the highest-tier labeled candidates at the top of its order." Gain is the
    exponential 2^tier - 1.)
  - Kendall tau-b  - rank correlation between ranker score and your overall_tier
    (tau-b handles the many tier ties). Positive = agreement.
  - A per-candidate table (ranker rank vs your tier) with disagreements flagged,
    so mis-rankings are eye-visible.

Usage:
  python eval/validate_ranker.py [labels.csv]
Default labels path: eval/labels.csv  (fill eval/to_label.csv and save as that).
"""

from __future__ import annotations

import csv
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.features import extract_features  # noqa: E402
from src.io_utils import iter_candidates  # noqa: E402
from src.score import score  # noqa: E402

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LABELS = os.path.join(EVAL_DIR, "labels.csv")


def load_labels(path):
    """Return {candidate_id: tier} for rows with a filled integer overall_tier."""
    labels = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            cid = (row.get("candidate_id") or "").strip()
            raw = (row.get("overall_tier") or "").strip()
            if not cid or raw == "":
                continue
            try:
                labels[cid] = int(float(raw))
            except ValueError:
                print(f"  ! skipping {cid}: overall_tier={raw!r} not a number")
    return labels


def score_pool():
    """Score the full pool with current weights; return {cid: (score, rank)}."""
    rows = []
    for c in iter_candidates():
        rows.append((c["candidate_id"], score(extract_features(c))))
    rows.sort(key=lambda r: (-r[1], r[0]))
    return {cid: (sc, i + 1) for i, (cid, sc) in enumerate(rows)}


def dcg(gains):
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ordered_tiers, k):
    """NDCG@k over the judged pool already ordered by the ranker."""
    actual = ordered_tiers[:k]
    ideal = sorted(ordered_tiers, reverse=True)[:k]
    idcg = dcg(ideal)
    return dcg(actual) / idcg if idcg > 0 else 0.0


def kendall_tau_b(xs, ys):
    """Kendall tau-b (ties-aware) between two parallel sequences."""
    n = len(xs)
    concordant = discordant = tx = ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = xs[i] - xs[j]
            dy = ys[i] - ys[j]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                tx += 1
            elif dy == 0:
                ty += 1
            elif (dx > 0) == (dy > 0):
                concordant += 1
            else:
                discordant += 1
    n0 = n * (n - 1) / 2
    denom = math.sqrt((n0 - tx) * (n0 - ty))
    return (concordant - discordant) / denom if denom > 0 else 0.0


def main(labels_path):
    if not os.path.exists(labels_path):
        print(f"No labels file at {labels_path}.")
        print("Fill eval/to_label.csv (see RUBRIC.md) and save it as eval/labels.csv.")
        return
    labels = load_labels(labels_path)
    if not labels:
        print(f"{labels_path} has no filled overall_tier values yet - nothing to score.")
        print("Fill the overall_tier column per RUBRIC.md, then re-run.")
        return

    print(f"Scoring full pool with current weights for {len(labels)} labeled candidates...")
    pool = score_pool()

    judged = []  # (cid, tier, ranker_score, ranker_rank)
    missing = []
    for cid, tier in labels.items():
        if cid in pool:
            sc, rk = pool[cid]
            judged.append((cid, tier, sc, rk))
        else:
            missing.append(cid)
    if missing:
        print(f"  ! {len(missing)} labeled ids not found in pool: {missing[:5]}...")

    # Order judged candidates by the ranker (score desc) for NDCG.
    judged.sort(key=lambda r: -r[2])
    ordered_tiers = [t for _, t, _, _ in judged]

    ndcg10 = ndcg_at_k(ordered_tiers, 10)
    ndcg50 = ndcg_at_k(ordered_tiers, 50)
    tau = kendall_tau_b([sc for _, _, sc, _ in judged],
                        [t for _, t, _, _ in judged])

    print("\n" + "=" * 64)
    print(f"  labeled candidates : {len(judged)}")
    print(f"  NDCG@10            : {ndcg10:.4f}")
    print(f"  NDCG@50            : {ndcg50:.4f}")
    print(f"  Kendall tau-b      : {tau:+.4f}   (score vs your overall_tier)")
    print("=" * 64)

    # Per-candidate table, ordered by the ranker, disagreements flagged.
    # A row is flagged when the ranker and your tier point opposite ways:
    # high tier (>=3) but ranked deep, or low tier (<=1) but ranked shallow.
    print(f"\n{'rank':>6} {'tier':>4} {'score':>8}  {'flag':4} candidate_id")
    print("-" * 64)
    for cid, tier, sc, rk in sorted(judged, key=lambda r: r[3]):
        flag = ""
        if tier >= 3 and rk > 100:
            flag = "MISS"   # good candidate buried
        elif tier <= 1 and rk <= 50:
            flag = "FALSE"  # weak candidate ranked high
        print(f"{rk:>6} {tier:>4} {sc:>8.3f}  {flag:4} {cid}")
    print("-" * 64)
    print("MISS  = your tier>=3 but ranker rank>100 (we buried a good fit)")
    print("FALSE = your tier<=1 but ranker rank<=50  (we ranked junk highly)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LABELS)
