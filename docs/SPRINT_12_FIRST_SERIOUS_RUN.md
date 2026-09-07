# Sprint 12 — First Production-Scale Opportunity Discovery Run

## Overview
Sprint 12 executed PRYTB at meaningful production scale across 3,132 production videos and 1,941 unique channels in English and Spanish, strictly evaluating whether the analytical engine discovers useful, specific, non-obvious YouTube opportunities without advancing to Sprint 13 or altering core engine logic.

---

## 1. Collection & Diversity Strategy
- **Seed Manifest**: `config/sprint12_seed_manifest.json` containing 16 seed families (Technology, Software, AI, Cybersecurity, Business, Finance, Education, Productivity, Science, Consumer Problems, Professional Skills, Tools, How-To, Emerging Topics) in English and Spanish.
- **Checkpoint / Quota / Resume**: `scripts/collect_sprint12_dataset.py` tracked `search.list`, `videos.list`, `channels.list`, quota units, page progress, and video ID collection checkpoints (`data/checkpoints/sprint12_checkpoint.json`).
- **Exclusions**: 
  - Excluded test records (including `VID_TEST_INTEGRATION_99`).
  - Global deduplication by `video_id`.
  - Excluded invalid, deleted, or missing videos.
- **Language / Channel Diversity**:
  - Production Videos: 3,132
  - English: 1,700 (54.3%)
  - Spanish: 1,316 (42.0%)
  - Other/Unknown: 116 (3.7%)
  - Unique Channels: 1,941
  - Median Videos/Channel: 1.0
  - P90 Videos/Channel: 3.0
  - Top 1 Channel Share: 0.96%
  - Top 10 Channel Share: 7.22%
  - Channel HHI: 8.9 (Low concentration)

---

## 2. Dataset Contract
- **Contract Artifact**: `data/processed/sprint12_dataset_contract.json`
- **Dataset Hash (`SHA-256`)**: `aff253509f52552097ad25283d3ae3bf3a0af6ab7682f4e79b3497919568ac3e`
- **Seed Manifest Hash (`SHA-256`)**: `24dd5ab551b141b61dec3a2b107f8b290f73ffff4eac11185c7818fa98b32334`

---

## 3. Pipeline Execution Results

### Stage 1: Outliers Engine (Sprint 4)
- **Evaluated Videos**: 3,132
- **Actual Outliers**: 209
- **Small-Channel Outliers**: 81
- **Top 100 Outliers**: 100 (from 75 unique channels)

### Stage 2: Clustering & K Selection (Sprint 5)
- **Method**: TF-IDF (`max_features=1000`, `ngram_range=(1,2)`) + `KMeans` (`n_init=3`)
- **Optimal K Selected**: 17 (Silhouette score: 0.0635)
- **Assignments Hash (`SHA-256`)**: `d98b3e7985e4694e1c4f4a53b84d812869f447d67858a8d5fef8b449b96ef4d2`
- **Total Clusters Mined**: 17

### Stage 3: Revenue & Geography Engine (Sprint 6)
- **Dominant Markets**: Tier 1 US/UK (EN) and Tier 2 ES/MX/AR (ES)
- **Audience Economic Value**: Derived without fabricating missing RPM or revenue benchmarks.

### Stage 4: Market Structure & Depth (Sprint 7)
- **Content Depth Distribution**:
  - `IDEAS_100_PLUS`: 13 clusters
  - `IDEAS_50_PLUS`: 3 clusters
  - `IDEAS_20_PLUS`: 1 cluster
  - `SHALLOW`: 0
  - `UNDETERMINED`: 0

### Stage 5 & 6: Production Risk & Profitability Engines (Sprint 8 & 9)
- **Production Risk**: Evaluated faceless feasibility, copyright risk, and AI assistance potential across 17 clusters.
- **Profitability**: Recalculated composite scores, classification ranges, and risk penalties.

### Stage 7: Opportunity Validator (Sprint 10)
- **Status Breakdown**:
  - `PASS`: 5 clusters
  - `PASS_WITH_WARNINGS`: 12 clusters
  - `WATCH`: 0
  - `FAIL`: 0
  - `INSUFFICIENT_EVIDENCE`: 0

---

## 4. Non-Obviousness Gate & Top Candidates
- **Specific / Actionable Subniches**: 17
- **Generic Broad Terms Count**: 0
- **Non-Obviousness Gate Status**: **PASS**
- **Top Validated Candidates (Sample)**:
  1. **AI Automation & Autonomous Agents** (Viability: 77.16, 225 videos, 128 channels) — `PASS`
  2. **Gobierno en la Nube / IT Cloud Auditing** (Viability: 76.70, 111 videos, 103 channels) — `PASS`
  3. **Software Engineer vs Web Developer Career Guides** (Viability: 76.02, 58 videos, 49 channels) — `PASS`
  4. **Python Web Framework Choice (Django/Flask/FastAPI)** (Viability: 75.75, 185 videos, 131 channels) — `PASS`
  5. **Levantamiento Topográfico / GIS Land Surveying** (Viability: 75.02, 469 videos, 339 channels) — `PASS`

---

## 5. Dashboard Compatibility & Provenance
- Dashboard data service (`dashboard/data_service.py`) updated to support the Sprint 12 dataset hash (`aff253509f5255...`) without breaking historical canonical dataset contracts.
- Provenance lineage fully verified across `dataset_run_id`, `cluster_run_id`, `revenue_run_id`, `market_run_id`, `production_run_id`, `profitability_run_id`, and `validation_run_id`.
