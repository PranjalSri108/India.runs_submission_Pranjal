<div align="center">

# 🎯 Redrob Ranker

### Intelligent Candidate Discovery & Ranking

**100,000 profiles → the 100 best matches** for a Senior AI Engineer role —
scored by *what each person built*, not what they listed.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)]()
[![CPU only](https://img.shields.io/badge/compute-CPU--only-success)]()
[![No network](https://img.shields.io/badge/ranking-offline-success)]()
[![Runtime](https://img.shields.io/badge/100K%20pool-~13s-brightgreen)]()
[![Streamlit](https://img.shields.io/badge/demo-Streamlit-FF4B4B?logo=streamlit)]()
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)]()

*“The right answer is not finding candidates whose skills section contains the most AI keywords.
That's a trap we've explicitly built into the dataset.”* — the job description

</div>

---

## 💡 The one idea

This challenge is **adversarial by design**. A ranker that matches the job's keywords
against each profile's skill list gets fooled — and gets disqualified. The pool is full of:

- **Keyword stuffers** — a Project Manager whose skills read *“RAG, Pinecone, LangChain (expert)”* but who never shipped a model.
- **Plain-language fits** — engineers who never write *“embeddings”* but whose career shows they built a recommendation system at a product company.
- **Honeypots** — internally impossible profiles (a skill *“used”* for more months than the person has worked).
- **Behavioral twins** — near-identical profiles separated only by who's actually available.

> **Our thesis: score the career, not the skill list.** What someone *did* at a product
> company is far harder to fake than what they *claim* — so career history is the primary
> evidence, the skill list is low-trust, and availability + internal-consistency act as gates.

---

## 📊 Results at a glance

Measured on a **60-profile hand-labeled validation set** (a local proxy — *not* the hidden competition score):

| | NDCG@10 | NDCG@50 | Kendall τ | Honeypots in top-100 | Runtime (100K, CPU) |
|---|:---:|:---:|:---:|:---:|:---:|
| Baseline | 0.87 | 0.95 | +0.72 | 0 | ~13 s |
| **Tuned** | **0.93** | **0.99** | **+0.77** | **0** | **~13 s** |

The lift came from validated changes, not guesswork: saturating the experience term,
converting the seniority band into a multiplicative gate, and adding skill-assessment
corroboration. Every change was kept only because it improved agreement with the labels.

---

## ✨ What's inside

| | |
|---|---|
| 🧠 **Career-first scoring** | The dominant signal is applied-ML years at *product* companies, derived from title + industry — not keyword counts |
| 🛡️ **Ratio-based honeypot gate** | Impossible profiles collapse on their own internal contradictions — no blocklist, no special-casing |
| 🔍 **Assessment corroboration** | Redrob skill-assessment scores expose “expert” claims with no backing — the keyword-stuffer's tell |
| ⚖️ **Multiplicative availability gates** | A ghost can't be rescued by a perfect profile; enthusiasm can't rescue a bad fit |
| 📝 **Evidence-based reasoning** | Every reasoning string cites real profile facts, names a JD requirement, and admits the biggest gap |
| 🧪 **Validation without ground truth** | Two independent blind labeling passes, 96.7% self-agreement — the rigor most submissions skip |
| 🎛️ **Explainable demo** | Live ranking workbench: per-candidate score decomposition, trap showcase, fairness audit, blind screening |
| ⚡ **Fast & reproducible** | Pure-Python feature scorer, all 100K in ~13s on CPU, byte-identical across runs |

---

## 📋 Table of contents

- [Pipeline](#-pipeline)
- [Quick start](#-quick-start)
- [How scoring works](#-how-scoring-works)
- [Defeating the traps](#️-defeating-the-traps)
- [Validation methodology](#-validation-methodology)
- [The interactive demo](#️-the-interactive-demo)
- [Project structure](#-project-structure)
- [Output format](#-output-format)
- [Compute constraints](#️-compute-constraints)
- [Design decisions](#-design-decisions)

---

## 🔧 Pipeline

```
                    candidates.jsonl (100,000)
                            │
                            ▼
          ┌────────────────────────────────────────┐
          │  Single streaming pass (constant RAM)  │
          │                                        │
          │  parse ─► classify each role           │
          │     (title + industry, not free text)  │
          │     ─► extract fit features            │
          │     ─► internal-consistency checks     │
          └──────────────┬─────────────────────────┘
                         │
                         ▼
          ┌────────────────────────────────────────┐
          │  Compose the score                     │
          │                                        │
          │  max(0, fit − penalties)               │
          │     × behavior_mult                    │
          │     × location_fit                     │
          │     × impossibility_gate               │
          └──────────────┬─────────────────────────┘
                         │
                         ▼
          ┌────────────────────────────────────────┐
          │  Rank ─► top 100 ─► reasoning ─► CSV    │
          │  (CPU, no network, ~13s, deterministic)│
          └──────────────┬─────────────────────────┘
                         │
                         ▼
                    submission.csv
```

---

## 🚀 Quick start

```bash
# setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# produce the ranking (single command, CPU-only, no network)
python -m src.rank --in data/candidates.jsonl --out submission.csv

# check format against the challenge validator
python validate_submission.py submission.csv

# check ranking quality against the hand-labeled set
python eval/validate_ranker.py

# launch the interactive demo
streamlit run app.py
```

| Requirement | Notes |
|---|---|
| Python ≥ 3.10 | standard library + a few light deps |
| RAM | comfortably under 16 GB (streams the file; peak ~0.8 GB) |
| GPU | **not required** — there is none in the ranking path |
| Network | **not required** — nothing is downloaded or called at ranking time |

---

## 🧮 How scoring works

Every candidate's score decomposes into terms you can read aloud — that legibility is the
whole point, and it's what makes the ranking defensible.

```
final_score = max(0, fit − penalties)
              × behavior_mult        # is the person actually available / responsive?
              × location_fit         # India / Pune-Noida / relocatable?
              × impossibility_gate   # ~0 for internally contradictory profiles
```

| Term | What it captures |
|---|---|
| **fit** | applied-ML years at product companies *(dominant, saturating)*, core retrieval/ranking/embedding skills with plausible durations and assessment backing, seniority-band fit, evidence of shipping a ranking/search/rec system, evaluation-framework signal |
| **penalties** | consulting-only career, title-chasing, CV/speech focus without NLP/IR, no real applied-ML experience |
| **behavior_mult** | open-to-work, activity recency, recruiter response rate, interview completion |
| **location_fit** | India-based / willing to relocate to the role's hubs |
| **impossibility_gate** | scale-invariant ratio check — a skill or tenure “used” far longer than the person has worked collapses the score |

Two deliberate properties:

- **Career over keywords.** Role classification keys on **title + industry** (reliable) and
  treats free-text descriptions as low-trust noise, because the dataset shuffles them.
  `applied_ml_years` *saturates* past ~5–6 years so raw seniority can't dominate — the JD
  wants 4–5 years of applied ML, not “as much as possible.”
- **Gates are multiplicative.** A perfect-on-paper candidate who is unavailable, mislocated,
  or internally impossible collapses regardless of fit — matching the JD's instruction to
  down-weight the unreachable.

---

## 🛡️ Defeating the traps

The system is built to beat the four trap types the dataset plants — verified on the full pool:

| Trap | How it's defeated | Evidence |
|---|---|---|
| **Keyword stuffer** | Fit reads career history, not the skill list; assessment scores expose unbacked “expert” claims | A “Project Manager” with a full AI skill list ranks ~19th of 50, not top-10 |
| **Plain-language fit** | The dominant term is title+industry-derived, so a real fit isn't lost for lacking buzzwords | Full-pool sweep of 692 strong-career/low-score profiles found **zero** genuine fits buried by vocabulary |
| **Honeypot** | Ratio-based impossibility gate, no blocklist | **0** impossible profiles in the final top-100; the gate strips honeypots the fit score would otherwise rank highly |
| **Behavioral twin** | Multiplicative availability gate separates identical profiles | Stale / unresponsive twins collapse below their active counterparts |

---

## 🧪 Validation methodology

No ground truth is provided, and only 3 submissions are allowed — so the ranker was tuned
against a **hand-labeled validation set**, never by trial-and-error submission.

1. **Stratified sample** of 60 profiles: the ranker's top picks, a *high-skill / low-ML*
   stratum to surface stuffers, mid-scoring, and random.
2. **Blind labeling.** Rows shuffled and the model's own score/rank hidden, so the labels
   can't rubber-stamp the model — the evaluation can't be circular.
3. **Two independent passes** → **96.7% exact self-agreement, 100% within one tier.** The
   only disagreements sit on the 4-vs-5 boundary among strong candidates and are flagged
   low-confidence so tuning can't overfit to them.
4. **Metrics:** NDCG@10/@50, Kendall τ, and a MISS/FALSE table (any strong fit buried past
   rank 100, or any non-fit surfaced into the top 50).

> This is the single thing that most distinguishes the project: the ranking isn't *asserted*
> to be good — it's *measured* against an independent human judgment, with the labeling's own
> reliability quantified.

---

## 🎛️ The interactive demo

`streamlit run app.py` — an explainability workbench, not just a table.

| Tab | What it shows |
|---|---|
| **Ranked list & audit** | The top candidates with score + reasoning, and a per-candidate **score decomposition** — every term, gate, and penalty made visible |
| **How it handles traps** | Side-by-side: a keyword-stuffer ranked down, a genuine fit ranked up, a honeypot collapsed — with the numbers |
| **Fairness audit** | Top-100 shortlist vs full-pool distribution by experience, location, and company type, with honest interpretation of any skew |
| **Actual top-100** | The real submission output, candidate by candidate |

A global **blind-screening** toggle masks names, companies, and institutions — demonstrating
the ranking is driven by signal, not pedigree. *(All demo views are read-only over the
ranking; they never alter the submitted output.)*

---

## 📁 Project structure

```
redrob-ranker/
├── src/
│   ├── io_utils.py       # streaming loader for the candidate pool
│   ├── vocab.py          # all keyword / skill / firm lists — each documented
│   ├── classify.py       # role → (ml_weight, is_product)
│   ├── honeypot.py       # impossibility_score (graduated ratio gate)
│   ├── features.py       # extract_features(candidate) → components
│   ├── score.py          # WEIGHTS + composition (single tunable knob)
│   ├── reasoning.py      # feature values → honest, specific reasoning
│   └── rank.py           # load → score → top 100 → submission.csv
├── eval/
│   ├── RUBRIC.md         # the labeling tier definitions
│   ├── labels.csv        # hand-labeled validation set (ground-truth proxy)
│   ├── validate_ranker.py# NDCG / Kendall τ / MISS-FALSE table
│   └── AUDIT.md          # top-10, plain-language, MAP-tail, sensitivity findings
├── tests/                # honeypots, traps, tie-breaks, CSV format
├── app.py                # Streamlit explainability demo
├── PLAN.md               # architecture + methodology + build phases
├── DECISIONS.md          # design rationale (for the defend-your-work review)
├── requirements.txt
├── submission_metadata.yaml
└── submission.csv        # the deliverable
```

---

## 📤 Output format

`submission.csv` — validated against the challenge spec:

```csv
candidate_id,rank,score,reasoning
CAND_0006557,1,32.121,"7.9yr Senior AI Engineer with search & ranking work at product companies; deep retrieval stack with assessment-backed skills; open to work and highly responsive."
CAND_0081846,2,31.486,"6.7yr Lead AI Engineer at a fintech product company; strong embeddings + vector-search depth matching the JD's retrieval requirement; ideal seniority band."
```

| Rule | Status |
|---|:---:|
| Exactly 100 rows, ranks 1–100 each once | ✅ |
| Scores non-increasing, ties broken by candidate_id ascending | ✅ |
| All `CAND_XXXXXXX` IDs valid and present in the pool | ✅ |
| 100 distinct scores (model differentiates) | ✅ |
| 0 honeypots in the top-100 | ✅ |
| Passes the official validator | ✅ |

---

## ⚙️ Compute constraints

| Constraint | Limit | How it's met |
|---|---|---|
| Runtime | ≤ 5 min | ~13 s for the full 100K pool |
| Memory | ≤ 16 GB | streaming pass, peak ~0.8 GB |
| Compute | CPU only | pure-Python feature scoring, no model inference |
| Network | off | nothing downloaded or called at ranking time |
| Determinism | — | byte-identical CSV across runs (pinned reference date, rank-pure reasoning) |

---

## 🧭 Design decisions

A few choices worth calling out (full rationale in [`DECISIONS.md`](DECISIONS.md)):

- **Feature-based, not embedding-first.** Every score is auditable and honeypots die by
  construction. A full-pool sweep found no genuine fits buried by vocabulary, so embeddings
  would have added complexity with no measured benefit — the “framework enthusiast” move the
  JD explicitly warns against.
- **No honeypot blocklist.** Impossible profiles are caught by internal-consistency math, so
  the system generalizes to honeypots it has never seen.
- **Tuned against labels, not submissions.** With 3 submissions and no leaderboard, a
  hand-labeled validation set is the only disciplined way to know a change helped.

---

<div align="center">

*Built for the Redrob AI — Intelligent Candidate Discovery & Ranking Challenge.*

**Score what someone built, not what they listed.**

</div>
