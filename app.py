"""
app.py — Redrob Ranker sandbox (Streamlit).

A lightweight, hosted-demo entry point (spec §10.5). It runs the *real* ranker
from src/ — not a reimplementation — on a small candidate sample, and exposes the
explainability: for every candidate you see the generated reasoning and an
expandable per-term breakdown of exactly how the score was composed.

Run locally:
    pip install -r requirements-sandbox.txt
    streamlit run app.py

Deploy: point a HuggingFace Space / Streamlit Cloud app at this repo, entrypoint
app.py. It loads data/sample_candidates.json by default and also accepts an
uploaded JSON array / JSONL of <=100 candidate records.
"""

from __future__ import annotations

import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.features import extract_features  # noqa: E402
from src.reasoning import make_reasoning  # noqa: E402
from src.score import WEIGHTS, _saturate_ml_years, fit_score, score  # noqa: E402

SAMPLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "data", "sample_candidates.json")

# Human labels for the fit terms (keys must match WEIGHTS).
TERM_LABELS = {
    "applied_ml_years": "Applied-ML years @ product cos (saturated)",
    "core_skill_score": "Core IR/ranking skills",
    "nice_skill_score": "Supporting ML skills",
    "band_fit": "Seniority-band fit (5-9 sweet spot)",
    "product_ratio": "Share of career at product cos",
    "shipped_system": "Shipped a ranking/search/rec system",
    "eval_signal": "Eval-framework signal (NDCG/MRR/A-B)",
}
GATE_LABELS = {
    "behavior_mult": "Behavior / availability",
    "location_fit": "Location fit",
    "impossibility": "Impossibility gate (honeypot)",
    "seniority_gate": "Seniority gate (over-band)",
}


def load_records(uploaded):
    if uploaded is not None:
        text = uploaded.getvalue().decode("utf-8")
        text = text.strip()
        if text.startswith("["):
            return json.loads(text)
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    with open(SAMPLE_PATH) as fh:
        return json.load(fh)


def fit_breakdown(f):
    """Per-term (raw, weight, weighted contribution) for the fit sum."""
    rows = []
    for key, w in WEIGHTS.items():
        v = f[key]
        if key == "applied_ml_years":
            raw_disp = f"{f[key]:.2f} → {_saturate_ml_years(f[key]):.2f}"
            contrib = w * _saturate_ml_years(f[key])
        else:
            num = 1.0 if v is True else (0.0 if v is False else float(v))
            raw_disp = ("yes" if v is True else "no") if isinstance(v, bool) else f"{num:.2f}"
            contrib = w * num
        rows.append((TERM_LABELS[key], raw_disp, w, contrib))
    return rows


def rank_records(records):
    scored = []
    for c in records:
        f = extract_features(c)
        scored.append((round(score(f), 6), c["candidate_id"], f, c))
    scored.sort(key=lambda r: (-r[0], r[1]))
    return scored


def main():
    st.set_page_config(page_title="Redrob Ranker", layout="wide")
    st.title("Redrob Ranker — explainable candidate ranking")
    st.caption("Feature-based scorer. Every number below is something you can say out "
               "loud about a candidate. Runs the real `src/` pipeline, CPU-only.")

    with st.sidebar:
        st.header("Input")
        uploaded = st.file_uploader("Candidate JSON array or JSONL (≤100)",
                                    type=["json", "jsonl"])
        st.markdown("No upload → uses `data/sample_candidates.json`.")
        top_n = st.slider("Show top N", 5, 100, 25)

    try:
        records = load_records(uploaded)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not parse input: {e}")
        return

    scored = rank_records(records)
    st.success(f"Ranked {len(scored)} candidates. Showing top {min(top_n, len(scored))}.")

    table = [{
        "rank": i,
        "candidate_id": cid,
        "score": f"{sc:.3f}",
        "title": f["_profile"].get("current_title", ""),
        "yoe": f["yoe"],
        "applied_ml_yrs": round(f["applied_ml_years"], 1),
    } for i, (sc, cid, f, c) in enumerate(scored[:top_n], 1)]
    st.dataframe(table, use_container_width=True, hide_index=True)

    st.subheader("Per-candidate explainability")
    for i, (sc, cid, f, c) in enumerate(scored[:top_n], 1):
        p = f["_profile"]
        with st.expander(f"#{i}  {cid} — {p.get('current_title','')}  ·  score {sc:.3f}"):
            st.markdown(f"**Reasoning:** {make_reasoning(f, rank=i)}")

            st.markdown("**Fit terms** (weighted contributions sum to `fit`):")
            st.table([
                {"term": label, "value": raw, "weight": w, "contribution": round(contrib, 3)}
                for (label, raw, w, contrib) in fit_breakdown(f)
            ])

            fit = fit_score(f)
            st.markdown(
                f"**Composition:**  `fit {fit:.2f}` − `penalties {f['penalties']:.2f}` "
                f"= `{max(0.0, fit - f['penalties']):.2f}`"
            )
            st.table([
                {"gate": GATE_LABELS[k], "multiplier": round(f[k], 3)}
                for k in GATE_LABELS
            ])
            gate_prod = f["behavior_mult"] * f["location_fit"] * f["impossibility"] * f["seniority_gate"]
            st.markdown(
                f"**Final** = max(0, fit − penalties) × (gates {gate_prod:.3f}) = "
                f"**{sc:.3f}**"
            )


if __name__ == "__main__":
    main()
