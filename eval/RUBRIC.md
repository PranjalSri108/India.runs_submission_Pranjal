# Labeling Rubric - Validation Ground Truth

This is how we hand-label the stratified sample (Phase 3) so we can tune weights
(Phase 4) without burning real submissions. The real ground truth uses relevance
tiers 0-5; we mirror that. Honeypots are forced to tier 0 in the real truth, so we
do the same.

**What we're labeling:** how strong a *hire* this candidate is for THIS role -
fit modulated by whether they're actually available - per the JD. Record one
`overall_tier` (0-5) per candidate, plus two diagnostic notes (below). The diagnostic
notes let us tell, in Phase 4, *which* component (fit vs behavior vs band) is
miscalibrated when the ranker disagrees with us.

## Columns to fill in `labels.csv`

| column | values | meaning |
|---|---|---|
| `candidate_id` | CAND_xxxxxxx | the candidate |
| `overall_tier` | 0-5 | the hire-strength label (drives NDCG) |
| `fit_tier` | 0-5 | role-fit ONLY, ignoring availability (diagnostic) |
| `avail` | strong / ok / stale | availability read from signals (diagnostic) |
| `deciding_factor` | free text, ≤1 line | the one thing that set the tier |

## Tier scale (anchored to the JD)

**Tier 5 - Ideal.** ~6-8 yrs total, ~4-5 of them in applied ML/AI/search/ranking/
recsys **at product companies**; has clearly **shipped a ranking/search/rec system**;
core IR skills (embeddings, vector DB, ranking, retrieval) present with *plausible*
durations; India-based or willing to relocate to Pune/Noida; behaviorally available.
This is the "how to read between the lines" candidate almost verbatim.

**Tier 4 - Strong, one real gap.** Clear ML/IR fit but one notable miss: e.g. great
ML but not specifically ranking/search (general ML or NLP), OR just outside band
(4yr, or 10-11yr but still hands-on IC), OR strong fit but mediocre availability,
OR currently at a consulting firm **but with genuine prior product-ML experience**.

**Tier 3 - Relevant / borderline (this is the P@10 cutoff - "relevant" = tier 3+).**
Real engineering with genuine ML adjacency but meaningful gaps: data/backend engineer
credibly moving into ML; ML experience but mostly at services firms; good fit but
unavailable; good fit but wrong location and won't relocate.

**Tier 2 - Weak.** Adjacent technical role (software/backend/data eng) with little
real ML, OR ML keywords the career doesn't support, OR a disqualifier that mostly
(not fully) sinks them.

**Tier 1 - Very weak.** Unrelated technical role (frontend, devops, QA, mobile) with
a stray relevant skill but no real ML/IR career.

**Tier 0 - Not relevant.** Non-technical (marketing, sales, ops, mechanical/civil
eng, accountant, HR); OR a **honeypot** (internally impossible profile); OR a
**keyword stuffer** whose actual career is non-ML regardless of skill list; OR a
hard JD disqualifier (pure research-only with no production; CV/speech/robotics with
no NLP/IR; entire career at consulting with zero product-ML).

## The hard judgment calls (decide these consistently - they calibrate the weights)

1. **The 15-16yr senior.** Band is "a range, not a requirement," but the ideal is
   6-8 and there's an explicit disqualifier for seniors who stopped coding for
   architecture/lead roles. Default: a way-over-band senior who is *still a hands-on
   ML IC* → **tier 4**. One who has drifted to "Tech Lead / Architect / Principal" or
   shows no recent hands-on ML → **tier 3 or lower**. Rarely tier 5 (band is wrong).
   → This decision tells Phase 4 whether to add `applied_ml_years` saturation and/or
   steepen the band penalty. Label several of these deliberately.

2. **Currently at a consulting firm.** The JD explicitly says current consulting
   employment is FINE if there's prior product-company experience. Do **not** tier-0
   someone just for a current TCS/Infosys/Wipro logo - check the *whole* career.
   Tier-0 only if the *entire* career is services with no product ML.

3. **Keyword stuffer.** Skill list full of RAG/Pinecone/LLM but career is PM/sales/
   support/etc. → **tier 0**. The skills are decoration; the career is the truth.

4. **Plain-language Tier 5.** The reverse trap: someone who *never says* "RAG" or
   "embeddings" but whose career history shows they built a recommendation or search
   ranking system at a product company → **tier 4-5**. If our ranker scores these
   low, that's the signal we need the embedding layer (Phase 7).

5. **Available-but-weak vs strong-but-stale.** Record `fit_tier` and `avail`
   separately. `overall_tier` should down-weight a strong-fit candidate who is clearly
   unavailable (stale + low response rate), per the JD's "not actually available"
   instruction - but not to zero. A tier-5 fit who's stale is roughly a tier-3 hire.

## How to use it

- Label the stratified sample one candidate at a time. Read the **career history
  titles + industries** first (most reliable), then skills, then signals. Spend ~1-2
  min each; trust your gut, write the deciding factor.
- You don't need perfect labels - you need *consistent* ones. The deciding-factor
  note is what keeps you consistent across a 60-candidate session.
- Keep this file and `labels.csv` in the repo. They are the strongest evidence of
  real engineering at Stage 4, and the basis for your Stage 5 "how did you tune
  without ground truth" answer.
