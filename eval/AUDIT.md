# Ranking audit - leak hunt on the 80%+ score drivers

Audited state: branch `phase9-assessment-corroboration` @ `ccfc805` (includes the
assessment-corroboration signal). The score is

    final = max(0, fit − penalties) × behavior × location × impossibility × seniority

where `fit` is dominated by `applied_ml_years` (w=2.2, saturated), `core_skill_score`
(w=1.5), the band terms (`band_fit` 1.2 + `seniority_gate`), and `shipped_system`
(1.0). Method: re-score the full 100K, evaluate against `eval/labels.csv` with the
**8 low-confidence labels excluded** (CAND_0081846, _0086022, _0088025, _0011162,
_0075574, _0039754, _0054059, _0050765 → 52 labels). No scoring was changed; the one
proposed change is validated and listed at the end for approval.

---

## 1. Top-10 ideal-candidate audit - CLEAN (0 flagged)

Checklist boxes: **6-8 yr**, **4-5 yr applied ML @ product**, **shipped a
ranking/search/rec system**, **retrieval + eval depth** (`core≥1.5` & eval signal),
**India / relocate**, **active + responsive** (open, idle ≤180d, resp ≥40%),
**corroborated skills** (a relevant skill with assessment ≥50 or ≥20 endorsements).

| # | id | title @ company | yoe | amlY | boxes | miss |
|---|----|----|----|----|----|----|
| 1 | CAND_0081846 | Lead AI Engineer @ Razorpay | 6.7 | 6.6 | 7/7 | - |
| 2 | CAND_0006557 | NLP Engineer @ Paytm | 7.9 | 7.8 | 7/7 | - |
| 3 | CAND_0086022 | Senior Applied Scientist @ Sarvam AI | 5.3 | 5.3 | 6/7 | 6-8 (yoe 5.3, in 5-9 band) |
| 4 | CAND_0018499 | Senior ML Engineer @ Zomato | 7.2 | 7.2 | 7/7 | - |
| 5 | CAND_0086151 | Recommendation Systems Engineer @ Wysa | 7.7 | 7.6 | 7/7 | - |
| 6 | CAND_0011162 | Recommendation Systems Engineer @ upGrad | 5.8 | 5.7 | 6/7 | 6-8 (yoe 5.8, in band) |
| 7 | CAND_0068811 | Applied ML Engineer @ Freshworks | 8.0 | 7.9 | 7/7 | - |
| 8 | CAND_0075574 | ML Engineer @ Haptik | 5.7 | 5.7 | 6/7 | 6-8 (yoe 5.7, in band) |
| 9 | CAND_0077337 | Staff ML Engineer @ Paytm | 7.0 | 6.9 | 7/7 | - |
| 10 | CAND_0070398 | ML Engineer @ Genpact AI | 7.2 | 7.1 | 7/7 | - |

**No top-10 candidate misses ≥2 boxes.** All 10 are product-company ML (prod=100%),
shipped a system, show eval depth, are India-based + open + responsive, and have
≥1 assessment/endorsement-backed relevant skill. The only "misses" are three
candidates at yoe 5.3-5.8 - below the 6-8 *ideal* but squarely inside the JD's stated
**5-9** band, so these are checklist-strictness artifacts, not gaps. The top-10 (50% of
the composite via NDCG@10) is sound.

## 2. Plain-language Tier-5 sweep - no genuine fit lost to vocabulary

Query: strong career signal (`applied_ml_years ≥ 3`, `product_ratio ≥ 50%`) **and**
final rank > 200 → **692 candidates**. Why each is buried:

| reason | count | correct down-weight? |
|---|---|---|
| behavioral gate (stale/unavailable/unresponsive) | 275 | ✅ JD: "down-weight a 6-month-idle, 5%-response candidate" |
| modest fit, no suppression (just not top-100) | 196 | ✅ expected competition |
| penalty (CV-only / consulting / title-chasing) | 71 | ✅ JD disqualifiers |
| low core & no shipped signal ("VOCAB?") | 70 | see below |
| location gate (outside India, not relocating) | 61 | ✅ JD: "outside India case-by-case" |
| impossibility gate (honeypot) | 11 | ✅ |
| seniority gate (16-yr over-band) | 8 | ✅ JD over-band disqualifier |

Of the 70 "low core & no shipped", the 60 with **no** gate/penalty suppression were
inspected directly. Every one is a **Junior ML Engineer / Data Scientist / Computer
Vision / AI Research** title with no retrieval/ranking/rec skills and no shipped-system
or eval signal (e.g. CAND_0002706 *Junior ML Engineer @ Zoho*, core=0.0; CAND_0069503
*Computer Vision Engineer @ Locobuzz*). These genuinely lack the role's **hard**
requirements (embeddings/retrieval, ranking eval), so their mid-pack rank (200-500) is
correct - they get full career credit but not top-100 specialization. None is a hidden
IR/ranking system our vocabulary failed to read.

**Conclusion: no genuine plain-language Tier-5 fit is buried by a vocabulary gap.**
The dominant career term (`applied_ml_years`) is derived from **title + industry**, not
skill keywords, so a "built a recsys at a product company" profile scores high whether
or not it says "RAG/Pinecone". This is the evidence that **embeddings are not needed** -
the misses are availability/seniority/location/specialization, not lexical.

## 3. MAP-tail check (ranks 50-100) - CLEAN

- Scores **monotonic non-increasing**; boundary is smooth (rank 50 = 21.19, rank 100 =
  17.55, rank 101 = 17.40 - no cliff, no inversion).
- **No near-impossible profiles**: min impossibility in the tail = **0.807** (floor 0.5);
  lowest five are 0.807 / 0.874 / 0.912 / 0.955 / 0.979.
- Archetype mix: **40 `ideal`, 11 `solid`** - the 11 `solid` are genuine careers with
  lower retrieval depth or no shipped-system signal, correctly ordered below the 40.
- Tier mix: all 51 are **unlabeled** (the 60-label set targets top picks + low strata,
  none landed in 50-100), so the tail can't be tier-checked directly, but the digests
  are sensible best-available adjacents (Senior DS @ Sarvam, AI Eng @ PolicyBazaar,
  Staff MLE @ LinkedIn, etc.).

## 4. Behavioral-weight sensitivity - top-10 fully immune

Re-scored with the behavioral multiplier's deviation from 1.0 scaled by ×0.5 and ×2.0:

| variant | top-50 changed rank | dropped out of top-50 | new entrants |
|---|---|---|---|
| halved (×0.5) | 32 | 4 | 4 |
| doubled (×2.0) | 9 | 1 | 1 |

- **All 10 top-10 candidates have `behavior_mult = 1.00`** (perfect availability), so
  their rank is **unchanged** under both halving and doubling. **No top-10 candidate is
  sensitive to behavioral weighting** - the NDCG@10 driver does not depend on this knob.
- The churn is confined to ranks 11-50, where behavioral penalties actively (and
  correctly) shape order; halving lifts penalized candidates (more churn), doubling
  sinks them (less churn among the already-clean top-50). This is the gate working as
  intended, not a leak.

## 5. FINDING (leak): `core_skill_score` is an unbounded sum and the single largest top term

The one real issue. `core_skill_score` is `Σ` over matched core skills (each
≈0.3-1.25 after duration cap + corroboration) with **no saturation**, unlike
`applied_ml_years`. Consequences:

- For #1 (CAND_0081846): `core_skill_score` contributes **13.95** vs `applied_ml_years`
  **12.04** - skills outweigh career at the top, inverting the documented
  "career over skills" thesis (DECISIONS #3).
- Top-100 `core_skill_score`: median **4.61**, max **9.30**; **40/100** exceed 5, i.e.
  for ~40% of the top-100 the *breadth* of the listed core-skill list is the largest
  single fit term.
- Risk: a candidate who lists many vector-DB/IR skills (each with plausible duration)
  can accrue a runaway core term and edge out a candidate who shipped one strong system
  but lists fewer core skills - rewarding list-breadth over depth.

This has **not** produced a validated failure (NDCG@10 = 1.0, no FALSE), and duration
capping + corroboration + the impossibility gate keep pure stuffers out. But it is a
latent leak in the highest-weight region, so a saturation was tested.

**Validated mitigation** - saturate `core_skill_score` with diminishing returns
(`core_eff = K·(1 − e^(−core/K))`), mirroring the existing `applied_ml_years`
saturation. Filtered-52 labels, before → after:

| variant | NDCG@10 | NDCG@50 | Kendall τ | FALSE | MISS |
|---|---|---|---|---|---|
| **baseline (no cap)** | 1.0000 | 0.9980 | +0.7649 | 0 | 0 |
| hard cap @4 | 1.0000 | 0.9980 | +0.7649 | 0 | 0 |
| hard cap @5 | 1.0000 | 0.9970 | +0.7614 | 0 | 0 |
| **soft-sat K=4** | 1.0000 | **0.9985** | **+0.7703** | 0 | 0 |
| soft-sat K=5 | 1.0000 | 0.9985 | +0.7685 | 0 | 0 |
| soft-sat K=6 | 1.0000 | 0.9984 | +0.7685 | 0 | 0 |

**soft-sat K=4** improves both movable metrics (τ +0.7649 → +0.7703, NDCG@50
0.9980 → 0.9985) with no NDCG@10 regression and **no new FALSE/MISS** - it clears the
keep-rule and re-aligns the top with the career-first thesis. The gain is small on a
52-label proxy, but the change is structurally motivated (an unbounded largest term)
and consistent with the existing saturation pattern.

---

## Proposed change for approval (not applied)

**P1 - saturate `core_skill_score` (soft-sat K=4) in `src/score.py`.** Add, mirroring
`_saturate_ml_years`:

```python
CORE_SKILL_SAT = 4.0   # diminishing returns on listed core skills (breadth ≠ depth)
def _saturate_core(x): return CORE_SKILL_SAT * (1 - math.exp(-x / CORE_SKILL_SAT))
```

and apply it to `core_skill_score` in `fit_score` (no `WEIGHTS` value changes).
Validation delta is the table above (τ +0.0054, NDCG@50 +0.0005, 0 FALSE). If
approved, this regenerates `submission.csv` (top order shifts toward career-weighted;
honeypot=0 and determinism re-verified before commit). **K=6** is a gentler alternative
(τ +0.7685) if a smaller departure from current behavior is preferred.

No other change is proposed: the top-10, the MAP tail, the behavioral gate, and the
vocabulary are all behaving as designed.
