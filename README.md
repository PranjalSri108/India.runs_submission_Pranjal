# Redrob Ranker

A feature-based, fully-explainable system that ranks the **top 100 candidates out of
100,000** for a single role: a Senior AI Engineer on a founding team building
ranking/search/recommendation systems.

The design thesis in one line: **score what someone built, not what they listed.**

Runs over all 100,000 profiles in **~20 seconds**, **CPU-only**, Python **standard
library only** — no GPU, no network, no LLM calls at ranking time. Output is
**byte-for-byte deterministic** across runs.

---

## Results at a glance

| | |
|---|---|
| NDCG@10 / NDCG@50 / Kendall τ | **0.93 / 0.99 / +0.77** (hand-labeled 60-profile set) |
| Honeypots in the top-100 | **0** (spec auto-DQ threshold is 10%) |
| Runtime · 100K · CPU | **~20 s** (budget 5 min) · peak RAM 0.81 GB |
| Output | **byte-for-byte deterministic**, reproduced from a clean clone |

Validated **without ground truth** by two-pass blind hand-labeling (96.7% inter-pass
agreement). Full method in [Validation methodology](#validation-methodology-no-ground-truth)
and [Results](#results); every design trade-off is defended in `DECISIONS.md`, and the
adversarial cases are quantified in `eval/TRAP_HANDLING.md`.

## The problem

The candidate pool is adversarial. A naive "match the job's keywords against each
profile's skills" ranker fails badly, because the data contains:

- **Keyword stuffers** — a project manager whose skill list reads "RAG, Pinecone,
  LangChain (expert)" but who never shipped a model.
- **Plain-language fits** — engineers who never write "embeddings" but whose career
  shows they built a recommendation system at a product company.
- **Honeypots** (~80 in the pool) — internally impossible profiles (e.g. a skill
  "used" for more months than the person has worked). Ranking these in the top 100
  above a 10% rate is an automatic Stage-3 disqualification.
- **Behavioral twins** — near-identical profiles separated only by whether the person
  is actually available and responsive.

So the ranker reads the **career history** as primary evidence, treats the skill list
as weak corroboration, and applies availability and internal-consistency checks as
multiplicative gates.

## Scoring model

Every term is something you can say out loud about a candidate:

```
final_score = max(0, fit - penalties)
              * behavior_mult        # actually available / responsive?
              * location_fit         # India / Pune-Noida / relocatable?
              * impossibility_gate   # ~0 for internally contradictory profiles
              * seniority_gate       # steep falloff well beyond the 5-9 band
```

| Term | Captures |
|---|---|
| `fit` | applied-ML years at product companies, core IR/ranking/embedding skills with plausible durations, seniority-band fit, evidence of shipping a ranking/search/rec system, eval-framework signal |
| `penalties` | consulting-only career, title-chasing, CV/speech focus without NLP/IR, no real applied-ML experience |
| `behavior_mult` | open-to-work, recency of activity, recruiter response rate, interview completion |
| `location_fit` | India-based / willing to relocate to the role's hubs |
| `impossibility_gate` | scale-invariant ratio check that collapses honeypots (skill or tenure duration far exceeding total experience) |
| `seniority_gate` | multiplicative band penalty: 1.0 through 5–9 yrs, steep falloff beyond — encodes the JD's "drifted senior" disqualifier |

`applied_ml_years` is the dominant signal, but it **saturates** — the role wants ~4–5
years of applied ML, so a 15-year veteran is not scored as 3× a focused 6-year IC.
All tunable weights live in one place: `src/score.py:WEIGHTS`.

## Repo layout

```
redrob-ranker/
├── README.md
├── PLAN.md                  # full architecture + methodology + build phases
├── COMPLIANCE.md            # requirements traceability matrix (every spec rule)
├── DECISIONS.md             # design-decision defense (Stage 5 interview prep)
├── requirements.txt         # core ranker deps (pure stdlib; pytest for tests)
├── requirements-sandbox.txt # demo-only deps (streamlit)
├── app.py                   # Streamlit sandbox: runs the real ranker on a sample
├── validate_submission.py   # the provided format validator
├── data/
│   ├── candidates.jsonl(.gz)   # the 100K pool (gitignored — obtain from bundle)
│   ├── sample_candidates.json  # first 50, for the sandbox + tests
│   └── ... (schema, JD, spec, signals doc, metadata template)
├── src/
│   ├── io_utils.py          # streaming loader (gzip magic-byte detection)
│   ├── vocab.py             # all keyword/skill/firm lists, each documented
│   ├── classify.py          # role -> (ml_weight, is_product)
│   ├── honeypot.py          # impossibility_score (graduated ratio gate)
│   ├── features.py          # extract_features(candidate) -> components
│   ├── score.py             # WEIGHTS + composition (single tunable knob)
│   ├── reasoning.py         # feature values -> honest, specific reasoning
│   └── rank.py              # load -> score -> top 100 -> submission.csv
├── eval/
│   ├── RUBRIC.md            # the labeling tier definitions
│   ├── sample_for_labeling.py
│   ├── labels.csv           # hand-labeled validation set (ground-truth proxy)
│   ├── to_label.csv         # the blank stratified sample that produced it
│   └── validate_ranker.py   # NDCG@10/@50, Kendall tau, MISS/FALSE table
├── scripts/
│   └── run.sh               # end-to-end; reports wall-clock + peak RAM, validates
└── submission.csv           # the deliverable
```

## Reproduce from a clean clone

```bash
# 1. clone, then create the environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # core ranker needs no third-party libs

# 2. obtain the candidate pool (gitignored — too big for git)
#    from the hackathon bundle, place candidates.jsonl.gz (or .jsonl) in data/
#    the loader auto-detects gzip vs plain via magic bytes.

# 3. produce the ranking  (single command; writes ./submission.csv)
python -m src.rank --candidates data/candidates.jsonl.gz --out submission.csv
#    The candidates path is a CLI argument (never hardcoded); --out sets the
#    destination. A plain data/candidates.jsonl also works (gzip is detected by
#    magic bytes, not extension). Equivalent shortcuts:
#      python -m src.rank                          # auto-resolves data/candidates.jsonl.gz then .jsonl
#      python -m src.rank data/candidates.jsonl    # positional, same as --candidates

# 4. validate the submission format
python validate_submission.py submission.csv      # -> "Submission is valid."

# 5. (optional) check ranking quality against the hand-labeled set
python eval/validate_ranker.py
```

Or run everything (ranking + timing + peak-RAM report + format validation) in one go:

```bash
bash scripts/run.sh
```

> **Determinism:** `scripts/run.sh` pins `PYTHONHASHSEED=0`, and the reasoning
> generator uses a stable hash internally, so `submission.csv` is byte-identical on
> every run regardless of environment.

## Sandbox / demo

`app.py` is a Streamlit explainability demo built from native Streamlit components
on the default theme (no custom CSS or fonts; the only color accents are green/red
on the score-breakdown chart). It runs the **real `src/` ranker** (never a
reimplementation) live on `data/sample_candidates.json`, and reads the committed
`submission.csv` for the actual top-100. Three views:

1. **Ranked list & audit** — two-pane (with the score-range / top-N filters in a
   control row above): pick any candidate on the left, and the right panel shows the full score
   decomposition — additive fit terms (green), the penalty (red), then the
   multiplicative gates as explicit neutral `×` steps down to the final score, plus
   the reasoning and the underlying career/skills/signals.
2. **How it handles traps** — a keyword-stuffer, a genuine fit, and a honeypot side by
   side, so you can see the system defeat the adversarial cases (skills-vs-career
   mismatch; impossible skill duration collapsed by the impossibility gate).
3. **Actual top-100** — the committed `submission.csv`, searchable.

Run locally:

```bash
pip install -r requirements-sandbox.txt
streamlit run app.py
```

### Deploying the sandbox (spec §10.5)

The demo needs **only a pip requirements file** — the three pinned lines in
`requirements-sandbox.txt` (`streamlit`, `altair`, `pandas`). No Dockerfile, system
packages, model downloads, or environment variables. It pre-loads
`data/sample_candidates.json` (50 profiles, ≤ 100), runs the **real `src/` ranker**
end-to-end on CPU in well under a second (far inside the 5-minute budget), and reads
the committed `submission.csv` for the actual top-100. Every path is resolved relative
to the app file (`__file__`), so there are **no absolute paths** to fix.

Files the deployed app needs — all committed: `app.py`, `src/`,
`data/sample_candidates.json`, `submission.csv`, `.streamlit/config.toml`.

**Streamlit Community Cloud**

1. Push this repo to GitHub.
2. Streamlit Cloud installs from `requirements.txt` at the repo root. That file is the
   *lean ranker* set, so give the deploy the demo deps one of two ways: copy the three
   lines from `requirements-sandbox.txt` into `requirements.txt`, **or** deploy from a
   branch whose `requirements.txt` is those three lines. (The ranker imports only the
   stdlib either way — see the import audit — so this only affects the demo build.)
3. On [share.streamlit.io](https://share.streamlit.io) → **New app** → select the repo
   and branch, set **Main file path** to `app.py`, and Deploy. The public URL it gives
   you is your sandbox link.

**HuggingFace Spaces** (the Space is its own git repo, so no branch juggling)

1. Create a new Space → **SDK: Streamlit** → CPU basic (free tier is fine).
2. Add to the Space: `app.py`, the `src/` folder, `data/sample_candidates.json`,
   `submission.csv`, `.streamlit/config.toml`, and a `requirements.txt` containing the
   three lines from `requirements-sandbox.txt`. (Upload via the web UI, or `git push`
   to the Space's remote.)
3. The Space auto-runs `streamlit run app.py`, building from that `requirements.txt`.
   The Space URL is your sandbox link.

Either path satisfies spec §10.5: a ≤100-candidate sample is pre-loaded, the ranking
runs end-to-end, and it completes far inside the 5-minute CPU budget. The breakdown
numbers are computed from `src/score.py` itself, so they match the ranker exactly.

## Submitting

The portal requires the file named after your **participant ID**:

```bash
cp submission.csv <your_participant_id>.csv     # e.g. team_42.csv
python validate_submission.py <your_participant_id>.csv
```

Then upload that file plus the portal metadata (mirrored in
`submission_metadata.yaml`).

## Validation methodology (no ground truth)

The true relevance labels are hidden and only 3 submissions are allowed, so the ranker
is tuned against a **hand-labeled validation set**, not by trial submission.

1. **Stratified sample** of 60 profiles (`eval/sample_for_labeling.py`): the ranker's
   top picks, a "high-skill / low-ML" stratum to surface keyword stuffers, mid-scoring,
   and random — so the set catches both "ranked junk highly" and "missed a real fit".
2. **Blind labeling.** The sample is shuffled and the ranker's own score/rank are
   hidden (trailing `_`-prefixed columns), so labels can't rubber-stamp the model
   (which would make the evaluation circular). Each profile is graded 0–5 per
   `eval/RUBRIC.md`.
3. **Two independent passes** to measure labeling reliability: **96.7% exact /
   100% within one tier**. The only disagreements sit on the 4-vs-5 boundary among
   strong candidates; those are treated as low-confidence so tuning does not overfit.
4. **Metrics** (`eval/validate_ranker.py`): NDCG@10, NDCG@50, Kendall tau, plus a
   MISS/FALSE table (any tier-3+ buried past rank 100, or any tier-≤1 surfaced into
   the top 50).

The validation NDCG is a *relative* compass for tuning, not a prediction of the final
score — with 60 labels, NDCG@10 is noisy, so Kendall tau and the MISS/FALSE table
carry weight too.

## Results

Measured on the 60-profile hand-labeled validation set:

| Metric | Baseline | After tuning (Phase 4) | Phase 8–9 (current) |
|---|---|---|---|
| NDCG@10 | 0.871 | 0.924 | **0.933** |
| NDCG@50 | 0.952 | 0.982 | **0.988** |
| Kendall tau-b | +0.722 | +0.764 | **+0.771** |
| Buried fits (MISS) | 1\* | 1\* | 2\* |
| Surfaced junk (FALSE) | 0 | 0 | 0 |

\* MISS = a tier-3+ profile ranked past 100. Every one is an **over-band** profile
(15–16 yrs, ~2× the ideal band) the seniority gate correctly demotes to the low
thousands where the other tier-3s sit — not a buried fit. They are also among the 8
low-confidence labels; on the **held-out 52-label set** (those excluded) MISS = 0,
FALSE = 0, and NDCG@10 = 1.000. No tier-5 is buried and no tier-≤1 reaches the top 50.

**Phase 8–9 refinements.** Two validated, audit-driven additions lifted the held-out
metrics without regressions: an **assessment-score corroboration** signal (Redrob skill
assessments + endorsements corroborate or discount a claimed skill — the direct
keyword-stuffer counter), and a **core-skill saturation** that stops a long listed skill
set from out-weighing career evidence. Each was kept only after it improved Kendall τ
with no NDCG@50 regression and no new FALSE; see `DECISIONS.md` #8–9 and the full leak
audit in `eval/AUDIT.md`.

Production-run facts (full 100K, this machine, CPU-only):

| | |
|---|---|
| Runtime | **~20 s** (20.3 s measured; budget: 5 min) |
| Peak RAM | **0.81 GB** (budget: 16 GB) |
| Honeypots in top-100 | **0** (disqualified above 10) |
| Distinct scores | 100 / 100 |
| Top-100 composition | 96 in the 5–9 band, 100/100 India-based, 89 with a shipped system |

**What the tuning changed.** Baseline cross-checking showed the discrimination was
already sound — no genuine fit buried, no junk surfaced — but one over-experienced
profile (16 years, ~2× the ideal band) sat at rank 3. The fix was structural rather
than cosmetic: `applied_ml_years` was given a soft cap (full credit to ~5 years,
shallow slope after) so raw seniority stops dominating, and the seniority-band term
was converted from a weak additive penalty into a **multiplicative gate** (1.0 through
the band, steep falloff beyond it). That dropped the 16-year profile from rank 3 to
~2100 — where the other tier-3s sit — and lifted NDCG@10 by ~0.05 without pushing any
genuine fit down.

**A documented trade-off.** The seniority gate keys on years of experience as a proxy
for the JD's real concern (hands-on recency — whether a senior still ships code). It is
deliberately blunt: every over-band profile is demoted, because every over-band profile
in the validation set was tier-3. A genuinely strong over-band hands-on IC would also be
demoted; no such profile existed to calibrate against, so softening the gate would mean
tuning to an unobserved case. The gate's floor is the knob to revisit if such profiles
appear. (See `DECISIONS.md`.)

## Key design decisions

See `DECISIONS.md` for the full defense. In brief:

- **Feature-based over embedding-first.** Every score decomposes into auditable
  reasons; honeypots collapse by construction. Embeddings are an optional add-on, to
  be introduced only if validation shows real fits being missed (it did not — the
  Phase-9 audit found 0 genuine fits lost to vocabulary across 692 strong-career
  candidates; `eval/AUDIT.md` §2).
- **Structure over prose.** Career-history *descriptions* in the data are partly
  shuffled noise, so role classification keys on title + industry; description text
  only adds corroboration, never drives a score down.
- **Multiplicative gates.** A perfect-on-paper but unavailable or internally
  impossible candidate collapses regardless of fit.
- **No honeypot blocklist.** Impossible profiles are caught by internal-consistency
  math, not by hard-coding IDs.

## Limitations

- The validation set is 60 profiles; absolute metric values are indicative, not
  precise. Mitigated by weighting the qualitative MISS/FALSE table and Kendall tau.
- Skill `duration_months` in the data is sometimes inflated relative to career length;
  the impossibility gate is calibrated to flag the extreme (likely-synthetic) cases
  while tolerating mild résumé padding — a deliberate precision/recall trade.
- Free-text descriptions are treated as low-trust by design, so a genuinely
  information-rich description that contradicts a noisy title is under-weighted.
- The seniority gate uses years-of-experience as a proxy for hands-on recency (see the
  trade-off above).
