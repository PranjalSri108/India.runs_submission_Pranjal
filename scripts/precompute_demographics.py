#!/usr/bin/env python3
"""
precompute_demographics.py - one-off demo cache for the Fairness Audit tab.

Streams the full candidate pool ONCE (read-only) and writes two small JSON caches
the Streamlit demo reads at runtime:

  data/pool_demographics.json      per-dimension category counts for the whole pool
  data/shortlist_demographics.json the 100 submitted candidates, each tagged with
                                   the same categories (+ identity strings so the
                                   blind-screening toggle has something to mask)

Why this is a separate script (and not part of the demo's load path):
  - The demo must start instantly and must run on a host that does NOT ship the
    487 MB pool (Streamlit Cloud / HF Spaces), so the pool stats are precomputed.
  - It is NOT on the submission reproduce path. It never imports or calls the
    scorer (src.score / src.rank); it only reads raw profile fields and reuses
    src.classify for product-vs-services, so it cannot perturb the ranking or
    submission.csv. Re-run it only when the pool or submission.csv changes.

Run (from repo root):  python scripts/precompute_demographics.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from datetime import date

# Make `src` importable whether run as a script or a module.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from src.classify import classify_role  # noqa: E402  (read-only, no scoring)
from src.io_utils import iter_candidates  # noqa: E402
from src.vocab import PREFERRED_CITIES  # noqa: E402

TODAY = date(2026, 6, 18)  # matches src.features.TODAY (competition "now")

POOL_OUT = os.path.join(_REPO_ROOT, "data", "pool_demographics.json")
SHORTLIST_OUT = os.path.join(_REPO_ROOT, "data", "shortlist_demographics.json")
SUBMISSION = os.path.join(_REPO_ROOT, "submission.csv")


# --- category functions: ONE source of truth for both pool and shortlist ----
# Every function returns a label that is present in its dimension's `order` list,
# so pool aggregates and per-candidate shortlist tags are always comparable.

YOE_ORDER = ["0 to 2", "2 to 5", "5 to 9 (JD band)", "9 to 15", "15+"]


def cat_yoe(c):
    y = c["profile"].get("years_of_experience") or 0
    if y < 2:
        return "0 to 2"
    if y < 5:
        return "2 to 5"
    if y <= 9:
        return "5 to 9 (JD band)"
    if y < 15:
        return "9 to 15"
    return "15+"


EDU_ORDER = ["Tier 1", "Tier 2", "Tier 3", "Tier 4", "Unknown", "No data"]
_TIER_LABEL = {"tier_1": "Tier 1", "tier_2": "Tier 2", "tier_3": "Tier 3",
               "tier_4": "Tier 4", "unknown": "Unknown"}
_TIER_RANK = {"tier_1": 1, "tier_2": 2, "tier_3": 3, "tier_4": 4, "unknown": 5}


def best_education(c):
    """Return (tier_label, institution_name) for the candidate's best-ranked school."""
    best, best_r = None, 99
    for e in c.get("education") or []:
        r = _TIER_RANK.get(e.get("tier"), 99)
        if r < best_r:
            best, best_r = e, r
    if best is None:
        return "No data", None
    return _TIER_LABEL.get(best.get("tier"), "Unknown"), best.get("institution")


def cat_education(c):
    return best_education(c)[0]


LOC_ORDER = ["India - preferred hub", "India - other", "Outside India"]


def cat_location(c):
    p = c["profile"]
    loc = (p.get("location") or "").lower() + " " + (p.get("country") or "").lower()
    if any(city in loc for city in PREFERRED_CITIES):
        return "India - preferred hub"
    if "india" in loc:
        return "India - other"
    return "Outside India"


COTYPE_ORDER = ["Product", "Services / consulting"]


def _current_job(c):
    for j in c.get("career_history") or []:
        if j.get("is_current"):
            return j
    p = c["profile"]
    return {"title": p.get("current_title"), "industry": p.get("current_industry"),
            "company": p.get("current_company"),
            "company_size": p.get("current_company_size")}


def cat_company_type(c):
    _, is_product = classify_role(_current_job(c))
    return "Product" if is_product else "Services / consulting"


AVAIL_ORDER = ["Open, active", "Open, recent", "Open, stale", "Not open to work"]


def cat_availability(c):
    sig = c.get("redrob_signals", {})
    if not sig.get("open_to_work_flag"):
        return "Not open to work"
    la = sig.get("last_active_date")
    days = None
    if la:
        try:
            days = (TODAY - date.fromisoformat(la)).days
        except ValueError:
            days = None
    if days is None:
        return "Open, stale"
    if days <= 90:
        return "Open, active"
    if days <= 180:
        return "Open, recent"
    return "Open, stale"


# key, human label, ordered categories, categorizer
DIMENSIONS = [
    ("yoe", "Years of experience", YOE_ORDER, cat_yoe),
    ("education", "Education tier", EDU_ORDER, cat_education),
    ("location", "Location", LOC_ORDER, cat_location),
    ("company_type", "Current company type", COTYPE_ORDER, cat_company_type),
    ("availability", "Availability", AVAIL_ORDER, cat_availability),
]


def _read_shortlist_ids():
    with open(SUBMISSION, newline="") as fh:
        return {r["candidate_id"]: int(r["rank"]) for r in csv.DictReader(fh)}


def main():
    rank_by_id = _read_shortlist_ids()
    pool_counts = {key: Counter() for key, _, _, _ in DIMENSIONS}
    shortlist = {}
    n = 0

    for c in iter_candidates():
        n += 1
        cats = {key: fn(c) for key, _, _, fn in DIMENSIONS}
        for key in pool_counts:
            pool_counts[key][cats[key]] += 1
        cid = c["candidate_id"]
        if cid in rank_by_id:
            tier_label, inst = best_education(c)
            p = c["profile"]
            shortlist[cid] = {
                "rank": rank_by_id[cid],
                "candidate_id": cid,
                "name": p.get("anonymized_name"),
                "title": p.get("current_title"),
                "company": p.get("current_company"),
                "company_size": p.get("current_company_size"),
                "institution": inst,
                "cat": cats,
            }

    pool_doc = {
        "pool_size": n,
        "generated_from": "data/candidates.jsonl",
        "dimensions": {
            key: {"label": label, "order": order,
                  "counts": {cat: pool_counts[key].get(cat, 0) for cat in order}}
            for key, label, order, _ in DIMENSIONS
        },
    }
    shortlist_doc = {
        "shortlist_size": len(shortlist),
        "candidates": sorted(shortlist.values(), key=lambda r: r["rank"]),
    }

    with open(POOL_OUT, "w") as fh:
        json.dump(pool_doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    with open(SHORTLIST_OUT, "w") as fh:
        json.dump(shortlist_doc, fh, indent=1, sort_keys=True)
        fh.write("\n")

    print(f"scanned {n} candidates; tagged {len(shortlist)} shortlisted")
    print(f"wrote {POOL_OUT}")
    print(f"wrote {SHORTLIST_OUT}")
    for key, label, order, _ in DIMENSIONS:
        top = max(order, key=lambda cat: pool_counts[key].get(cat, 0))
        print(f"  {label:22s} pool mode: {top} "
              f"({100 * pool_counts[key].get(top, 0) / n:.0f}%)")


if __name__ == "__main__":
    main()
