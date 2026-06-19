"""
validate_submission.py — Format validator for submission.csv.

NOTE: the competition ships its own validator "copied in" here; until we have that
exact file, this implements the documented contract (PLAN.md checklist §242-244)
so we fail loudly on anything the real one would reject. It is intentionally
strict about the things that silently corrupt a CSV (column count, escaping).

Checks:
  - header is exactly: candidate_id,rank,score,reasoning
  - exactly 100 data rows, each with exactly 4 columns (CSV-parsed, so quoted
    reasonings with commas/quotes are fine — a row with the wrong column count
    means broken escaping);
  - ranks are 1..100, each exactly once;
  - scores are non-increasing down the file, ties broken by candidate_id ascending;
  - scores are differentiated (not all identical);
  - candidate_ids match CAND_XXXXXXX, are unique, and all exist in the pool;
  - every reasoning is non-empty.

Usage: python validate_submission.py [submission.csv] [candidates_path]
Prints "Submission is valid." and exits 0 on success; otherwise prints the
failures and exits 1.
"""

from __future__ import annotations

import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.io_utils import iter_candidates  # noqa: E402

EXPECTED_HEADER = ["candidate_id", "rank", "score", "reasoning"]
N_ROWS = 100
ID_RE = re.compile(r"^CAND_\d{7}$")


def validate(sub_path, candidates_path=None):
    errors = []

    with open(sub_path, newline="") as fh:
        rows = list(csv.reader(fh))

    if not rows:
        return ["submission.csv is empty"]

    header, data = rows[0], rows[1:]
    if header != EXPECTED_HEADER:
        errors.append(f"header is {header!r}, expected {EXPECTED_HEADER!r}")

    if len(data) != N_ROWS:
        errors.append(f"expected {N_ROWS} data rows, found {len(data)}")

    # Every row must parse to exactly 4 columns; otherwise escaping is broken.
    for i, r in enumerate(data, 1):
        if len(r) != 4:
            errors.append(f"row {i} has {len(r)} columns (expected 4) — "
                          f"likely an unescaped comma/quote in reasoning: {r!r}")

    # If column counts are wrong, the rest of the checks are unreliable.
    if errors and any("columns" in e for e in errors):
        return errors

    ids, ranks, scores = [], [], []
    for i, (cid, rank, sc, reasoning) in enumerate(data, 1):
        ids.append(cid)
        if not ID_RE.match(cid):
            errors.append(f"row {i}: candidate_id {cid!r} not CAND_XXXXXXX")
        try:
            ranks.append(int(rank))
        except ValueError:
            errors.append(f"row {i}: rank {rank!r} not an integer")
        try:
            scores.append(float(sc))
        except ValueError:
            errors.append(f"row {i}: score {sc!r} not a float")
        if not reasoning.strip():
            errors.append(f"row {i}: empty reasoning")

    # ranks 1..100 each once
    if sorted(ranks) != list(range(1, N_ROWS + 1)):
        errors.append("ranks are not exactly 1..100 each once")

    # unique ids
    if len(set(ids)) != len(ids):
        dupes = {x for x in ids if ids.count(x) > 1}
        errors.append(f"duplicate candidate_ids: {sorted(dupes)}")

    # scores non-increasing; ties broken by candidate_id ascending
    if len(scores) == len(ids) == len(data):
        for i in range(1, len(scores)):
            if scores[i] > scores[i - 1] + 1e-12:
                errors.append(f"row {i + 1}: score {scores[i]} > previous "
                              f"{scores[i - 1]} (not non-increasing)")
            elif abs(scores[i] - scores[i - 1]) <= 1e-12 and ids[i] < ids[i - 1]:
                errors.append(f"row {i + 1}: tie not broken by candidate_id asc "
                              f"({ids[i - 1]} then {ids[i]})")

    # scores differentiated
    if len(set(scores)) <= 1:
        errors.append("scores are not differentiated (all identical)")

    # all ids exist in the pool
    pool_ids = {c["candidate_id"] for c in iter_candidates(candidates_path)}
    missing = [cid for cid in ids if cid not in pool_ids]
    if missing:
        errors.append(f"{len(missing)} candidate_ids not found in pool: {missing[:5]}")

    return errors


def main():
    sub = sys.argv[1] if len(sys.argv) > 1 else "submission.csv"
    cands = sys.argv[2] if len(sys.argv) > 2 else None
    errors = validate(sub, cands)
    if errors:
        print(f"INVALID — {len(errors)} problem(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("Submission is valid.")
    sys.exit(0)


if __name__ == "__main__":
    main()
