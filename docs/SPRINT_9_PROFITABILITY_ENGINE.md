# SPRINT 9 — PROFITABILITY ENGINE

## Overview

Sprint 9 introduces the first consolidated economic ranking (`ProfitabilityScore 0–100`) for approved YouTube opportunity clusters.
It evaluates multi-dimensional signals across demand, outlier performance, audience economic value, competition, geography, evergreen longevity, production feasibility/cost, content depth, and format-specific potential.

---

## 1. Critical Monetary Policy

Sprint 9 strictly separates comparative economic indicators from monetary claims.
It defines 5 explicit evidence source types:
- `OBSERVED`
- `EXTERNAL_BENCHMARK`
- `MANUAL_ASSUMPTION`
- `INFERRED`
- `UNKNOWN`

When no RPM benchmark or explicit monetary cost benchmark exists (e.g. `RevenueBenchmarkProvider = EmptyBenchmarkProvider`), monetary outputs remain `unavailable`:
- `RPMRange = unavailable`
- `ExpectedRevenue = unavailable`
- `ExpectedProfit = unavailable`

No RPM constants, country-tier monetary conversions, or revenue figures are ever fabricated. Missing monetary benchmarks never block the calculation of comparative `ProfitabilityScore`.

---

## 2. Two Output Modes

1. **Comparative Mode (Always Available):**
   - Calculates `ProfitabilityScore` (0–100), `Confidence` (0–100), component contribution breakdown, and cluster classification.
   - Operates purely on relative analytical evidence.

2. **Monetary Scenario Mode (Conditional):**
   - Enabled only when explicit RPM and production monetary cost benchmarks exist.
   - Generates `Pessimistic`, `Base`, and `Optimistic` scenarios for `ExpectedRevenue`, `ExpectedCost`, and `ExpectedProfit`.

---

## 3. Robust Expected Views Range

`ExpectedViewsRange` computes `low`, `base`, and `high` view targets using robust percentiles and medians rather than single viral outliers:
- `low`: 25th percentile of cluster view distribution.
- `base`: Median of cluster view distribution.
- `high`: 75th percentile of cluster view distribution.

Formats (Shorts vs Long-form) are tracked and separated to ensure Shorts view counts do not artificially inflate long-form profitability estimates.

---

## 4. Master Prompt Component Weights

The composite `BaseScore` is computed using configurable weights defined in `app/config/profitability_config.py`:

| Component | Weight | Source |
| :--- | :--- | :--- |
| **Demand** | 15% | Robust view distributions & velocity |
| **Outliers** | 15% | Outlier rank score & small-channel success evidence |
| **Revenue Potential** | 20% | Audience economic value & long-form format presence |
| **Competition** | 10% | Inverse Sprint 7 competition score & accessibility |
| **Geography** | 10% | Market tier & geographic audience evidence |
| **Evergreen** | 10% | Sprint 7 evergreen longevity score |
| **Production** | 10% | Inverse Sprint 8 production cost index |
| **Content Depth** | 5% | Sprint 7 depth score (0% weight if UNDETERMINED) |
| **Short Potential** | 5% | Actual Shorts performance signals |

Total component weights sum strictly to 1.0 (100%).

---

## 5. Missing Evidence Policy & Risk Penalty

1. **Coverage-Aware Renormalization:**
   - Missing or UNDETERMINED components (e.g., Content Depth = UNDETERMINED) are excluded from the denominator rather than awarded free points.
   - `component_coverage` (0.0–1.0) measures the fraction of known component weights.

2. **Transparent Risk Penalty:**
   - Applied after `BaseScore`: `ProfitabilityScore = BaseScore - RiskPenalty`.
   - `UNKNOWN` risk levels incur a mandatory safety risk penalty (15.0 pts) and warning to prevent unassessed clusters from appearing risk-free.

---

## 6. Classification Bands

- `0–49`: **DISCARD**
- `50–69`: **WATCH**
- `70–79`: **INTERESTING**
- `80–89`: **STRONG**
- `90–100`: **EXCEPTIONAL**

---

## 7. Data Provenance & InsForge Persistence

Persisted in `public.cluster_profitability_analyses`:
- Canonical contract hashes (`dataset_hash`, `assignments_hash`).
- Source run IDs (`source_cluster_run_id`, `source_revenue_run_id`, `source_market_run_id`, `source_production_run_id`).
- `methodology_version` (`sprint9-v1`).
- Exact payload verification (10 records written, 10 read-back, 0 payload/provenance mismatches).
