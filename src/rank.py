"""
rank.py — End-to-end orchestrator: pool -> scores -> top 100 -> submission.csv.

Phase 6 of PLAN.md. This is the deliverable pipeline:

    load 100K  ->  extract_features  ->  score  ->  sort  ->  top 100
               ->  assign ranks 1..100  ->  make_reasoning  ->  write CSV

Ordering contract (must match validate_submission.py):
  - sort by final score DESCENDING;
  - ties broken by candidate_id ASCENDING;
  - scores written non-increasing down the file.

We round the score to 6 dp and sort on the rounded value so the written column is
exactly what the tie-break was computed against (no float-vs-display drift).

CSV is written with the stdlib csv module (QUOTE_MINIMAL): reasoning strings hold
commas and quotes, and the writer escapes them so the column count stays 4.

Run:  python -m src.rank   (or scripts/run.sh, which also times + measures RAM)
"""

from __future__ import annotations

import csv
import os
import sys
import time

from .features import extract_features
from .honeypot import impossibility_score
from .io_utils import iter_candidates
from .reasoning import make_reasoning
from .score import score

TOP_N = 100
HEADER = ["candidate_id", "rank", "score", "reasoning"]
SCORE_DP = 6
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "submission.csv")


def rank_pool(in_path=None):
    """Score the whole pool; return the top-N rows as (cid, score, features).

    Single streaming pass; we retain only (rounded_score, cid, features) so peak
    memory is the feature dicts, not raw JSON. Sorted by (-score, cid).
    """
    scored = []
    n = 0
    for c in iter_candidates(in_path):
        n += 1
        f = extract_features(c)
        scored.append((round(score(f), SCORE_DP), c["candidate_id"], f))
    scored.sort(key=lambda r: (-r[0], r[1]))
    return scored[:TOP_N], n


def honeypot_scan(top_rows):
    """Stage-3 literal check: impossible profiles (<=0.5) in the FINAL top-N.

    This is a different set than 'top-N by fit' — gates can pull a high-fit
    honeypot down or leave it up, so we scan the actually-submitted rows.
    """
    flagged = []
    for _, cid, f in top_rows:
        imp = f["impossibility"]
        if imp <= 0.5:
            flagged.append((cid, imp))
    return flagged


def write_submission(top_rows, out_path):
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)  # QUOTE_MINIMAL: quotes any field with , " or newline
        w.writerow(HEADER)
        for rank, (sc, cid, f) in enumerate(top_rows, 1):
            w.writerow([cid, rank, f"{sc:.{SCORE_DP}f}", make_reasoning(f, rank=rank)])


def main(in_path=None, out_path=DEFAULT_OUT):
    t0 = time.time()
    top_rows, n_pool = rank_pool(in_path)
    t_score = time.time() - t0

    flagged = honeypot_scan(top_rows)
    write_submission(top_rows, out_path)
    dt = time.time() - t0

    distinct = len({r[0] for r in top_rows})
    print(f"scored {n_pool} candidates in {t_score:.1f}s")
    print(f"wrote {len(top_rows)} rows -> {out_path}")
    print(f"score spread: {top_rows[0][0]:.4f} (rank 1) .. "
          f"{top_rows[-1][0]:.4f} (rank {len(top_rows)}); "
          f"{distinct} distinct scores")
    print(f"HONEYPOT SCAN (final top-{TOP_N} by final score, impossibility<=0.5): "
          f"{len(flagged)} flagged")
    if flagged:
        for cid, imp in flagged:
            print(f"   !! {cid} impossibility={imp:.3f}")
    print(f"total wall-clock: {dt:.1f}s")
    return 0 if not flagged else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
