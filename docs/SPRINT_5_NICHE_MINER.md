# PRYTB — SPRINT 5: NICHE MINER

## 1. Description
The Niche Miner transforms videos, titles, descriptions, and outlier signals into coherent, actionable thematic clusters structured hierarchically (`Niche` → `Subniche` → `Microniche`). It avoids generic categorizations (e.g. "Technology", "Business") by discovering specific market subsegments while keeping semantic representations independent from statistical metrics.

---

## 2. Architecture & Pipeline Flow

```text
videos + titles/descriptions
↓
Text Normalization (Unicode NFKC, noise removal, technical key term preservation)
↓
Semantic Representation (SemanticProvider: TF-IDF L2 Normalized / OmniRoute)
↓
Optimal Clustering (ClusterOptimizer: Silhouette Score over Cosine Distance)
↓
Channel Diversity & Outlier Crossover Integration
↓
Centroid-based Representative Title Selection
↓
Structured Labeling (ClusterLabeler: JSON schema LLM / Deterministic Fallback)
↓
Scoring (ClusterConfidence & ClusterSignalScore)
↓
Persistence (InsForge `clusters` and `subniches` tables with unique `run_id`)
```

---

## 3. Key Components & Implementation Details

### 3.1 Semantic Provider Abstraction
Defined in `app/analytics/semantic_provider.py`:
- Interface: `SemanticProvider` with `embed_texts(texts: List[str]) -> np.ndarray`.
- Implementations:
  - `TFIDFLocalSemanticProvider`: Deterministic, local vectorization using `TfidfVectorizer` with $L_2$ vector normalization and fallback handling for empty or low-term matrices.
  - `OmniRouteEmbeddingProvider`: Placeholder structure ready for direct OmniRoute API embedding endpoint integration.

### 3.2 Text Normalization & Term Preservation
Defined in `app/analytics/text_normalizer.py`:
- `clean_text_for_embedding(title, description, max_desc_len=200)`:
  - Combines title and truncated description.
  - Normalizes Unicode (NFKC), removes URLs, standardizes whitespace.
  - Preserves technical terms intact (e.g. `GPT-5`, `Windows 11`, `RTX 5090`, `Python`, `ChatGPT`).
  - Strict separation: Excludes statistical metrics (`views`, `subscribers`, `outlier_ratio`) from semantic embeddings.

### 3.3 Reproducible Clustering & Parameter Selection
Defined in `app/analytics/clustering_engine.py`:
- `ClusterOptimizer.fit_optimal_clusters`:
  - Evaluates K values from $K_{min}$ to $K_{max}$ (configurable in `NicheConfig`).
  - Evaluates cosine distance using Silhouette Score while penalizing singleton clusters.
  - Returns optimal labels, algorithm name, parameters, and silhouette score.

### 3.4 Cluster Quality & Channel Diversity Metrics
Defined in `app/analytics/cluster_analyzer.py`:
- `unique_channels`: Count of distinct YouTube channels in cluster.
- `dominant_channel_share`: $\frac{\max(\text{videos\_from\_one\_channel})}{\text{cluster\_video\_count}}$.
- Diversity Levels:
  - `HIGH_DIVERSITY`: `dominant_channel_share < 0.40`
  - `MEDIUM_DIVERSITY`: `0.40 <= dominant_channel_share <= 0.60`
  - `LOW_DIVERSITY`: `dominant_channel_share > 0.60` (Triggers `DOMINANT_CHANNEL_WARNING`)

### 3.5 Outlier Crossover Integration
Cross-references cluster video IDs with Sprint 4 `OutlierEngine` results:
- Measures `outlier_count`, `strong_outlier_count`, `major_outlier_count`, `median_outlier_ratio`, and `max_outlier_ratio`.

### 3.6 Centroid-Based Representative Titles
Selects 3–5 representative titles per cluster based on minimum Euclidean distance to the cluster's semantic centroid.

### 3.7 Structured Labeling & Fallback
Defined in `app/analytics/labeler.py`:
- Asks LLM for structured JSON (`niche`, `subniche`, `microniche`, `summary`, `confidence`).
- Fallback: `DeterministicLabeler` extracts top n-gram keywords and constructs hierarchical fallback labels if LLM is unavailable or fails validation.

### 3.8 Confidence & Signal Ranking
- `ClusterConfidence` (0–100): Combines semantic cohesion, cluster size, unique channels, label coherence, and applies a heavy penalty for low channel diversity.
- `ClusterSignalScore`: Exploratory score combining semantic quality ($30\%$), outlier density ($35\%$), channel diversity ($20\%$), and cluster confidence ($15\%$).

---

## 4. Configuration
Defined centrally in `app/config/niche_config.py`:
- `K_MIN = 2`, `K_MAX = 15`
- `MIN_CLUSTER_SIZE = 2`
- `DOMINANT_CHANNEL_THRESHOLD = 0.60`
- `WEIGHT_SEMANTIC = 0.30`, `WEIGHT_OUTLIER = 0.35`, `WEIGHT_DIVERSITY = 0.20`, `WEIGHT_CONFIDENCE = 0.15`

---

## 5. Script Usage & Execution
Run the main mining CLI script:
```powershell
.\.venv\Scripts\python.exe scripts/mine_niches.py --limit 100 --persist
```

Outputs summary statistics, top clusters, and runs the Sprint 4 Top Outlier Dominance Test.
