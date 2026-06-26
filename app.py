"""
app.py - Redrob Ranker explainability demo (Streamlit sandbox).

Design brief: make a skeptical reviewer conclude, in under a minute, two things -
(1) the ranking is correct, and (2) every score is auditable, term by term - which
is our whole thesis over black-box similarity.

It runs the REAL src/ pipeline (never a re-implementation): live on
data/sample_candidates.json for interactivity, and reads the committed
submission.csv for the actual top-100 deliverable. No ranker logic lives here.

Visual identity: native Streamlit theme - clean, intentional layout built purely
from native components (st.metric, st.tabs, bordered st.container, st.expander,
st.columns) with no custom CSS, colors, or web fonts.

Run:  pip install -r requirements-sandbox.txt && streamlit run app.py
"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter

import altair as alt
import pandas as pd
import streamlit as st

import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from src.classify import classify_role  # noqa: E402  (read-only, for blind masking)
from src.features import extract_features  # noqa: E402
from src.reasoning import _archetype, make_reasoning  # noqa: E402
from src.score import WEIGHTS, _saturate_core, _saturate_ml_years, fit_score, score  # noqa: E402

SAMPLE_PATH = os.path.join(HERE, "data", "sample_candidates.json")
SUBMISSION_PATH = os.path.join(HERE, "submission.csv")
POOL_DEMO_PATH = os.path.join(HERE, "data", "pool_demographics.json")
SHORTLIST_DEMO_PATH = os.path.join(HERE, "data", "shortlist_demographics.json")
RESULTS_PATH = os.path.join(HERE, "eval", "results.json")

FIT_LABELS = {
    "applied_ml_years": "Applied-ML years @ product cos",
    "core_skill_score": "Core IR / ranking skills",
    "nice_skill_score": "Supporting ML skills",
    "band_fit": "Seniority-band fit (5-9)",
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


@st.cache_data(show_spinner=False)
def load_demographics():
    """Read the precomputed pool + shortlist demographic caches (fairness tab).

    Built off-line by scripts/precompute_demographics.py from the full pool; the
    demo never scans the 487 MB pool itself. Returns (pool_doc, shortlist_doc) or
    (None, None) if the caches are absent.
    """
    if not (os.path.exists(POOL_DEMO_PATH) and os.path.exists(SHORTLIST_DEMO_PATH)):
        return None, None
    return json.load(open(POOL_DEMO_PATH)), json.load(open(SHORTLIST_DEMO_PATH))


@st.cache_data(show_spinner=False)
def load_results():
    """Read eval/results.json (the header numbers). Regenerated, never hardcoded.

    Built by eval/build_results.py from the live scoring, so the displayed metrics
    cannot drift from the ranker. Returns None if the file is absent.
    """
    if not os.path.exists(RESULTS_PATH):
        return None
    return json.load(open(RESULTS_PATH))


def breakdown(f):
    """Exact decomposition of src.score.score(f). Returns the audit pieces."""
    terms = []
    for key, w in WEIGHTS.items():
        v = f[key]
        if key == "applied_ml_years":
            num, raw = _saturate_ml_years(v), v
        elif key == "core_skill_score":
            num, raw = _saturate_core(v), v
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
POOL_COLOR, SHORT_COLOR = "#9AA0AA", "#3E7CB1"  # fairness charts: pool vs shortlist


# ---------- blind screening (display-only identity masking) ------------------
# Masking is cosmetic: it swaps human-identifying STRINGS for neutral placeholders
# that keep the auditable category (company type/size, school tier). It never
# changes ordering, scores, or any distribution - those come from the pipeline and
# from category counts, not from the masked strings.
def _company_label(job, blind):
    """Company string for a career entry, masked to 'Company [type, size]' if blind."""
    name = job.get("company") or "-"
    if not blind:
        return name
    _, is_product = classify_role(job)
    return f"Company [{'product' if is_product else 'services'}, {job.get('company_size') or '?'}]"


def _profile_company_label(p, blind):
    """Company string for a profile's current role (synthesises a job for classify)."""
    return _company_label({"title": p.get("current_title"), "industry": p.get("current_industry"),
                           "company": p.get("current_company"),
                           "company_size": p.get("current_company_size")}, blind)


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
    bars = enc.mark_bar(color=GATE_NEUTRAL)  # gates kept neutral - see brief
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


def dist_chart(rows, order):
    """Grouped horizontal bars: pool vs shortlist share for one dimension.

    `rows` is a long-form list of {category, series, share}; both series are
    normalized to percent so the 100 vs 100K scale difference does not matter.
    """
    df = pd.DataFrame(rows)
    enc = alt.Chart(df).encode(
        y=alt.Y("category:N", sort=order, title=None),
        x=alt.X("share:Q", title="share of group (%)"),
        yOffset=alt.YOffset("series:N", sort=["Pool", "Shortlist"]),
        color=alt.Color("series:N", sort=["Pool", "Shortlist"],
                        scale=alt.Scale(domain=["Pool", "Shortlist"],
                                        range=[POOL_COLOR, SHORT_COLOR]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip("series:N", title="group"),
                 alt.Tooltip("category:N", title="bucket"),
                 alt.Tooltip("share:Q", title="share", format=".1f")],
    )
    bars = enc.mark_bar()
    text = enc.mark_text(align="left", dx=3, baseline="middle").encode(
        text=alt.Text("share:Q", format=".0f"))
    return (bars + text).properties(height=max(150, 44 * len(order)))


# ---------- evidence renderers (native tables / text) -----------------------
def equation_text(bd):
    gates = " ".join(f'× {c["short"]} {c["mult"]:.2f}' for c in bd["cascade"])
    return (f'final = max(0, fit {bd["fit"]:.2f} − pen {bd["pen"]:.2f}) '
            f'{gates} = {bd["final"]:.2f}')


def career_df(c, blind=False):
    rows = [{
        "title": j.get("title"),
        "company": _company_label(j, blind),
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
        {"signal": "last active", "value": s.get("last_active_date", "-")},
        {"signal": "response rate", "value": f'{s.get("recruiter_response_rate", 0):.0%}'},
        {"signal": "relocate", "value": "yes" if s.get("willing_to_relocate") else "no"},
        {"signal": "location", "value": f'{p.get("location")}, {p.get("country")}'},
    ])


# ---------- panels ----------------------------------------------------------
def detail_panel(item, blind=False):
    c, f, rank = item["cand"], item["f"], item["rank"]
    p = c["profile"]
    bd = breakdown(f)

    with st.container(border=True):
        head, scorecol = st.columns([3, 1])
        with head:
            st.caption(f'RANK {rank} / 50  ·  {item["archetype"]}')
            st.subheader(p.get("current_title"), anchor=False)
            st.caption(f'{c["candidate_id"]} · {_profile_company_label(p, blind)} · '
                       f'{p.get("years_of_experience")} yrs experience')
        with scorecol:
            st.metric("Final score", f'{bd["final"]:.2f}')
        st.markdown(f'> {make_reasoning(f, rank=rank)}')

    st.markdown("**1 · How fit was built** - additive, weighted")
    st.altair_chart(fit_chart(bd), use_container_width=True)

    st.markdown("**2 · Gates applied** - multiplicative")
    st.altair_chart(gate_chart(bd), use_container_width=True)
    st.code(equation_text(bd))

    st.markdown("**3 · The evidence**")
    with st.expander("Career history", expanded=True):
        st.dataframe(career_df(c, blind), hide_index=True, use_container_width=True)
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
def view_ranked(ranked, blind=False):
    max_score = float(ranked[0]["score"]) + 0.5
    fc = st.columns([3, 2], gap="medium")
    lo, hi = fc[0].slider("Score range", 0.0, max_score, (0.0, max_score), step=0.5)
    topn = fc[1].slider("Show top N", 5, len(ranked), min(20, len(ranked)))
    st.divider()

    filt = [it for it in ranked if lo <= it["score"] <= hi][:topn]
    left, right = st.columns([5, 7], gap="medium")
    with left:
        st.markdown("**Ranked candidates** - select one to audit")
        if not filt:
            st.info("No candidates match this score range. Widen it to see results.")
            return
        df = pd.DataFrame([{
            "rank": it["rank"],
            "candidate": it["cand"]["profile"].get("current_title"),
            "company": _profile_company_label(it["cand"]["profile"], blind),
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
        detail_panel(chosen, blind)


def view_traps(ranked, blind=False):
    by_id = {it["cand"]["candidate_id"]: it for it in ranked}
    fit, stuf, hp = by_id[TRAP_IDS["fit"]], by_id[TRAP_IDS["stuffer"]], by_id[TRAP_IDS["honeypot"]]

    st.subheader("The traps the pool is built around - and what the ranker does",
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
                  "Career is Project Manager / Sales / Support - yet the skills list "
                  "shows Pinecone, FAISS, Embeddings. applied-ML = 0, so fit ≈ 0.", False)
    with c3:
        trap_card(hp, "Honeypot · collapsed by gate",
                  "“Kubeflow” listed for 59 months on a 24-month career - internally "
                  "impossible. The impossibility gate multiplies the score to near zero.", False)

    st.subheader("Why - the receipts", anchor=False)
    a, b = st.columns(2, gap="large")
    with a:
        st.markdown("**Keyword stuffer - skills listed vs. career**")
        st.dataframe(skills_df(stuf["cand"], limit=8), hide_index=True, use_container_width=True)
        st.dataframe(career_df(stuf["cand"], blind), hide_index=True, use_container_width=True)
        st.code(equation_text(breakdown(stuf["f"])))
    with b:
        st.markdown("**Honeypot - the impossible duration**")
        st.dataframe(skills_df(hp["cand"], limit=8), hide_index=True, use_container_width=True)
        yexp = hp["cand"]["profile"].get("years_of_experience", 0)
        st.caption(f'Total experience: {yexp} yrs (~{int(yexp * 12)} months) - '
                   f'yet a skill above is listed for longer.')
        st.code(equation_text(breakdown(hp["f"])))


# JD-driven category we EXPECT to be over-represented in each dimension, plus the
# plain-language reason it is legitimate. Education is handled separately: tier is
# not a scoring feature, so any skew there is emergent, not optimized for.
_LEGIT = {
    "yoe": ("5 to 9 (JD band)",
            "the JD targets the 5 to 9 year band and a seniority gate down-weights above it"),
    "company_type": ("Product",
                     "the JD explicitly prefers product experience over services/consulting (DECISIONS #3)"),
    "location": ("India - preferred hub",
                 "the JD prefers India-based and relocatable candidates"),
    "availability": ("Open, active",
                     "the behavior gate down-weights candidates who are unavailable or inactive, as the JD asks"),
}


def fairness_interpretation(dim_key, merged):
    """Return (kind, sentence) describing the skew, generated from the numbers.

    kind is one of 'legitimate' (JD-driven), 'emergent' (not a scoring feature),
    or 'watch' (the most over-represented bucket is not the JD-driven one).
    """
    over = max(merged, key=lambda r: r["delta"])
    under = min(merged, key=lambda r: r["delta"])

    def phr(r):
        return (f'{r["category"]} ({r["short"]:.0f}% of the shortlist vs '
                f'{r["pool"]:.0f}% of the pool)')

    if dim_key == "education":
        t1 = next((r for r in merged if r["category"] == "Tier 1"), over)
        return ("emergent",
                "The scorer never reads education tier - it is not a feature in src/ "
                "(confirm with the blind-screening toggle above). Any concentration here "
                "is an emergent correlation with the career signals we do score, not a "
                f"pedigree preference. Here {phr(t1)}.")

    exp_cat, why = _LEGIT[dim_key]
    if over["category"] == exp_cat:
        return ("legitimate",
                f"Legitimate, JD-driven concentration: {phr(over)}, because {why}. "
                f"Under-represented: {phr(under)}.")
    return ("watch",
            f"Most over-represented bucket is {phr(over)}, which is not the JD-driven "
            f"bucket ({exp_cat}) - worth an honest look before relying on it.")


def view_fairness(blind):
    pool, short = load_demographics()
    st.subheader("Pool vs shortlist - audit the top-100 against the full pool", anchor=False)
    if not pool or not short:
        st.info("Demographic caches not found. Run "
                "`python scripts/precompute_demographics.py` to build them.")
        return

    cands = short["candidates"]
    n_short = len(cands)
    n_pool = pool["pool_size"]
    st.markdown(
        f"How the {n_short} submitted candidates compare to all {n_pool:,} in the pool, "
        "across five dimensions. Shares are normalized, so the 100-vs-100K scale gap does "
        "not distort the comparison. Where a skew is JD-driven we say so; where it is not "
        "something the ranker optimizes for, we say that too.")
    badge = {"legitimate": st.success, "emergent": st.info, "watch": st.warning}

    for key, dim in pool["dimensions"].items():
        order = dim["order"]
        pcounts = dim["counts"]
        scounts = Counter(c["cat"][key] for c in cands)
        merged, rows = [], []
        for cat in order:
            ps = 100.0 * pcounts.get(cat, 0) / n_pool if n_pool else 0.0
            ss = 100.0 * scounts.get(cat, 0) / n_short if n_short else 0.0
            merged.append({"category": cat, "pool": ps, "short": ss, "delta": ss - ps})
            rows.append({"category": cat, "series": "Pool", "share": ps})
            rows.append({"category": cat, "series": "Shortlist", "share": ss})

        st.markdown(f"**{dim['label']}**")
        cchart, ctable = st.columns([3, 2], gap="medium")
        with cchart:
            st.altair_chart(dist_chart(rows, order), use_container_width=True)
        with ctable:
            tdf = pd.DataFrame([{
                "bucket": m["category"], "shortlist %": m["short"],
                "pool %": m["pool"], "vs pool (pp)": m["delta"],
            } for m in merged])
            st.dataframe(tdf, hide_index=True, use_container_width=True,
                         column_config={
                             "shortlist %": st.column_config.NumberColumn(format="%.0f"),
                             "pool %": st.column_config.NumberColumn(format="%.0f"),
                             "vs pool (pp)": st.column_config.NumberColumn(format="%+.0f"),
                         })
        kind, line = fairness_interpretation(key, merged)
        badge[kind](line)
        st.divider()

    st.subheader("The 100 submitted candidates", anchor=False)
    st.caption(("Blind screening ON - names, companies and institutions are masked; "
                "ranks, buckets and every chart above are identical."
                if blind else
                "Blind screening OFF - toggle it at the top to mask names, companies "
                "and institutions and confirm nothing below the strings changes."))
    sdf = pd.DataFrame([{
        "rank": c["rank"],
        "candidate": (f"Candidate #{c['rank']}" if blind else (c.get("name") or "-")),
        "company": (f"Company [{'product' if c['cat']['company_type'] == 'Product' else 'services'}, "
                    f"{c.get('company_size') or '?'}]" if blind else (c.get("company") or "-")),
        "company type": c["cat"]["company_type"],
        "institution": (f"Institution [{c['cat']['education']}]" if blind
                        else (c.get("institution") or "-")),
        "edu tier": c["cat"]["education"],
        "yoe band": c["cat"]["yoe"],
        "location": c["cat"]["location"],
        "availability": c["cat"]["availability"],
    } for c in cands])
    st.dataframe(sdf, hide_index=True, use_container_width=True, height=440,
                 column_config={"rank": st.column_config.NumberColumn("#", width="small")})


def view_top100():
    sub = load_submission()
    st.subheader("The committed deliverable - submission.csv (full 100K pool)",
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
               "(their records aren't in the sandbox) - the reasoning embeds the cited facts.")
    st.dataframe(df, hide_index=True, use_container_width=True, height=560,
                 column_config={
                     "rank": st.column_config.NumberColumn("#", width="small"),
                     "score": st.column_config.NumberColumn("score", format="%.3f"),
                     "reasoning": st.column_config.TextColumn("reasoning", width="large"),
                 })


# ---------- header metrics --------------------------------------------------
_TAU_LABEL = "Kendall τ"  # display label; results.json keeps it ASCII


def render_header(res):
    """Two grouped metric strips: ranking quality (numbers) + constraints (pass pills).

    All values come from eval/results.json so they track the live scoring. The two
    groups make different claims - measured quality vs rule-compliance - so they are
    rendered differently: quality as plain numbers with a baseline->current story,
    constraints as green pass states. No 0-100% gauges (NDCG and tau live on
    different scales, so a percent dial would mislead).
    """
    q, cons, val = res["quality"], res["constraints"], res["validation"]

    st.caption(
        f"Ranking-quality scores are measured on a {val['n_labels']}-profile "
        "hand-labeled validation set - a local tuning proxy, not the hidden "
        "competition score. Constraints are checked on the full 100K pool.")

    st.markdown("**Ranking quality**")
    qcols = st.columns(3)
    for col, key in zip(qcols, ("ndcg10", "ndcg50", "tau")):
        m = q[key]
        sign = "+" if key == "tau" else ""
        label = _TAU_LABEL if key == "tau" else m["label"]
        col.metric(label, f"{sign}{m['current']:.2f}")
        col.caption(f"{m['sub']}  \n{sign}{m['baseline']:.2f} "
                    f"→ {sign}{m['current']:.2f} after tuning")

    st.markdown("**Constraints met**")
    ccols = st.columns(3)

    with ccols[0]:
        st.markdown("Honeypots in top-100")
        hp, seeded = cons["honeypots_top100"], cons["honeypots_seeded_approx"]
        if hp == 0:
            st.success(f"{hp} of ~{seeded} reached the top-100", icon="✅")
        else:
            st.error(f"{hp} impossible profiles in top-100", icon="⚠️")
        st.caption("impossible profiles caught by the consistency gate")

    with ccols[1]:
        st.markdown("Runtime, 100K pool")
        rt, budget = cons["runtime_s"], cons["runtime_budget_s"]
        if rt <= budget:
            st.success(f"~{rt:.0f} s, within the {budget // 60}-min budget", icon="✅")
        else:
            st.error(f"{rt:.0f} s exceeds the {budget // 60}-min budget", icon="⚠️")
        st.caption("full 100K pool, CPU-only, no network")

    with ccols[2]:
        st.markdown("Valid submission")
        if cons["validator_passed"]:
            st.success("validator: passed", icon="✅")
        else:
            st.error("validator: failed", icon="⚠️")
        ds, n = cons["distinct_scores"], cons["top_n"]
        if ds == n:
            st.success(f"{ds} distinct scores", icon="✅")
        else:
            st.warning(f"{ds}/{n} distinct scores", icon="⚠️")


# ---------- app -------------------------------------------------------------
def main():
    st.set_page_config(page_title="Redrob Ranker - explainable ranking",
                       layout="wide", initial_sidebar_state="collapsed")

    st.title("Redrob Ranker")
    st.caption("INTELLIGENT CANDIDATE DISCOVERY & RANKING")
    st.markdown("**Score what someone built, not what they listed** - "
                "every number below traces to a fact in the profile.")
    st.divider()

    res = load_results()
    if res:
        render_header(res)
    else:
        st.caption("Run `python eval/build_results.py` to populate the metrics header.")
    st.divider()

    ranked = load_ranked()
    blind = st.toggle(
        "Blind screening - mask names, companies and institutions",
        value=False, key="blind",
        help="Display-only. Hides identifying strings wherever they appear so you can "
             "confirm the ranking and the distributions do not change when identity is "
             "masked. It never alters scores, ranks, or any chart.")
    st.divider()

    t1, t2, t3, t4 = st.tabs(["Ranked list & audit", "How it handles traps",
                              "Fairness audit", "Actual top-100"])
    with t1:
        view_ranked(ranked, blind)
    with t2:
        view_traps(ranked, blind)
    with t3:
        view_fairness(blind)
    with t4:
        view_top100()


if __name__ == "__main__":
    main()
