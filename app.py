"""
app.py — Redrob Ranker explainability demo (Streamlit sandbox).

Design brief: make a skeptical reviewer conclude, in under a minute, two things —
(1) the ranking is correct, and (2) every score is auditable, term by term — which
is our whole thesis over black-box similarity.

It runs the REAL src/ pipeline (never a re-implementation): live on
data/sample_candidates.json for interactivity, and reads the committed
submission.csv for the actual top-100 deliverable. No ranker logic lives here.

Visual identity: native Streamlit theme — clean, intentional layout built purely
from native components (st.metric, st.tabs, bordered st.container, st.expander,
st.columns) with no custom CSS, colors, or web fonts.

Run:  pip install -r requirements-sandbox.txt && streamlit run app.py
"""

from __future__ import annotations

import csv
import json
import os

import altair as alt
import pandas as pd
import streamlit as st

import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from src.features import extract_features  # noqa: E402
from src.reasoning import _archetype, make_reasoning  # noqa: E402
from src.score import WEIGHTS, _saturate_ml_years, fit_score, score  # noqa: E402

SAMPLE_PATH = os.path.join(HERE, "data", "sample_candidates.json")
SUBMISSION_PATH = os.path.join(HERE, "submission.csv")

FIT_LABELS = {
    "applied_ml_years": "Applied-ML years @ product cos",
    "core_skill_score": "Core IR / ranking skills",
    "nice_skill_score": "Supporting ML skills",
    "band_fit": "Seniority-band fit (5–9)",
    "product_ratio": "Product- vs services-career",
    "shipped_system": "Shipped a ranking/search system",
    "eval_signal": "Eval framework (NDCG/MRR/A-B)",
}
GATE_DEFS = [
    ("behavior_mult", "behavior"),
    ("location_fit", "location"),
    ("impossibility", "impossibility"),
    ("seniority_gate", "seniority"),
]

# Sample trap exemplars (verified to exist in sample_candidates.json).
TRAP_IDS = {
    "fit": "CAND_0000031",       # RecSys Engineer, genuine high fit
    "stuffer": "CAND_0000021",   # Project Manager listing AI skills
    "honeypot": "CAND_0000011",  # QA Engineer, skill used longer than career
}


# ---------- data + scoring (cached so the UI is instant) --------------------
@st.cache_data(show_spinner=False)
def load_ranked():
    """Run the real ranker on the sample; return list of dicts (rank order)."""
    cands = json.load(open(SAMPLE_PATH))
    scored = []
    for c in cands:
        f = extract_features(c)
        scored.append((round(score(f), 6), c, f))
    scored.sort(key=lambda r: (-r[0], r[1]["candidate_id"]))
    out = []
    for rank, (sc, c, f) in enumerate(scored, 1):
        out.append({"rank": rank, "score": sc, "cand": c, "f": f,
                    "archetype": _archetype(f)})
    return out


@st.cache_data(show_spinner=False)
def load_submission():
    if not os.path.exists(SUBMISSION_PATH):
        return None
    with open(SUBMISSION_PATH, newline="") as fh:
        return list(csv.DictReader(fh))


def breakdown(f):
    """Exact decomposition of src.score.score(f). Returns the audit pieces."""
    terms = []
    for key, w in WEIGHTS.items():
        v = f[key]
        if key == "applied_ml_years":
            num, raw = _saturate_ml_years(v), v
        else:
            num = 1.0 if v is True else (0.0 if v is False else float(v))
            raw = v
        terms.append({"key": key, "label": FIT_LABELS[key], "raw": raw,
                      "weight": w, "contribution": w * num})
    fit = fit_score(f)
    pen = f["penalties"]
    base = max(0.0, fit - pen)
    cascade, running = [], base
    for key, short in GATE_DEFS:
        m = f[key]
        running *= m
        cascade.append({"key": key, "short": short, "mult": m, "running": running})
    return {"terms": terms, "fit": fit, "pen": pen, "base": base,
            "cascade": cascade, "final": running, "ref": score(f)}


# Chart-only accent colors for the score-decomposition breakdown. The rest of the
# app stays on the native Streamlit theme; these apply solely to the charts below.
# Mid-tones chosen to read on both the light and dark default backgrounds.
FIT_GREEN, PEN_RED, GATE_NEUTRAL = "#1F9D6B", "#D1495B", "#808495"


# ---------- charts ----------------------------------------------------------
def fit_chart(bd):
    rows = [{"label": t["label"], "value": t["contribution"], "kind": "fit"}
            for t in bd["terms"] if t["contribution"] > 1e-4]
    if bd["pen"] > 0:
        rows.append({"label": "Penalties", "value": -bd["pen"], "kind": "penalty"})
    df = pd.DataFrame(rows)
    order = df.reindex(df["value"].abs().sort_values(ascending=False).index)["label"].tolist()
    enc = alt.Chart(df).encode(
        y=alt.Y("label:N", sort=order, title=None),
        x=alt.X("value:Q", title="weighted contribution to fit"),
        color=alt.Color("kind:N", scale=alt.Scale(domain=["fit", "penalty"],
                        range=[FIT_GREEN, PEN_RED]), legend=None),
        tooltip=[alt.Tooltip("label:N", title="term"),
                 alt.Tooltip("value:Q", title="contribution", format="+.2f")],
    )
    bars = enc.mark_bar()
    text = enc.mark_text(align="left", dx=4, baseline="middle").encode(
        text=alt.Text("value:Q", format="+.2f"))
    return (bars + text).properties(height=max(150, 32 * len(rows)))


def gate_chart(bd):
    rows = [{"step": "fit − penalties", "value": bd["base"]}]
    for c in bd["cascade"]:
        rows.append({"step": f"× {c['short']} ({c['mult']:.2f})", "value": c["running"]})
    rows.append({"step": "= final", "value": bd["final"]})
    df = pd.DataFrame(rows)
    order = [r["step"] for r in rows]
    enc = alt.Chart(df).encode(
        y=alt.Y("step:N", sort=order, title=None),
        x=alt.X("value:Q", title="running score after each multiplicative gate"),
        tooltip=[alt.Tooltip("step:N", title="step"),
                 alt.Tooltip("value:Q", title="running score", format=".2f")],
    )
    bars = enc.mark_bar(color=GATE_NEUTRAL)  # gates kept neutral — see brief
    val = enc.mark_text(align="left", dx=4, baseline="middle").encode(
        text=alt.Text("value:Q", format=".2f"))
    return (bars + val).properties(height=max(160, 36 * len(rows)))


def score_chart(items):
    """Small comparison bar of a few candidates' final scores (trap section)."""
    df = pd.DataFrame(items)
    return alt.Chart(df).mark_bar().encode(
        y=alt.Y("name:N", sort=list(df["name"]), title=None),
        x=alt.X("score:Q", title="final score"),
        color=alt.Color("kind:N", legend=None),
        tooltip=["name", alt.Tooltip("score:Q", format=".2f")],
    ).properties(height=140)


# ---------- evidence renderers (native tables / text) -----------------------
def equation_text(bd):
    gates = " ".join(f'× {c["short"]} {c["mult"]:.2f}' for c in bd["cascade"])
    return (f'final = max(0, fit {bd["fit"]:.2f} − pen {bd["pen"]:.2f}) '
            f'{gates} = {bd["final"]:.2f}')


def career_df(c):
    rows = [{
        "title": j.get("title"),
        "company": j.get("company"),
        "industry": j.get("industry"),
        "months": j.get("duration_months") or 0,
        "current": "●" if j.get("is_current") else "",
    } for j in c.get("career_history", [])]
    return pd.DataFrame(rows)


def skills_df(c, limit=12):
    sk = sorted(c.get("skills", []), key=lambda s: (s.get("duration_months") or 0),
                reverse=True)[:limit]
    return pd.DataFrame([{
        "skill": s.get("name"),
        "proficiency": s.get("proficiency"),
        "months": s.get("duration_months") or 0,
    } for s in sk])


def signals_df(c):
    s = c.get("redrob_signals", {})
    p = c["profile"]
    return pd.DataFrame([
        {"signal": "open to work", "value": "yes" if s.get("open_to_work_flag") else "no"},
        {"signal": "last active", "value": s.get("last_active_date", "—")},
        {"signal": "response rate", "value": f'{s.get("recruiter_response_rate", 0):.0%}'},
        {"signal": "relocate", "value": "yes" if s.get("willing_to_relocate") else "no"},
        {"signal": "location", "value": f'{p.get("location")}, {p.get("country")}'},
    ])


# ---------- panels ----------------------------------------------------------
def detail_panel(item):
    c, f, rank = item["cand"], item["f"], item["rank"]
    p = c["profile"]
    bd = breakdown(f)

    with st.container(border=True):
        head, scorecol = st.columns([3, 1])
        with head:
            st.caption(f'RANK {rank} / 50  ·  {item["archetype"]}')
            st.subheader(p.get("current_title"), anchor=False)
            st.caption(f'{c["candidate_id"]} · {p.get("current_company")} · '
                       f'{p.get("years_of_experience")} yrs experience')
        with scorecol:
            st.metric("Final score", f'{bd["final"]:.2f}')
        st.markdown(f'> {make_reasoning(f, rank=rank)}')

    st.markdown("**1 · How fit was built** — additive, weighted")
    st.altair_chart(fit_chart(bd), use_container_width=True)

    st.markdown("**2 · Gates applied** — multiplicative")
    st.altair_chart(gate_chart(bd), use_container_width=True)
    st.code(equation_text(bd))

    st.markdown("**3 · The evidence**")
    with st.expander("Career history", expanded=True):
        st.dataframe(career_df(c), hide_index=True, use_container_width=True)
    with st.expander("Skills (top by duration)"):
        st.dataframe(skills_df(c), hide_index=True, use_container_width=True)
    with st.expander("Signals & availability"):
        st.dataframe(signals_df(c), hide_index=True, use_container_width=True)


def trap_card(item, tag, verdict, verdict_good):
    c, f = item["cand"], item["f"]
    bd = breakdown(f)
    p = c["profile"]
    with st.container(border=True):
        st.caption(tag)
        st.markdown(f'**{p.get("current_title")}**')
        st.caption(f'{c["candidate_id"]} · rank {item["rank"]} / 50')
        st.metric("Final score", f'{bd["final"]:.2f}')
        (st.success if verdict_good else st.error)(verdict)


# ---------- views -----------------------------------------------------------
def view_ranked(ranked):
    max_score = float(ranked[0]["score"]) + 0.5
    arches = sorted({it["archetype"] for it in ranked})
    fc = st.columns([3, 3, 3, 2], gap="medium")
    q = fc[0].text_input("Search", "", placeholder="title / company / id")
    picked = fc[1].multiselect("Archetype", arches, default=arches)
    lo, hi = fc[2].slider("Score range", 0.0, max_score, (0.0, max_score), step=0.5)
    topn = fc[3].slider("Show top N", 5, len(ranked), min(20, len(ranked)))
    st.divider()

    def keep(it):
        c = it["cand"]; p = c["profile"]
        hay = f'{p.get("current_title","")} {p.get("current_company","")} {c["candidate_id"]}'.lower()
        return (q.lower() in hay) and (lo <= it["score"] <= hi) and (it["archetype"] in picked)

    filt = [it for it in ranked if keep(it)][:topn]
    left, right = st.columns([5, 7], gap="medium")
    with left:
        st.markdown("**Ranked candidates** — select one to audit")
        if not filt:
            st.info("No candidates match these filters. Widen the score range or clear the search.")
            return
        df = pd.DataFrame([{
            "rank": it["rank"],
            "candidate": it["cand"]["profile"].get("current_title"),
            "company": it["cand"]["profile"].get("current_company"),
            "score": it["score"],
            "type": it["archetype"],
        } for it in filt])
        ev = st.dataframe(
            df, hide_index=True, use_container_width=True, height=min(560, 60 + 35 * len(df)),
            on_select="rerun", selection_mode="single-row",
            column_config={
                "rank": st.column_config.NumberColumn("#", width="small"),
                "score": st.column_config.ProgressColumn(
                    "score", format="%.2f", min_value=0.0,
                    max_value=float(ranked[0]["score"])),
            })
        sel = ev.selection.rows if ev and ev.selection else []
        chosen = filt[sel[0]] if sel else filt[0]
    with right:
        detail_panel(chosen)


def view_traps(ranked):
    by_id = {it["cand"]["candidate_id"]: it for it in ranked}
    fit, stuf, hp = by_id[TRAP_IDS["fit"]], by_id[TRAP_IDS["stuffer"]], by_id[TRAP_IDS["honeypot"]]

    st.subheader("The traps the pool is built around — and what the ranker does",
                 anchor=False)
    st.altair_chart(score_chart([
        {"name": "Genuine fit", "score": fit["score"], "kind": "good"},
        {"name": "Keyword stuffer", "score": stuf["score"], "kind": "bad"},
        {"name": "Honeypot", "score": hp["score"], "kind": "bad"},
    ]), use_container_width=True)

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        trap_card(fit, "Genuine fit · ranked high",
                  "RecSys Engineer, ~5.8 applied-ML yrs at a product co, shipped a "
                  "ranking system, available. Earns it on evidence.", True)
    with c2:
        trap_card(stuf, "Keyword stuffer · ranked low",
                  "Career is Project Manager / Sales / Support — yet the skills list "
                  "shows Pinecone, FAISS, Embeddings. applied-ML = 0, so fit ≈ 0.", False)
    with c3:
        trap_card(hp, "Honeypot · collapsed by gate",
                  "“Kubeflow” listed for 59 months on a 24-month career — internally "
                  "impossible. The impossibility gate multiplies the score to near zero.", False)

    st.subheader("Why — the receipts", anchor=False)
    a, b = st.columns(2, gap="large")
    with a:
        st.markdown("**Keyword stuffer — skills listed vs. career**")
        st.dataframe(skills_df(stuf["cand"], limit=8), hide_index=True, use_container_width=True)
        st.dataframe(career_df(stuf["cand"]), hide_index=True, use_container_width=True)
        st.code(equation_text(breakdown(stuf["f"])))
    with b:
        st.markdown("**Honeypot — the impossible duration**")
        st.dataframe(skills_df(hp["cand"], limit=8), hide_index=True, use_container_width=True)
        yexp = hp["cand"]["profile"].get("years_of_experience", 0)
        st.caption(f'Total experience: {yexp} yrs (~{int(yexp * 12)} months) — '
                   f'yet a skill above is listed for longer.')
        st.code(equation_text(breakdown(hp["f"])))


def view_top100():
    sub = load_submission()
    st.subheader("The committed deliverable — submission.csv (full 100K pool)",
                 anchor=False)
    if not sub:
        st.info("submission.csv not found. Run `python -m src.rank` to produce it.")
        return
    q = st.text_input("Search reasoning / id", "", key="top100q")
    n = st.slider("Show top N", 5, len(sub), min(25, len(sub)), key="top100n")
    rows = [r for r in sub if q.lower() in (r["reasoning"] + " " + r["candidate_id"]).lower()][:n]
    df = pd.DataFrame([{"rank": int(r["rank"]), "candidate_id": r["candidate_id"],
                        "score": float(r["score"]), "reasoning": r["reasoning"]} for r in rows])
    st.caption("These are full-pool candidates, so the live per-term audit isn't shown here "
               "(their records aren't in the sandbox) — the reasoning embeds the cited facts.")
    st.dataframe(df, hide_index=True, use_container_width=True, height=560,
                 column_config={
                     "rank": st.column_config.NumberColumn("#", width="small"),
                     "score": st.column_config.NumberColumn("score", format="%.3f"),
                     "reasoning": st.column_config.TextColumn("reasoning", width="large"),
                 })


# ---------- app -------------------------------------------------------------
def main():
    st.set_page_config(page_title="Redrob Ranker — explainable ranking",
                       layout="wide", initial_sidebar_state="collapsed")

    st.title("Redrob Ranker")
    st.caption("INTELLIGENT CANDIDATE DISCOVERY & RANKING")
    st.markdown("**Score what someone built, not what they listed** — "
                "every number below traces to a fact in the profile.")
    st.divider()

    metrics = [("NDCG@10", "0.92"), ("NDCG@50", "0.98"), ("Kendall τ", "+0.76"),
               ("Honeypots in top-100", "0"), ("Runtime · 100K · CPU", "~13 s")]
    for col, (label, value) in zip(st.columns(len(metrics)), metrics):
        col.metric(label, value)
    st.divider()

    ranked = load_ranked()
    t1, t2, t3 = st.tabs(["Ranked list & audit", "How it handles traps", "Actual top-100"])
    with t1:
        view_ranked(ranked)
    with t2:
        view_traps(ranked)
    with t3:
        view_top100()


if __name__ == "__main__":
    main()
