# Redrob Ranker - Build Plan & Methodology

A feature-based, fully-explainable ranking system for the Intelligent Candidate
Discovery & Ranking Challenge. This document is the spec we build against. It is
also the methodology writeup (Stage 4) and the architecture you defend (Stage 5).

---

## 0. The one thing that matters

This competition is **adversarially designed to punish keyword matching.** The JD
says so explicitly. The dataset contains keyword-stuffers, plain-language real
fits, behavioral twins, and ~80 honeypots. A cosine-similarity-over-skills system
ranks the traps in its top 10 and gets **disqualified at Stage 3** (honeypot rate
> 10%).

Our thesis: **read the career history, not the skills list.** A candidate is a fit
because of what they *did at product companies*, weighted by whether they're
*actually available*, gated by whether the profile is *internally consistent*.

The scoring model (every term is explainable):

```
final_score = max(0, fit - penalties) * behavior_mult * location_fit * impossibility_gate
```

| Term | What it captures | JD basis |
|---|---|---|
| `fit` | applied-ML years at product cos, core IR/ranking skills, band fit, "shipped a ranking system", eval-framework signal | "skills inventory" + "how to read between the lines" |
| `penalties` | consulting-only career, title-chasing, wrong-domain (CV/speech), no real ML | "Things we explicitly do NOT want" |
| `behavior_mult` | open-to-work, recency, recruiter response rate, interview completion | redrob_signals_doc + "weigh behavioral signals" |
| `location_fit` | India / Pune-Noida / willing to relocate | "On location" |
| `impossibility_gate` | honeypot detection via internal contradiction | Section 7 honeypot warning |

---

## 1. Repo layout

```
redrob-ranker/
├── README.md                # what it is, how to run, results
├── PLAN.md                  # this file (methodology + architecture)
├── requirements.txt         # pin versions; keep minimal
├── .gitignore               # ignore the big .gz, __pycache__, .venv
├── data/
│   ├── candidates.jsonl.gz  # the 100K pool (gitignored - too big for git)
│   └── sample_candidates.json
├── src/
│   ├── __init__.py
│   ├── io_utils.py          # streaming loader for the gz file
│   ├── vocab.py             # ALL keyword/skill/firm vocabularies - auditable
│   ├── classify.py          # role -> (ml_weight, is_product)
│   ├── honeypot.py          # impossibility_score(candidate) -> [0,1]
│   ├── features.py          # extract_features(candidate) -> dict
│   ├── score.py             # compose features -> final score (weights live here)
│   ├── reasoning.py         # feature components -> honest, specific reasoning
│   └── rank.py              # orchestrator: load -> score -> top100 -> csv
├── eval/
│   ├── sample_for_labeling.py   # draw a stratified sample to hand-label
│   ├── labels.csv               # YOUR hand labels (the validation set)
│   └── validate_ranker.py       # agreement metrics vs your labels
├── tests/
│   ├── test_honeypot.py
│   ├── test_features.py
│   └── test_format.py           # wraps the provided validator
├── scripts/
│   └── run.sh                    # end-to-end, prints wall-clock time
├── validate_submission.py        # provided validator, copied in
└── submission.csv                # the deliverable
```

Why this split: each module is small, independently testable, and maps to one idea
you can explain. `vocab.py` and `score.py` hold every tunable knob in one place so
tuning never means hunting through logic.

---

## 2. Build sequence (phases with checkpoints)

Build in this order. **Commit after every phase** - Stage 4 checks git history for
real iteration. Do not squash into one dump commit.

### Phase 0 - Scaffold & data access
- Create repo, venv, `requirements.txt`, `.gitignore`.
- `io_utils.py`: stream the gz file lazily (`gzip.open` + generator) so we never
  hold 465 MB of parsed objects unless needed. Provide `load_all()` and
  `iter_candidates()`.
- **Checkpoint:** `python -c "from src.io_utils import load_all; print(len(load_all()))"` → 100000.

### Phase 1 - Vocabulary, classification, honeypot
- `vocab.py`: move every keyword list from the prototype here. Document *why* each
  term is in each list (defensibility).
- `classify.py`: `classify_role(job) -> (ml_weight in [0,1], is_product: bool)`.
  Title + industry are trusted; description only adds corroboration (it's noisy -
  see §4).
- `honeypot.py`: `impossibility_score(candidate) -> [0,1]`. Checks: skill duration
  > total experience; job tenure > total experience; advanced/expert skill with
  <6 months; career-month sum wildly > plausible.
- **Checkpoint:** `tests/test_honeypot.py` - the 5 known sample honeypots
  (CAND_0000003, _0000011, _0000012, _0000013, _0000022) all score ≤ 0.5.

### Phase 2 - Features & scoring
- `features.py`: `extract_features(candidate) -> dict` (start from the prototype).
- `score.py`: holds the weight vector and `score(features) -> float`. Keep weights
  as a named dict/dataclass so tuning is one edit.
- **Checkpoint:** on the sample, CAND_0000031 ranks #1; CAND_0000021 (keyword
  stuffer) is outside the top 10; no honeypot in the top 10.

### Phase 3 - Validation harness (NO ground truth - this is the crux)
We cannot tune against the hidden truth, and we get 3 submissions. So we build our
own validation set.
- `sample_for_labeling.py`: from the full 100K, draw a **stratified** sample (~60):
  pull the ranker's current top ~30, plus ~15 mid-scoring, plus ~15 random. This
  surfaces both "did we rank junk highly" and "did we miss anyone".
- Hand-label each into a relevance tier 0-5 using the JD rubric (write the rubric
  into `eval/RUBRIC.md`). Save to `labels.csv`.
- `validate_ranker.py`: compute NDCG@10/@50 and Kendall-tau of the ranker's order
  vs your labels. This is your offline proxy for the real metric.
- **Checkpoint:** a reproducible number you can improve. Record it in README.

### Phase 4 - Tuning
- Adjust weights in `score.py` to maximize agreement with `labels.csv`.
- Resist overfitting to 60 labels: prefer round, defensible weights; change a weight
  only if you can articulate *why* in JD terms.
- **Checkpoint:** validation NDCG improves and the top-10 contains zero obvious
  mis-ranks on manual inspection.

### Phase 5 - Reasoning generation
- `reasoning.py`: `make_reasoning(features) -> str`. Build sentences from the actual
  feature values: years, current title, named matched skills, the strongest signal,
  AND the biggest gap/concern. Vary structure by which features dominate so the 10
  sampled rows read differently. Never mention a skill/employer not in the profile.
- **Checkpoint:** `tests/` asserts every reasoning string references ≥2 concrete
  profile facts and that 10 random reasonings are not string-identical.

### Phase 6 - Pipeline, format, timing
- `rank.py`: load → score all 100K → sort → take top 100 → assign ranks 1-100 →
  ensure scores are strictly non-increasing (break ties by candidate_id ascending,
  matching the validator) → write `submission.csv` with the reasoning column.
- `scripts/run.sh`: times the whole run; must be < 5 min on 16 GB CPU.
- Run the provided `validate_submission.py` - must print "Submission is valid."
- **Checkpoint:** valid CSV produced in < 5 min, peak RAM < 16 GB.

### Phase 7 - (Optional) embedding layer, ONLY if Phase 3 shows a gap
- If hand-labeling reveals real fits the vocabulary missed (plain-language Tier 5s),
  add a local sentence-embedding similarity feature (e.g. `bge-small`, CPU, cached)
  as ONE additional term in `fit`. Load the model once; embed JD once; batch-embed
  candidate summaries. Keep it as an additive signal, never the whole score.
- **Decision rule:** add it only if it raises validation NDCG. Otherwise skip -
  unjustified complexity is the "framework enthusiast" failure mode the JD warns of.

### Phase 8 - Repo polish & submission assets
- `README.md`: one-paragraph approach, how to run, validation numbers, honest
  limitations.
- Methodology summary (≤200 words) for the portal.
- Sandbox: HuggingFace Space / Streamlit / Colab that runs the ranker on a small
  sample (required by the spec, §10.5).
- Fill `submission_metadata_template.yaml`.

---

## 3. Module-by-module contract (signatures to build against)

```python
# io_utils.py
def iter_candidates(path: str): ...        # yields dicts, streaming
def load_all(path: str) -> list[dict]: ...

# classify.py
def classify_role(job: dict) -> tuple[float, bool]: ...   # (ml_weight, is_product)

# honeypot.py
def impossibility_score(candidate: dict) -> float: ...     # 1.0 plausible -> 0.0 impossible

# features.py
def extract_features(candidate: dict) -> dict: ...         # all components + carried profile/signals

# score.py
WEIGHTS = {...}                                            # single source of tunable truth
def score(features: dict) -> float: ...

# reasoning.py
def make_reasoning(features: dict) -> str: ...             # specific, honest, varied

# rank.py
def main(in_path, out_path): ...                           # produces submission.csv
```

---

## 4. Key design decisions (and how to defend them)

1. **Feature-based, not embedding-first.** Every score is explainable; honeypots
   die by construction; defensible in interview. Embeddings are an *optional add-on*
   gated on measured need.

2. **Trust structure over prose.** Sample inspection showed `career_history`
   *descriptions* are partly shuffled/templated noise (a "Project Manager" role
   described as "brand design"). So role classification keys on **title + industry**;
   description text only *adds* corroboration, never drives the score down.

3. **Multiplicative composition for gates.** Behavior, location, and impossibility
   are multipliers. A perfect-on-paper but unavailable or impossible candidate
   collapses regardless of fit - matching the JD's "not actually available → down-
   weight" instruction and the honeypot requirement.

4. **Anti-stuffing in skills.** Skill credit is capped at the candidate's actual
   years of experience and scaled by plausible duration, so "expert in 10 skills,
   0 months used" earns almost nothing.

5. **No honeypot blocklist.** We never special-case specific IDs. We detect internal
   contradiction. The JD explicitly says a good system avoids them *naturally*.

6. **Tuning without ground truth** via a hand-labeled stratified validation set, not
   by burning submissions. This is the disciplined method the spec recommends.

---

## 5. Compute budget

- 100K candidates, pure-Python dict feature scoring: expect well under 60s. No GPU,
  no network - satisfied trivially since nothing calls out.
- If Phase 7 embeddings are added: embed 100K short summaries on CPU. Batch and time
  it; if it threatens the 5-min budget, pre-filter with the cheap feature score to
  the top ~5-10K before embedding (funnel). Cache embeddings to disk (< 5 GB).
- Always run `scripts/run.sh` and read the wall-clock before submitting.

---

## 6. Git hygiene (Stage 4 checks this)

- Real commits per phase with honest messages ("add honeypot impossibility checks",
  "tune fit weights against validation set v2").
- Keep the `eval/labels.csv` and `eval/RUBRIC.md` in the repo - they are the
  evidence of genuine engineering.
- Don't commit the 465 MB data; `.gitignore` it and document where to get it.

---

## 7. Pre-submission checklist

- [ ] Exactly 100 data rows, header `candidate_id,rank,score,reasoning`.
- [ ] Ranks 1-100 each once; scores non-increasing; ties broken by candidate_id asc.
- [ ] All candidate_ids exist in the pool; no duplicates; format `CAND_XXXXXXX`.
- [ ] Scores differentiated (not all equal).
- [ ] No honeypot in top 100 (manually eyeball the top 100 for impossible profiles).
- [ ] Reasoning: specific facts, JD connection, honest concerns, no hallucinations,
      varied, tone matches rank.
- [ ] `validate_submission.py submission.csv` → "Submission is valid."
- [ ] `run.sh` completes < 5 min, < 16 GB.
- [ ] README, methodology ≤200 words, sandbox link, metadata yaml filled.
