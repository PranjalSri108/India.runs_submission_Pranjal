"""
sample_for_labeling.py - Draw a stratified ~60-candidate sample to hand-label.

Phase 3 of PLAN.md. We have no ground truth and only 3 real submissions, so we
build our own validation set: a small stratified sample, hand-labeled against
eval/RUBRIC.md, used to tune weights (Phase 4) without burning submissions.

The make-or-break concern is labeling UX: opening raw JSON for 60 candidates
guarantees burnout. So every row carries a compact, human-readable DIGEST
(profile / career / skills / signals) - you should be able to label a row in
~90 seconds without ever touching the JSON.

Strata (~60 total):
  - 25  top by final score          (incl. the over-band seniors to adjudicate)
  - 10  high core_skill_score but low applied_ml_years (keyword-stuffer hunt)
  - 10  mid-score                    (middle of the positive-score distribution)
  - 15  random                       (catch fits the vocabulary missed)

Anti-bias measures:
  - The ranker's score, global rank, and the stratum each row came from live in
    trailing `_`-prefixed columns AND the row order is shuffled, so position
    cannot telegraph the ranker's opinion (esp. the stuffer stratum).
  - Sampling is seeded, so the emitted to_label.csv is reproducible.

Output: eval/to_label.csv - fill in overall_tier/fit_tier/avail/deciding_factor
per RUBRIC.md, then save as eval/labels.csv for validate_ranker.py.
"""

from __future__ import annotations

import csv
import os
import random
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.features import extract_features  # noqa: E402
from src.io_utils import iter_candidates  # noqa: E402
from src.score import score  # noqa: E402

SEED = 42
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(EVAL_DIR, "to_label.csv")

N_TOP = 25
N_STUFFER = 10
N_MID = 10
N_RANDOM = 15

HEADER = [
    # --- you fill these (see RUBRIC.md) ---
    "candidate_id", "overall_tier", "fit_tier", "avail", "deciding_factor",
    # --- human-readable digest (label from these, not the JSON) ---
    "profile", "career_history", "top_skills", "signals",
    # --- trailing: the ranker's opinion, kept out of view while you judge ---
    "_ranker_score", "_ranker_rank", "_stratum",
]


def _fmt_career(c):
    lines = []
    for j in c.get("career_history", []):
        title = j.get("title") or "?"
        company = j.get("company") or "?"
        industry = j.get("industry") or "?"
        mo = j.get("duration_months") or 0
        cur = " *current*" if j.get("is_current") else ""
        lines.append(f"{title} @ {company} [{industry}] ({mo}mo){cur}")
    return "\n".join(lines)


def _fmt_skills(c, top_n=8):
    skills = sorted(
        c.get("skills", []),
        key=lambda s: (s.get("duration_months") or 0),
        reverse=True,
    )
    shown = skills[:top_n]
    parts = [
        f"{s.get('name')}({s.get('proficiency')}, {s.get('duration_months') or 0}mo)"
        for s in shown
    ]
    line = "; ".join(parts)
    if len(skills) > top_n:
        line += f"  (+{len(skills) - top_n} more)"
    return line


def _fmt_profile(c):
    p = c["profile"]
    return f"{p.get('current_title')} | {p.get('years_of_experience')} yrs total"


def _fmt_signals(c):
    s = c.get("redrob_signals", {})
    p = c["profile"]
    otw = "Y" if s.get("open_to_work_flag") else "N"
    relo = "Y" if s.get("willing_to_relocate") else "N"
    loc = f"{p.get('location')}, {p.get('country')}"
    return (
        f"open_to_work={otw} | last_active={s.get('last_active_date')} | "
        f"recruiter_response_rate={s.get('recruiter_response_rate')} | "
        f"willing_to_relocate={relo} | location={loc}"
    )


def build():
    # Score the whole pool once, then assign a stable global rank.
    rows = []  # (candidate_id, score, features, raw_candidate)
    for c in iter_candidates():
        f = extract_features(c)
        rows.append((c["candidate_id"], score(f), f, c))
    # Rank by score desc, candidate_id asc (same tie-break as the validator).
    rows.sort(key=lambda r: (-r[1], r[0]))
    rank = {r[0]: i + 1 for i, r in enumerate(rows)}

    rng = random.Random(SEED)
    chosen = OrderedDict()  # candidate_id -> stratum

    def add(cid, stratum):
        if cid not in chosen:
            chosen[cid] = stratum

    # 1) Top by final score (includes the over-band seniors to adjudicate).
    for r in rows[:N_TOP]:
        add(r[0], "top")

    # 2) Keyword-stuffer hunt: strong core skills, ~no applied ML at product cos.
    stuffer = [r for r in rows
               if r[2]["applied_ml_years"] < 1.0 and r[0] not in chosen]
    stuffer.sort(key=lambda r: (-r[2]["core_skill_score"], r[0]))
    for r in stuffer[:N_STUFFER]:
        add(r[0], "high_core_low_ml")

    # 3) Mid-score: middle of the *positive*-score distribution.
    pos = [r for r in rows if r[1] > 0 and r[0] not in chosen]
    pos.sort(key=lambda r: r[1])  # ascending
    if pos:
        lo, hi = int(len(pos) * 0.40), int(len(pos) * 0.60)
        band = pos[lo:hi] or pos
        for r in rng.sample(band, min(N_MID, len(band))):
            add(r[0], "mid")

    # 4) Random from everyone not already chosen.
    remaining = [r for r in rows if r[0] not in chosen]
    for r in rng.sample(remaining, min(N_RANDOM, len(remaining))):
        add(r[0], "random")

    # Build output rows, then shuffle so neither rank nor stratum biases labels.
    by_id = {r[0]: r for r in rows}
    out = []
    for cid, stratum in chosen.items():
        _, sc, _, c = by_id[cid]
        out.append({
            "candidate_id": cid,
            "overall_tier": "", "fit_tier": "", "avail": "", "deciding_factor": "",
            "profile": _fmt_profile(c),
            "career_history": _fmt_career(c),
            "top_skills": _fmt_skills(c),
            "signals": _fmt_signals(c),
            "_ranker_score": round(sc, 4),
            "_ranker_rank": rank[cid],
            "_stratum": stratum,
        })
    rng.shuffle(out)

    with open(OUT_PATH, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        w.writerows(out)

    # Report strata counts (to stderr-ish stdout) for a sanity check.
    counts = {}
    for v in chosen.values():
        counts[v] = counts.get(v, 0) + 1
    print(f"Wrote {len(out)} rows to {OUT_PATH}")
    for k in ("top", "high_core_low_ml", "mid", "random"):
        print(f"  {k:18s}: {counts.get(k, 0)}")


if __name__ == "__main__":
    build()
