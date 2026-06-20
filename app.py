"""
app.py — Redrob Ranker explainability demo (Streamlit sandbox).

Design brief: make a skeptical reviewer conclude, in under a minute, two things —
(1) the ranking is correct, and (2) every score is auditable, term by term — which
is our whole thesis over black-box similarity.

It runs the REAL src/ pipeline (never a re-implementation): live on
data/sample_candidates.json for interactivity, and reads the committed
submission.csv for the actual top-100 deliverable. No ranker logic lives here.

Visual identity: an "evidence ledger" — fit terms build up (green), penalties
subtract (red), multiplicative gates cut down (slate) to the final score.

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

# ---- palette (mirrors .streamlit/config.toml + DECISIONS) -------------------
INK, PAPER, MUTED, LINE = "#161B26", "#F4F5F7", "#5B6472", "#E4E7EC"
ACCENT, FIT, PENALTY, GATE, GATE_CUT = "#0E7C86", "#1F9D6B", "#D1495B", "#3D5A80", "#C2410C"

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

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"], .stMarkdown, p, li, label, .stSelectbox, .stSlider { font-family: 'Inter', sans-serif; }
h1,h2,h3,h4 { font-family: 'Space Grotesk', sans-serif; letter-spacing:-0.01em; color:#161B26; }
.block-container { padding-top: 1.2rem; max-width: 1280px; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height:0; }

/* ---- masthead ---- */
.masthead { border-bottom: 2px solid #161B26; padding-bottom: 14px; margin-bottom: 4px; }
.wordmark { font-family:'Space Grotesk'; font-weight:700; font-size:30px; color:#161B26; letter-spacing:-0.02em; }
.wordmark .dot { color:#0E7C86; }
.eyebrow { font-family:'IBM Plex Mono'; font-size:12px; letter-spacing:0.14em; text-transform:uppercase; color:#5B6472; }
.thesis { font-family:'Space Grotesk'; font-weight:500; font-size:15px; color:#3D4250; margin-top:2px; }

/* ---- metric strip ---- */
.metric-grid { display:flex; gap:10px; margin:16px 0 6px; flex-wrap:wrap; }
.metric { flex:1; min-width:120px; background:#fff; border:1px solid #E4E7EC; border-radius:10px;
          padding:12px 14px; border-left:3px solid #0E7C86; }
.metric .v { font-family:'IBM Plex Mono'; font-weight:600; font-size:24px; color:#161B26; line-height:1.1; }
.metric .l { font-family:'IBM Plex Mono'; font-size:10.5px; letter-spacing:0.08em; text-transform:uppercase; color:#5B6472; margin-top:4px; }

/* ---- panels / cards ---- */
.panel { background:#fff; border:1px solid #E4E7EC; border-radius:12px; padding:18px 20px; margin-bottom:14px; }
.panel h3 { margin:0 0 2px; font-size:18px; }
.cand-id { font-family:'IBM Plex Mono'; font-size:12px; color:#5B6472; }
.rankbadge { display:inline-block; font-family:'IBM Plex Mono'; font-weight:600; font-size:13px; color:#0E7C86;
             border:1px solid #0E7C86; border-radius:6px; padding:1px 8px; }
.finalscore { font-family:'IBM Plex Mono'; font-weight:600; font-size:34px; color:#161B26; }
.eq { font-family:'IBM Plex Mono'; font-size:12.5px; color:#3D4250; background:#F4F5F7; border:1px solid #E4E7EC;
      border-radius:8px; padding:9px 11px; overflow-x:auto; white-space:nowrap; }
.eq b { color:#1F9D6B; } .eq .pen { color:#D1495B; } .eq .gate { color:#3D5A80; } .eq .fin { color:#0E7C86; font-weight:600; }
.reason { font-size:14px; line-height:1.55; color:#262B36; border-left:3px solid #0E7C86; padding-left:12px; }
.kv { font-size:13px; color:#262B36; line-height:1.7; }
.kv .k { font-family:'IBM Plex Mono'; font-size:11px; color:#5B6472; text-transform:uppercase; letter-spacing:0.06em; }
.chip { display:inline-block; font-family:'IBM Plex Mono'; font-size:11.5px; padding:2px 8px; border-radius:20px;
        margin:2px 4px 2px 0; border:1px solid #E4E7EC; background:#F8FAFB; color:#262B36; }
.sectlabel { font-family:'IBM Plex Mono'; font-size:11px; letter-spacing:0.12em; text-transform:uppercase;
             color:#5B6472; margin:14px 0 6px; }
.verdict { font-family:'Space Grotesk'; font-weight:600; font-size:14px; margin-top:8px; }
.v-good { color:#1F9D6B; } .v-bad { color:#D1495B; }
.trapcard { background:#fff; border:1px solid #E4E7EC; border-radius:12px; padding:16px 18px; height:100%; }
.trapcard.bad { border-top:4px solid #D1495B; } .trapcard.good { border-top:4px solid #1F9D6B; }
.trap-tag { font-family:'IBM Plex Mono'; font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:#5B6472; }
</style>
"""


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


# ---------- charts ----------------------------------------------------------
def fit_chart(bd):
    rows = [{"label": t["label"], "value": t["contribution"], "kind": "Fit"}
            for t in bd["terms"] if t["contribution"] > 1e-4]
    if bd["pen"] > 0:
        rows.append({"label": "Penalties", "value": -bd["pen"], "kind": "Penalty"})
    df = pd.DataFrame(rows)
    order = df.reindex(df["value"].abs().sort_values(ascending=False).index)["label"].tolist()
    enc = alt.Chart(df).encode(
        y=alt.Y("label:N", sort=order, title=None,
                axis=alt.Axis(labelFontSize=12, labelLimit=240, labelColor=INK)),
        x=alt.X("value:Q", title="weighted contribution to fit",
                axis=alt.Axis(titleFontSize=11, titleColor=MUTED, grid=True, gridColor=LINE)),
        color=alt.Color("kind:N", scale=alt.Scale(domain=["Fit", "Penalty"],
                        range=[FIT, PENALTY]), legend=None),
        tooltip=[alt.Tooltip("label:N", title="term"),
                 alt.Tooltip("value:Q", title="contribution", format="+.2f")],
    )
    bars = enc.mark_bar(height=20, cornerRadius=3)
    text = enc.mark_text(align="left", dx=4, baseline="middle", font="IBM Plex Mono",
                         fontSize=11, color=INK).encode(
        text=alt.Text("value:Q", format="+.2f"),
        x=alt.X("value:Q"))
    return (bars + text).properties(height=max(150, 30 * len(rows))).configure_view(
        stroke=None).configure_axis(domainColor=LINE)


def gate_chart(bd):
    rows = [{"step": "fit − penalties", "value": bd["base"], "type": "base", "tag": ""}]
    for c in bd["cascade"]:
        cut = c["mult"] < 0.999
        rows.append({"step": f"× {c['short']}", "value": c["running"],
                     "type": "cut" if cut else "gate", "tag": f"×{c['mult']:.2f}"})
    rows.append({"step": "= final", "value": bd["final"], "type": "final", "tag": ""})
    df = pd.DataFrame(rows)
    order = [r["step"] for r in rows]
    enc = alt.Chart(df).encode(
        y=alt.Y("step:N", sort=order, title=None,
                axis=alt.Axis(labelFontSize=12, labelFont="IBM Plex Mono", labelColor=INK)),
        x=alt.X("value:Q", title="running score after each multiplicative gate",
                axis=alt.Axis(titleFontSize=11, titleColor=MUTED, grid=True, gridColor=LINE)),
        color=alt.Color("type:N", scale=alt.Scale(
            domain=["base", "gate", "cut", "final"],
            range=[GATE, GATE, GATE_CUT, ACCENT]), legend=None),
        tooltip=[alt.Tooltip("step:N"), alt.Tooltip("value:Q", format=".2f"),
                 alt.Tooltip("tag:N", title="multiplier")],
    )
    bars = enc.mark_bar(height=20, cornerRadius=3)
    val = enc.mark_text(align="left", dx=4, baseline="middle", font="IBM Plex Mono",
                        fontSize=11, color=INK).encode(text=alt.Text("value:Q", format=".2f"))
    mult = enc.mark_text(align="left", dx=4, baseline="middle", font="IBM Plex Mono",
                         fontSize=11, fontWeight=600, color=GATE_CUT).encode(
        text=alt.Text("tag:N"))
    return (bars + val).properties(height=max(160, 34 * len(rows))).configure_view(
        stroke=None).configure_axis(domainColor=LINE)


def score_chart(items):
    """Small comparison bar of a few candidates' final scores (trap section)."""
    df = pd.DataFrame(items)
    return alt.Chart(df).mark_bar(height=26, cornerRadius=4).encode(
        y=alt.Y("name:N", sort=list(df["name"]), title=None,
                axis=alt.Axis(labelFontSize=12, labelColor=INK)),
        x=alt.X("score:Q", title="final score", axis=alt.Axis(grid=True, gridColor=LINE, titleColor=MUTED)),
        color=alt.Color("kind:N", scale=alt.Scale(domain=["good", "bad"], range=[FIT, PENALTY]), legend=None),
        tooltip=["name", alt.Tooltip("score:Q", format=".2f")],
    ).properties(height=120).configure_view(stroke=None).configure_axis(domainColor=LINE)


# ---------- rendering helpers ----------------------------------------------
def equation_html(bd):
    g = bd["cascade"]
    gates = " ".join(
        f'<span class="gate">× {c["short"]} {c["mult"]:.2f}</span>' for c in g)
    return (f'<div class="eq">final = max(0, <b>fit {bd["fit"]:.2f}</b> − '
            f'<span class="pen">pen {bd["pen"]:.2f}</span>) {gates} '
            f'= <span class="fin">{bd["final"]:.2f}</span></div>')


def career_html(c):
    out = []
    for j in c.get("career_history", []):
        cur = ' <span style="color:#0E7C86">·current</span>' if j.get("is_current") else ""
        out.append(f'<div class="kv">{j.get("title")} · <span style="color:#5B6472">'
                   f'{j.get("company")} · {j.get("industry")} · {j.get("duration_months") or 0}mo</span>{cur}</div>')
    return "".join(out)


def skills_html(c, limit=12):
    sk = sorted(c.get("skills", []), key=lambda s: (s.get("duration_months") or 0), reverse=True)[:limit]
    return "".join(f'<span class="chip">{s.get("name")} · {s.get("proficiency")} · '
                   f'{s.get("duration_months") or 0}mo</span>' for s in sk)


def signals_html(c):
    s = c.get("redrob_signals", {})
    p = c["profile"]
    pairs = [
        ("open to work", "yes" if s.get("open_to_work_flag") else "no"),
        ("last active", s.get("last_active_date", "—")),
        ("response rate", f'{s.get("recruiter_response_rate", 0):.0%}'),
        ("relocate", "yes" if s.get("willing_to_relocate") else "no"),
        ("location", f'{p.get("location")}, {p.get("country")}'),
    ]
    return "".join(f'<span class="chip"><span style="color:#5B6472">{k}</span> {v}</span>' for k, v in pairs)


def detail_panel(item):
    c, f, rank = item["cand"], item["f"], item["rank"]
    p = c["profile"]
    bd = breakdown(f)
    st.markdown(
        f'<div class="panel"><span class="rankbadge">rank {rank} / 50</span>'
        f'<h3 style="margin-top:8px">{p.get("current_title")}</h3>'
        f'<div class="cand-id">{c["candidate_id"]} · {p.get("current_company")} · '
        f'{p.get("years_of_experience")} yrs · {item["archetype"]}</div>'
        f'<div style="margin-top:10px"><span class="finalscore">{bd["final"]:.2f}</span>'
        f'<span style="color:#5B6472;font-size:13px"> final score</span></div>'
        f'<div style="margin-top:8px" class="reason">{make_reasoning(f, rank=rank)}</div></div>',
        unsafe_allow_html=True)

    st.markdown('<div class="sectlabel">1 · How fit was built (additive, weighted)</div>',
                unsafe_allow_html=True)
    st.altair_chart(fit_chart(bd), use_container_width=True)

    st.markdown('<div class="sectlabel">2 · Gates applied (multiplicative)</div>',
                unsafe_allow_html=True)
    st.altair_chart(gate_chart(bd), use_container_width=True)
    st.markdown(equation_html(bd), unsafe_allow_html=True)

    st.markdown('<div class="sectlabel">3 · The evidence</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kv"><span class="k">career</span></div>{career_html(c)}',
                unsafe_allow_html=True)
    st.markdown(f'<div class="kv" style="margin-top:8px"><span class="k">skills</span></div>'
                f'{skills_html(c)}', unsafe_allow_html=True)
    st.markdown(f'<div class="kv" style="margin-top:8px"><span class="k">signals</span></div>'
                f'{signals_html(c)}', unsafe_allow_html=True)


def trap_card(item, kind, tag, verdict, verdict_good):
    c, f = item["cand"], item["f"]
    bd = breakdown(f)
    p = c["profile"]
    cls = "good" if verdict_good else "bad"
    vcls = "v-good" if verdict_good else "v-bad"
    st.markdown(
        f'<div class="trapcard {cls}"><div class="trap-tag">{tag}</div>'
        f'<h3 style="margin:6px 0 2px">{p.get("current_title")}</h3>'
        f'<div class="cand-id">{c["candidate_id"]} · rank {item["rank"]} / 50</div>'
        f'<div style="margin:10px 0"><span class="finalscore" style="font-size:28px">{bd["final"]:.2f}</span>'
        f'<span style="color:#5B6472;font-size:12px"> score</span></div>'
        f'<div class="verdict {vcls}">{verdict}</div></div>',
        unsafe_allow_html=True)


# ---------- views -----------------------------------------------------------
def view_ranked(ranked):
    with st.sidebar:
        st.markdown('<div class="sectlabel">Filters</div>', unsafe_allow_html=True)
        q = st.text_input("Search title / company / id", "")
        lo, hi = st.slider("Score range", 0.0, float(ranked[0]["score"]) + 0.5,
                           (0.0, float(ranked[0]["score"]) + 0.5), step=0.5)
        arches = sorted({it["archetype"] for it in ranked})
        picked = st.multiselect("Archetype", arches, default=arches)
        topn = st.slider("Show top N", 5, len(ranked), min(20, len(ranked)))

    def keep(it):
        c = it["cand"]; p = c["profile"]
        hay = f'{p.get("current_title","")} {p.get("current_company","")} {c["candidate_id"]}'.lower()
        return (q.lower() in hay) and (lo <= it["score"] <= hi) and (it["archetype"] in picked)

    filt = [it for it in ranked if keep(it)][:topn]
    left, right = st.columns([5, 7], gap="medium")
    with left:
        st.markdown('<div class="sectlabel">Ranked candidates — select one to audit</div>',
                    unsafe_allow_html=True)
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
    st.markdown('<div class="sectlabel">The traps the pool is built around — and what the ranker does</div>',
                unsafe_allow_html=True)
    st.altair_chart(score_chart([
        {"name": "Genuine fit", "score": fit["score"], "kind": "good"},
        {"name": "Keyword stuffer", "score": stuf["score"], "kind": "bad"},
        {"name": "Honeypot", "score": hp["score"], "kind": "bad"},
    ]), use_container_width=True)

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        trap_card(fit, "fit", "Genuine fit · ranked high",
                  "RecSys Engineer, ~5.8 applied-ML yrs at a product co, shipped a "
                  "ranking system, available. Earns it on evidence.", True)
    with c2:
        trap_card(stuf, "stuffer", "Keyword stuffer · ranked low",
                  "Career is Project Manager / Sales / Support — yet the skills list "
                  "shows Pinecone, FAISS, Embeddings. applied-ML = 0, so fit ≈ 0.", False)
    with c3:
        trap_card(hp, "honeypot", "Honeypot · collapsed by gate",
                  "“Kubeflow” listed for 59 months on a 24-month career — internally "
                  "impossible. The impossibility gate multiplies the score to near zero.", False)

    st.markdown('<div class="sectlabel">Why — the receipts</div>', unsafe_allow_html=True)
    a, b = st.columns(2, gap="medium")
    with a:
        st.markdown('<div class="kv"><span class="k">stuffer: skills listed vs career</span></div>',
                    unsafe_allow_html=True)
        st.markdown(skills_html(stuf["cand"], limit=8), unsafe_allow_html=True)
        st.markdown(career_html(stuf["cand"]), unsafe_allow_html=True)
        st.markdown(equation_html(breakdown(stuf["f"])), unsafe_allow_html=True)
    with b:
        st.markdown('<div class="kv"><span class="k">honeypot: the impossible duration</span></div>',
                    unsafe_allow_html=True)
        st.markdown(skills_html(hp["cand"], limit=8), unsafe_allow_html=True)
        st.markdown(f'<div class="kv">total experience: '
                    f'{hp["cand"]["profile"].get("years_of_experience")} yrs '
                    f'(~{int(hp["cand"]["profile"].get("years_of_experience",0)*12)} months)</div>',
                    unsafe_allow_html=True)
        st.markdown(equation_html(breakdown(hp["f"])), unsafe_allow_html=True)


def view_top100():
    sub = load_submission()
    st.markdown('<div class="sectlabel">The committed deliverable — submission.csv (full 100K pool)</div>',
                unsafe_allow_html=True)
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
                       layout="wide", initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)

    st.markdown(
        '<div class="masthead">'
        '<div class="eyebrow">Intelligent Candidate Discovery &amp; Ranking</div>'
        '<div class="wordmark">Redrob Ranker<span class="dot">.</span></div>'
        '<div class="thesis">Score what someone built, not what they listed — '
        'every number below traces to a fact in the profile.</div></div>',
        unsafe_allow_html=True)

    st.markdown(
        '<div class="metric-grid">'
        '<div class="metric"><div class="v">0.92</div><div class="l">NDCG@10</div></div>'
        '<div class="metric"><div class="v">0.98</div><div class="l">NDCG@50</div></div>'
        '<div class="metric"><div class="v">+0.76</div><div class="l">Kendall τ</div></div>'
        '<div class="metric"><div class="v">0</div><div class="l">honeypots in top-100</div></div>'
        '<div class="metric"><div class="v">~13s</div><div class="l">100K · CPU only</div></div>'
        '</div>', unsafe_allow_html=True)

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
