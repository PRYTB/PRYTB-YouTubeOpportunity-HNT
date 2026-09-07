# PRYTB — SPRINT 10: OPPORTUNITY VALIDATOR / ADVERSARIAL VALIDATION

## 1. Overview & Philosophy

Sprint 10 introduces the **Adversarial Opportunity Validator**, an independent validation framework that subjects Sprint 9 profitability candidates to rigorous analytical stress tests before promotion. 

The primary objective is to answer:
> *Is this apparent opportunity real enough to keep investigating, or is it likely a false positive caused by sample bias, single-channel dominance, single-video dominance, viral spikes, data sparsity, weak economics, production assumptions, semantic mixing, insufficient depth, or unstable evidence?*

The Validator functions with explicit skepticism:
- It **never** increases a candidate's validation score merely because Sprint 9 ranked it highly.
- It calculates independent risk and stability metrics, perturbation deltas, and cross-signal consistency checks.
- It produces a formal `ValidationStatus` and an independent `ValidationScore` (0–100).

---

## 2. Validation Outputs & Statuses

### Validation Status Gate (`ValidationStatus`)

- `PASS`: Strong validation + high confidence (>=60.0%) + high validation score (>=75.0) + low false positive risk (<=35.0) + no critical failures.
- `PASS_WITH_WARNINGS`: Supportive evidence with material uncertainties or warnings remaining.
- `WATCH`: Mixed evidence, moderate fragility, or unresolved dependencies (e.g. Sprint 9 score 50–70).
- `FAIL`: Major contradictory evidence, single-video dependency, extreme fragility, or high false positive risk (>=65.0).
- `INSUFFICIENT_EVIDENCE`: Low coverage (<50%) or low confidence (<40%) preventing meaningful validation.

### Core Validation Metrics

1. **`ValidationScore` (0–100)**: Measure of independent analytical support. Distinct from `ProfitabilityScore`.
2. **`ValidationConfidence` (0–100%)**: Certainty of validation findings based on component coverage and sample size.
3. **`FragilityScore` (0–100)**: Quantifies how severely candidate profitability changes under reasonable analytical perturbations (leave-one-out top video, dominant channel removal, assumption reductions).
4. **`FalsePositiveRisk` (0–100)**: Multi-component risk score combining fragility, channel concentration, sample inadequacy, missing RPM evidence, and cross-signal contradictions.
5. **`SampleAdequacyScore` (0–100)**: Evaluates sample size, channel diversity, historical depth, and age distribution.
6. **`CrossSignalConsistencyScore` (0–100)**: Checks agreement across independent engines (Demand, Outliers, Revenue, Competition, Risk).
7. **`ExpectedViewsStabilityScore` (0–100)**: Assesses statistical stability (IQR spread, leave-one-out median ratio) of Sprint 9 `ExpectedViewsRange`.

---

## 3. False Positive & Challenge Tests

Every candidate cluster is tested against 14 adversarial challenges:

1. **Single-Video Dominance**: Leave-one-out perturbation measuring top video view share (`top_video_view_share > 50%`) and profitability score drop without top video.
2. **Single-Channel Dominance**: Concentration evaluation using `dominant_channel_share > 50%` and Herfindahl-Hirschman Index (HHI).
3. **Top-3 Channel Concentration**: Flagged when top 3 channels control >80% of cluster views.
4. **Outlier Robustness**: Differentiating single extreme viral breakouts from repeatable breakouts across multiple creators.
5. **Temporal Robustness**: Differentiating evergreen demand from recent trend spikes or declining views.
6. **Sample Adequacy**: Penalizing small video samples (<3) or single-channel clusters.
7. **Economic Validation**: Flagging heavy reliance on Tier-A fallback assumptions without observed RPM benchmarks (`ECONOMIC_SIGNAL_ASSUMPTION_HEAVY`, `NO_MONETARY_BENCHMARK`).
8. **Production Validation**: Challenging complexity and feasibility when evidence coverage is low.
9. **Content Depth Validation**: Preserving the Sprint 7 truth that 10/10 content depth is `UNDETERMINED`. Reports `DEPTH_NOT_VALIDATED`.
10. **Semantic Coherence**: Checking title text similarity and detecting obvious semantic outliers without reclustering.
11. **Cross-Signal Contradiction**: Flagging conflicts (e.g. High Demand + High Channel Concentration, High Economic Potential + Zero RPM Evidence).

---

## 4. Counterfactual & Sensitivity Perturbations

For all 10 clusters, safe analytical stress tests are performed in-memory without altering persisted production data:

- **Top Video Removal (`score_without_top_video`)**: Recalculates profitability after removing the highest-view video.
- **Dominant Channel Removal (`score_without_dominant_channel`)**: Recalculates profitability after removing the largest channel.
- **Assumption Reduction**: Applies a 20% penalty to unverified economic/production components.
- **Stress-Adjusted Score (`stress_adjusted_score`)**: Lower bound score under combined worst-case perturbation.

---

## 5. Execution & Persistence

### CLI Pipeline

Run adversarial validation (Read-Only):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts\validate_opportunities.py --json
```

Apply database migration and persist to InsForge DB:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts\migrate_sprint10_schema.py
.\.venv\Scripts\python.exe scripts\validate_opportunities.py --persist
```

### InsForge Persistence & Read-Back Verification

The persistence engine writes to `public.cluster_validation_analyses` and performs strict read-back verification:
- Writes: **10** records
- Read-Back: **10** records
- Unique Clusters: **10**
- Duplicates / Orphans / Missing / Payload Mismatches / Provenance Mismatches: **0**

---

## 6. Provenance & Production Contract

Canonical production contract preserved across Sprint 0–10:
- **Videos**: 83
- **Clusters**: 10
- **Dataset Hash**: `4d81c80e8da54b371c7eb969957ea347fc632d82abd737719141c866f4bfe9ad`
- **Assignments Hash**: `6c0e7bb6aeec75985664becb05f7c61cbfec874c15a6ec7395d60c2996436288`

Tracked Provenance Fields:
- `source_profitability_run_id`
- `source_cluster_run_id`
- `source_revenue_run_id`
- `source_market_run_id`
- `source_production_run_id`
- `methodology_version`: `1.0.0`
