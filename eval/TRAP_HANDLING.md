# Trap handling - quantified

The pool is adversarially built. This doc shows the system defeating each trap with
**numbers, not claims** - current code, full 100K pool. The defeat is structural: the
dominant term (`applied_ml_years`) is career-derived (title + industry), and four
multiplicative gates collapse perfect-on-paper-but-disqualified profiles. No honeypot
IDs are blocklisted.

## 1. Keyword stuffer - skills look strong, the career doesn't back them

A claimed-skill list that reads great but isn't supported by any product-ML career.
The skill term earns some `fit`, but `applied_ml_years` (the dominant, career-derived
term) is ~0 and the JD's disqualifier penalties subtract - so the profile sinks.

| candidate | label | role | core_skill_score | applied_ml_years | product_ratio | penalties | final score | final rank |
|---|---|---|---|---|---|---|---|---|
| **CAND_0028838** | tier 1 | Data Scientist @ Wipro | **3.91** (looks strong) | **0.00** | 0% | 0.90 | 4.80 | **2,044 / 100,000** |
| CAND_0036391 | tier 1 | Computer Vision Engineer @ HCL | 3.22 | 0.00 | 0% | 1.15 | 3.05 | 4,507 |
| CAND_0054059 | tier 3\* | AI Specialist @ InMobi | 3.68 | 0.00 | 100% | 0.40 | 2.75 | 5,265 |

CAND_0028838 lists three core IR skills (core_skill_score 3.91 - top-100 territory on
skills alone) but has **0.00 applied-ML years at a product company** and an
all-services career (penalty 0.90). Net: rank **2,044**, nowhere near the top-100. The
stuffer cannot manufacture career structure, which is what the ranker actually scores.

## 2. Honeypots - impossibility gate strips them from the fit-top-100

Ranked by **`fit` alone (pre-gate)**, 3 internally-impossible profiles reach the
top-100. The impossibility gate (a scale-invariant skill-duration / career-length
ratio check, no ID list) multiplies each to ~0.05 and ejects them.

| candidate | role | yoe | fit-rank (pre-gate) | impossibility | final score | final rank |
|---|---|---|---|---|---|---|
| **CAND_0093547** | Senior ML Engineer @ PhonePe | 2.9 | **76** | **0.050** | 0.518 | **45,895** |
| **CAND_0001610** | ML Engineer @ Dream11 | 3.0 | **86** | **0.050** | 1.005 | **19,378** |
| **CAND_0037000** | Search Engineer @ Unacademy | 2.7 | **99** | **0.050** | 0.595 | **39,382** |

Each claims skill/role durations far exceeding a ~3-year career → ratio ≥ 2.5 →
impossibility 0.05 → score × 0.05. **Honeypots in the final top-100: 0** (the spec's
auto-DQ threshold is 10%). (The count of fit-top-100 honeypots is now 3, up from the 2
reported pre-Phase-9: the core-skill saturation rebalanced the fit-only ordering, so a
third impossible profile floats into the pre-gate top-100 - and is likewise stripped.)

## 3. Over-band senior - seniority gate demotes genuine-but-mis-banded depth

Real ML depth that would rank top-10 on fit, but 2× over the JD's 5-9 band ("we will
probably not move forward" with a senior who drifted from hands-on IC). The seniority
gate is multiplicative, so it bites hard.

| candidate | label | role | yoe | applied_ml_years | rank **without** gate | seniority_gate | final rank **with** gate |
|---|---|---|---|---|---|---|---|
| **CAND_0039754** | tier 3\* | Senior Applied Scientist @ Meta | **16.2** | 8.2 | **~6** | **0.18** | **2,793** |
| CAND_0010770 | - | Recommendation Systems Engineer @ Aganitha | 15.2 | 7.2 | ~48 | 0.28 | 1,562 |
| CAND_0095619 | - | NLP Engineer @ Nykaa | 15.6 | 4.2 | ~68 | 0.24 | 2,440 |

CAND_0039754 would sit at **rank ~6** without the gate (fit score 22.68 - genuine deep
ML). At 16.2 years the gate is 0.18, dropping it to rank **2,793**, exactly where the
other tier-3s sit. This is the documented blunt trade-off (DECISIONS #5): every
over-band profile is demoted because every over-band profile in the validation set was
tier-3. (\* tier 3 here is one of the 8 low-confidence labels, excluded from tuning.)

---

**Summary.** Keyword stuffer → rank 2,044 (career term + penalties). Honeypots →
ejected to ranks 19k-46k (impossibility gate), 0 in the final top-100. Over-band senior
→ rank 2,793 (seniority gate). All three are handled by construction - career-over-skills
scoring plus multiplicative gates - with zero hard-coded candidate IDs.
