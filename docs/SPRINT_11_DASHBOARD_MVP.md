# PRYTB — SPRINT 11 DASHBOARD MVP

## 1. Overview
The Sprint 11 Dashboard MVP provides the first visual presentation layer for **PRYTB — YouTube Opportunity Intelligence**. It translates persisted analytical pipeline outputs from Sprints 5 through 10 into an interactive, read-only Streamlit web application without executing raw multi-table queries or mutating database records.

---

## 2. Launching the Dashboard

### Prerequisites
Activate the project virtual environment (`.venv`):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
```

### Launch Command
Execute the entry point using the venv-safe Streamlit executable:

```powershell
.\.venv\Scripts\streamlit.exe run dashboard\app.py
```

---

## 3. Pages & Features

1. **Overview**:
   - High-level portfolio metrics: Videos analyzed (83), Channels (27), Clusters/Subniches (10), Outliers (12), Validated Candidates (10).
   - Sprint 10 Validation status distribution (`PASS`, `PASS_WITH_WARNINGS`, `WATCH`, `FAIL`).
   - Development dataset disclaimer and data provenance summary (`dataset_hash`, `assignments_hash`, run IDs).
   - API quota and model cost tracking status (`Unavailable / Not tracked`).

2. **Opportunities**:
   - Sortable & filterable table of all 10 candidate clusters.
   - Default sorting prioritizes validation strength (`ValidationScore`, `ProfitabilityScore`).
   - Filters for validation status, profitability classification, score thresholds, false positive risk, fragility, and niche.

3. **Opportunity Detail**:
   - Deep evidence drill-down for selected candidate clusters.
   - Grouped sections:
     - Executive Summary: Positive evidence, contradictory/negative evidence, missing evidence, warnings, critical failures.
     - Profitability & Expected Views: Base/low/high ranges, coverage, and explicit RPM/revenue/cost/profit unavailablity warnings (never renders false `$0` values).
     - Validator & Sensitivity: Validation score, fragility, false positive risk, top video removal, dominant channel removal, stress-adjusted score.
     - Market & Competition (Sprint 7): Competition score, accessibility, HHI, small channel success, outlier diversity, evergreen class, content depth (`UNDETERMINED`).
     - Production Risk (Sprint 8): Complexity, cost index, faceless feasibility, AI assistance, expertise requirement, repeatability, and specific risk levels.
     - Economic & Geography (Sprint 6): Dominant language, market tier, audience economic value.
     - Supporting Videos: Underlying videos table with canonical YouTube links.

4. **Outliers**:
   - Table of strongest video outliers sorted by `OutlierRatio`.
   - Filters for cluster and minimum outlier ratio.

5. **Channels**:
   - Emerging/relevant channel intelligence, video counts in dataset, outlier counts, clusters represented, median views, and small channel indicator.

---

## 7. Internationalization (I18n / L10n)

The dashboard includes full bilingual localization:

- **Supported Languages:**
  - `es` (Español) - Default
  - `en` (English)
- **Language Selector:** Located in the sidebar above page navigation (`Language / Idioma`). Changing selection updates all page elements immediately without data loss.
- **Centralized Architecture (`dashboard/i18n.py`):**
  - All dictionary keys are organized in `TRANSLATIONS["es"]` and `TRANSLATIONS["en"]`.
  - Helper `t(key, lang)` accesses localized strings with fallback handling.
  - `format_enum_presentation(enum_val, lang)` maps internal canonical analytical enums (e.g. `PASS_WITH_WARNINGS`, `WATCH`, `FAIL`) to user-facing strings without altering stored database values.
  - `translate_column_header(col, lang)` dynamically localizes Pandas DataFrame table column headers at render time without mutating DataFrame schema names.
  - `format_number(val, lang)` applies locale-safe numeric formatting (`.` for thousands in Spanish, `,` in English).

---

## 4. Architecture & Data Service Layer

- **Service Layer**: `dashboard/data_service.py` (`DashboardDataService`) wraps InsForge reads and Sprint 5–10 pipeline execution in read-only mode (`persist=False`).
- **View Models**: Strong Pydantic data models (`OpportunityCandidateViewModel`, `VideoViewModel`, `ChannelViewModel`, `DashboardDataset`, `ProvenanceInfo`).
- **Data Provenance & Safety**: Enforces canonical contract validation (`dataset_hash = 4d81c80e8da54b371c7eb969957ea347fc632d82abd737719141c866f4bfe9ad`, `assignments_hash = 6c0e7bb6aeec75985664becb05f7c61cbfec874c15a6ec7395d60c2996436288`). If a mismatch occurs, analytical ranking rendering is blocked and a visible error is raised.
- **Caching**: Streamlit `@st.cache_data` caches read-only dataset structures, with a **Refresh Data** control in the sidebar to safely clear and reload.

---

## 5. Development Dataset Disclaimer
Because the dataset is currently bounded to 83 videos across 10 clusters for system validation:
- Prominent banners are rendered on both **Overview** and **Opportunity Detail** pages indicating:
  > **DEVELOPMENT DATASET** — These rankings are for system validation. They are not final market recommendations. Sprint 12 will run 10K–20K videos.
