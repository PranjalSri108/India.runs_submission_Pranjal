# COMPLIANCE — Requirements Traceability Matrix

Phase 8, Stage A. Every requirement from the authoritative bundle docs, mapped to
how this repo satisfies it, with file/line evidence and status.

**Sources** (all in `data/`): `submission_spec.docx` (§N), `job_description.docx` (JD),
`README.docx` (bundle), `redrob_signals_doc.docx` (signals), `candidate_schema.json`,
`submission_metadata_template.yaml`.

**Legend:** ✅ met · ⚠️ met with note · ❓ needs input from you.

Verification run (this machine, CPU-only): scored 100,000 in **13.8 s**, peak RAM
**0.81 GB**, validator **"Submission is valid."**, honeypots in top-100 **0**,
pytest **7 passed**, output **byte-identical across 3 runs** (incl. differing
`PYTHONHASHSEED`).

---

## 1. Required deliverables (spec §10)

| # | Requirement | Source | How we satisfy it | Evidence | Status |
|---|---|---|---|---|---|
| 1 | Top-100 ranking CSV | §10.1 | `rank.py` writes `submission.csv` | `submission.csv`, `src/rank.py:write_submission` | ✅ |
| 2 | Portal metadata mirrored in repo as `submission_metadata.yaml` | §10.3 | Filled from template at repo root | `submission_metadata.yaml` | ⚠️ team/GitHub/sandbox/phone are placeholders → **need you** |
| 3 | Code repository (full source, no hidden steps) | §10.3 | All ranking code in `src/`, committed per phase | `src/`, `git log` | ✅ |
| 4 | README with setup + exact reproduce command | §10.3 | Clone→venv→run documented | `README.md` "Quickstart" / "Reproduce from a clean clone" | ✅ |
| 5 | Pre-computed artifacts or a script that makes them | §10.3 | None needed — no embeddings/indexes/models; pure-stdlib ranker | `requirements.txt` (pytest only) | ✅ |
| 6 | `requirements.txt` (or equiv.) with pinned deps | §10.3 | Pinned, minimal | `requirements.txt` | ✅ |
| 7 | Single command produces CSV from candidates file | §10.3 | `python -m src.rank data/candidates.jsonl` | `src/rank.py:__main__`, `scripts/run.sh` | ✅ |
| 8 | Working sandbox/demo link | §10.5 | `app.py` (Streamlit) runs real `src/` ranker on a sample; needs hosting | `app.py`, `requirements-sandbox.txt` | ❓ **need you to host** (HF Spaces / Streamlit Cloud) |
| 9 | Methodology summary ≤200 words | §10.2 | Filled (197 words) | `submission_metadata.yaml:methodology_summary` | ✅ |

## 2. Submission-file constraints (spec §2–3)

| Requirement | Source | How we satisfy it | Evidence | Status |
|---|---|---|---|---|
| Filename = participant ID + `.csv` | §2 | We emit `submission.csv`; rename before upload | README "Submitting" + rename cmd | ⚠️ **rename to `<your_id>.csv`** |
| UTF-8 encoding | §2 | `csv.writer` default text mode, UTF-8 | validator reads `encoding="utf-8"` & passes | ✅ |
| Header exactly `candidate_id,rank,score,reasoning` | §2 | `HEADER` constant | `src/rank.py:HEADER` | ✅ |
| Column order | §2 | Same constant order | `src/rank.py:HEADER` | ✅ |
| Exactly 100 data rows | §3 | `TOP_N=100`, slice `[:100]` | `src/rank.py:rank_pool` | ✅ |
| Each rank 1–100 exactly once | §3 | `enumerate(...,1)` over 100 rows | `src/rank.py:write_submission` | ✅ |
| Each candidate_id once | §3 | Pool ids unique; top-100 distinct | validator passes (no dupes) | ✅ |
| Every candidate_id exists in pool | §3 | IDs come straight from the pool | `src/rank.py:rank_pool` (ids from records) | ✅ |
| `candidate_id` matches `CAND_[0-9]{7}` | §3, schema | IDs copied verbatim from records | validator regex passes | ✅ |
| score float | §2 | Written `f"{sc:.6f}"` | `src/rank.py:write_submission` | ✅ |
| Score non-increasing with rank | §3 | Sort `(-rounded_score, id)` | `src/rank.py:rank_pool` | ✅ |
| Ties broken deterministically (id ascending) | §3 | Secondary sort key = candidate_id asc | `src/rank.py:rank_pool` | ✅ |
| Scores differentiated (not all equal) | §3, §6 | 100 distinct scores observed | run log "100 distinct scores" | ✅ |
| Proper CSV quoting (no column blow-up) | §3 | `csv.writer` QUOTE_MINIMAL quotes commas/quotes | `src/rank.py:write_submission`; validator 4-col check | ✅ |
| Reasoning present, 1–2 sentences | §2 | Generated per candidate | `src/reasoning.py:make_reasoning` | ✅ (optional, included) |

## 3. Compute constraints (spec §3)

| Requirement | Limit | Actual | Evidence | Status |
|---|---|---|---|---|
| Total runtime | ≤ 5 min | **13.8 s** | `scripts/run.sh` output | ✅ |
| Memory | ≤ 16 GB | **0.81 GB** peak RSS | `/usr/bin/time -v` in run.sh | ✅ |
| CPU only (no GPU) | required | pure-Python, no GPU libs | `requirements.txt` | ✅ |
| No network during ranking | required | no network calls anywhere in `src/` | no `requests`/`urllib`/SDK imports | ✅ |
| Disk intermediate state | ≤ 5 GB | ~42 KB (`submission.csv`) | output file size | ✅ |

## 4. Reasoning-quality checks (spec §3, Stage 4)

| Check | Source | How we satisfy it | Evidence | Status |
|---|---|---|---|---|
| Specific facts cited | §3 | ≥2 record facts per reasoning, enforced by test | `tests/test_reasoning.py::test_every_reasoning_cites_two_real_facts` | ✅ |
| JD connection | §3 | Every reasoning ends with a brief-fit clause | `src/reasoning.py:_connect` | ✅ |
| Honest concerns | §3 | Every reasoning names a gap | `src/reasoning.py:_gap`; `test_always_has_a_caveat` | ✅ |
| No hallucination | §3 | Facts pulled only from the record; test guards skills | `test_no_hallucinated_skill_names` | ✅ |
| Variation (not templated) | §3 | Archetype-branched structure + per-id wording | `test_reasonings_are_varied` | ✅ |
| Rank-consistent tone | §3 | Tone tiered by rank | `src/reasoning.py:_lead` | ✅ |

## 5. Disqualification criteria (spec §5–7) — actively defended

| Disqualifier | Source | Defense | Evidence | Status |
|---|---|---|---|---|
| Honeypot rate > 10% in top-100 | §7, Stage 3 | Multiplicative impossibility gate; final-ranking scan = 0 | `src/honeypot.py`; run log "0 flagged" | ✅ 0% |
| Can't reproduce in 5 min / 16 GB / CPU | Stage 3 | 13.8 s / 0.81 GB / stdlib | `scripts/run.sh` | ✅ |
| Any format violation | Stage 1 | Official validator passes | `data/validate_submission.py` → "valid" | ✅ |
| Flat git history (single dump) | Stage 4 | 7 honest per-phase commits + this one | `git log` | ✅ |
| Codebase is just LLM API calls | Stage 4 | Zero LLM/network calls; feature logic is ours | `src/` | ✅ |
| Can't defend architecture (interview) | Stage 5 | `DECISIONS.md` + `PLAN.md` | `DECISIONS.md` | ✅ |

## 6. JD fit logic (job_description.docx) — encoded, auditable

| JD signal | How encoded | Evidence |
|---|---|---|
| 4–5 yrs applied ML at product cos | `applied_ml_years` (product-only), saturated | `src/features.py`, `src/score.py:_saturate_ml_years` |
| Shipped a ranking/search/rec system | `shipped_system` from descriptions | `src/features.py`, `src/vocab.py:SHIPPED_SYSTEM_PHRASES` |
| Eval frameworks (NDCG/MRR/MAP/A-B) | `eval_signal` | `src/vocab.py:EVAL_PHRASES` |
| Embeddings / vector DB skills | `core_skill_score` | `src/vocab.py:CORE_SKILL_TERMS` |
| 5–9 band ("range, not requirement") | `band_fit` + `seniority_gate` | `src/features.py` |
| Disqualifier: consulting-only career | `penalties` (all-services) | `src/features.py`, `src/vocab.py:CONSULTING_FIRMS` |
| Disqualifier: CV/speech/robotics w/o NLP | `penalties` | `src/features.py` |
| Disqualifier: title-chasing | `penalties` (short stints) | `src/features.py` |
| Disqualifier: drifted senior (not hands-on) | `seniority_gate` (proxy: yoe) | `src/features.py` — see DECISIONS.md trade-off |
| Behavioral availability down-weight | `behavior_mult` | `src/features.py` |
| Location: Pune/Noida/Tier-1 India | `location_fit` | `src/features.py`, `src/vocab.py:PREFERRED_CITIES` |

---

## Ambiguities / open items flagged

1. **Filename rule (§2).** Spec wants the file named your *participant ID*; the
   validator only checks `.csv` + non-empty stem, so `submission.csv` passes locally,
   but the **portal upload must be `<participant_id>.csv`**. Rename command in README.
2. **Bundle says `candidates.jsonl.gz`; this machine has plain `candidates.jsonl`.**
   The loader handles both via gzip magic-byte sniffing (`src/io_utils.py`). No action.
3. **`reproduce_command` flag style.** Spec's example uses
   `--candidates/--out`; our command is `python -m src.rank data/candidates.jsonl`
   (single command, spec says the flags are "for example"). A flag wrapper can be
   added on request (no logic change).
4. **Needs you:** team identity, primary contact + phone, GitHub URL, sandbox host,
   AI-tools declaration specifics, compute-env line. Placeholders marked in
   `submission_metadata.yaml`.
