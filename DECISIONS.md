# DECISIONS — design rationale (Stage 5 defense)

One short entry per major choice: **the decision**, **the alternative**, **why**.
This is interview prep — honest, not promotional.

---

### 1. Feature-based scoring, not embedding/keyword similarity

**Decision.** Score each candidate as a transparent function of interpretable
features (applied-ML years at product companies, core IR skills, shipped-system
evidence, behavioral signals), where every point is traceable to a fact in the
profile.

**Alternative.** Embed the JD and each profile with a sentence model and rank by
cosine similarity — the default hackathon move.

**Why.** The dataset is *built to punish that*. The JD says so explicitly ("the right
answer is not the most AI keywords") and seeds keyword-stuffers, plain-language fits,
and ~80 honeypots. Cosine similarity ranks a keyword-stuffed "Marketing Manager" and
an impossible honeypot highly, which is a Stage-3 disqualifier. A feature scorer makes
those failures structurally impossible and produces a defensible reason per candidate.
Embeddings remain an *optional additive term* (Phase 7) to be added only if validation
showed missed plain-language fits — it didn't, so we didn't add unjustified complexity
(the "framework enthusiast" failure mode the JD warns about).

### 2. Multiplicative gates, not one additive sum

**Decision.** `final = max(0, fit − penalties) × behavior × location × impossibility ×
seniority`. Availability, location, internal consistency, and over-band are
*multipliers*, not addends.

**Alternative.** Fold everything into one weighted sum.

**Why.** Some properties are vetoes, not features. A perfect-on-paper candidate who
hasn't logged in for six months is *not actually hireable* — the JD says to down-weight
exactly this. An additive penalty lets a high enough skill score paper over
unavailability; a multiplier collapses the whole score, which is the correct semantics.
It also keeps each gate independently interpretable ("× 0.6 because not open to work").

### 3. Trust career structure over skills and free-text prose

**Decision.** Classify roles from **title + industry**; treat the skill list as weak
corroboration and free-text descriptions as low-trust noise.

**Alternative.** Trust the self-reported skills inventory, or mine the description text.

**Why.** Exploring the data showed descriptions are partly shuffled/noisy and skill
lists are the stuffer's main weapon. The career history — what roles, at what kind of
company, for how long — is the hardest signal to fake and the one the JD says to read
("if their career history shows they built a recommendation system... they're a fit").
So the decisive signal is `applied_ml_years at product companies`, derived from titles
and industries, not from the words a candidate chose to list.

### 4. Honeypots caught by internal-consistency math, no blocklist

**Decision.** `impossibility_score` is a scale-invariant ratio gate: if a skill (or
role tenure) duration far exceeds the person's total career length, the profile is
internally contradictory and the gate collapses toward zero. Graduated, not binary.

**Alternative.** Hard-code the known honeypot IDs, or special-case them.

**Why.** The spec says honeypots are identifiable "through careful profile inspection"
and that "a good ranking system should naturally avoid them" — hard-coding IDs would
fail the hidden test set and is exactly the brittle move the evaluation filters out.
A ratio check generalizes to unseen honeypots and is itself an explainable feature. We
verified it on the *final* top-100 (not just top-by-fit): 0 honeypots, while the
top-by-fit set contained 2 the gate removed.

### 5. The tuning fix: saturate experience, gate the band

**Decision.** Give `applied_ml_years` a soft cap (full credit to ~5 yrs, shallow slope
after) and convert the seniority band from a weak additive bonus into a *multiplicative
gate* (1.0 through 5–9, steep falloff beyond).

**Alternative.** Bump the additive band penalty's weight; or leave it.

**Why.** Validation surfaced one systematic flaw: a 16-year profile (~2× the ideal
band) at rank 3. Diagnosis showed the additive band term (weight ~1) was
*structurally* too weak to move a 30-point profile — zeroing it removed barely a point.
Saturation stops raw seniority from dominating the top term; the gate makes "well over
band" actually bite. This dropped the 16-year profile to ~rank 2100 (where the other
tier-3s sit), raised NDCG@10 0.87→0.92, and buried no genuine fit. It is a *structural*
fix, not weight-fiddling to a number.

**The honest trade-off.** The gate keys on years-of-experience as a *proxy* for the
JD's real concern (hands-on recency — does the senior still ship code?). It is blunt:
every over-band profile is demoted, because every over-band profile in our validation
set was tier-3. A genuinely strong over-band hands-on IC would also be demoted — but no
such profile existed to calibrate against, and softening the gate would mean tuning to
an unobserved case. The gate floor is the knob to revisit if Stage-3 data shows such
profiles.

### 6. Validation without ground truth: stratified blind labeling

**Decision.** With hidden labels and only 3 submissions, build an internal validation
set: 60 stratified profiles (top picks / high-skill-low-ML / mid / random),
hand-labeled 0–5 **blind** to the model's score, across **two independent passes**
(96.7% self-agreement). Tune to NDCG/Kendall-tau plus a MISS/FALSE table.

**Alternative.** Tune by eyeballing the top-100, or by burning submissions.

**Why.** Eyeballing only sees what the model already ranks high — it can't catch buried
fits, so it makes the evaluation circular. Hiding the model's score/rank during
labeling breaks that circularity. The high-skill-low-ML stratum is the stuffer trap on
purpose. Two passes quantify our own labeling noise so we don't overfit to it. This is
also the answer to "how did you tune without ground truth" at Stage 5 — and the labels
are committed (`eval/labels.csv`) as evidence.

### 7. One tunable knob, single source of truth

**Decision.** All vocabularies live in `vocab.py`; all scoring weights in
`score.py:WEIGHTS`; classification and the honeypot gate each in one module imported
everywhere.

**Alternative.** Inline weights and keyword lists where they're used.

**Why.** Tuning should never mean hunting through logic, and an auditor (or
interviewer) should find every value in one place. It also made the Phase-4 fix a
localized, reviewable change rather than a scatter of edits.

### 8. Assessment-score corroboration on the skill term (kept, but marginal)

**Decision.** Multiply each relevant (core/nice) skill's contribution by a
corroboration factor centered at 1.0, driven by Redrob signal #9
(`skill_assessment_scores`) and per-skill `endorsements`: assessment ≥50 boosts up
to +25%, <50 discounts down to −40%, an "advanced/expert" claim the assessment
contradicts (<40) takes an extra ×0.8, *absent* assessment stays neutral, and
endorsements only nudge upward. No `WEIGHTS` value changed; the lever is a new
modifier inside `features.py`, behind a `USE_ASSESSMENT_CORROB` toggle.

**Alternative.** (a) Ignore the signal — it was the highest-value untapped one.
(b) Penalise *absent* assessments too, or fold it into the impossibility gate.

**Why.** It is the direct counter to the keyword-stuffer trap: a claimed "expert"
skill the platform's own assessment scores low is exposed (honeypot CAND_0000011 —
"advanced" Recommendation Systems, assessment 29.8 — is discounted; the genuine fit
CAND_0000031, FAISS 68 / MLflow 75, is boosted). We rejected penalising *absence*
because coverage is sparse — only ~8% of relevant skills (and 18% of advanced/expert
core skills) carry an assessment, so absence is the norm even for genuine experts;
docking it would punish real fits. Endorsements are 100%-dense but noisy, so they
only ever boost.

**The honest result.** Validated on the hand-labeled set (52 labels, 8
low-confidence excluded), before → after: NDCG@10 1.0000 → 1.0000 (already at
ceiling), NDCG@50 0.9975 → 0.9980, Kendall τ-b +0.7632 → +0.7649, FALSE 0 → 0,
MISS 0 → 0. It clears the keep-rule (τ up, NDCG@50 not down, no new FALSE) and the
movement is qualitatively correct — but the gain is *small*, because NDCG@10 was
maxed and only ~20/52 labels carry the signal on a relevant skill (just one has the
low-backed-expert case). Kept on the discipline "kept only if it measurably helps
and never hurts"; it is the kind of signal whose value should grow on the full
hidden set, where assessment coverage and stuffer density are higher than in our
small proxy. The honeypot guarantee (0 impossible profiles in the final top-100)
and byte-for-byte determinism are preserved.

### 9. Saturate core_skill_score — thesis restoration (audit-driven)

**Decision.** Pass `core_skill_score` through a diminishing-returns saturation
(`core_eff = K·(1 − e^(−core/K))`, K=6) in `fit_score`, mirroring the existing
`applied_ml_years` cap. No `WEIGHTS` value changed.

**Alternative.** Leave it as an unbounded sum; or a hard cap.

**Why.** The Phase-9 audit (`eval/AUDIT.md` §5) found a leak in the highest-weight
region: `core_skill_score` is a *sum* over matched core skills with no cap, so it had
grown into the single largest fit term — at the pre-change #1 it contributed 13.95 vs
12.04 for `applied_ml_years`, and 40/100 of the top-100 had core>5. That inverts the
core thesis (career structure over a listed skill set, DECISIONS #3) and rewards
*breadth* of a keyword list over depth/shipping evidence — the exact failure the
dataset is built to punish. Saturation restores the ordering: the first few genuine
core skills earn near-full credit while extra listed skills add little, so a deep
shipper is no longer edged out by a long skill list. A hard cap was rejected as it
flattens legitimate differences just below the cap; soft saturation preserves them.

**The honest result.** Validated on the hand-labeled set (52 labels, 8 low-confidence
excluded). Incremental over the corroboration signal (#8), before → after:
NDCG@10 1.0000 → 1.0000, NDCG@50 0.9980 → 0.9984, Kendall τ-b +0.7649 → +0.7685,
FALSE 0 → 0, MISS 0 → 0 — both movable metrics improve, none regress. The top-10 set
is unchanged (no genuine deep fit evicted; re-audited clean, still 0 missing ≥2 JD
boxes), but re-ordered toward career: the candidate previously ranked #1 purely on a
core=9.3 skill list moved to #3, behind stronger-career profiles. K=6 (gentler) was
chosen over the marginally-better K=4 (τ +0.7703) to minimise departure from validated
behaviour. Cumulatively across Phase-9 (#8 + #9), τ moved +0.7632 → +0.7685 and NDCG@50
0.9975 → 0.9984. Honeypot=0 and byte-for-byte determinism preserved; submission.csv
regenerated.
