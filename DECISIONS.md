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
