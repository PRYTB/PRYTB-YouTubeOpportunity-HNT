import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from app.config.niche_config import niche_config as cfg


def detect_near_duplicates(texts: List[str], similarity_threshold: float = 0.88) -> List[List[int]]:
    """
    Detects groups of near-duplicate titles using TF-IDF cosine similarity.
    Returns list of groups where each group is a list of title indices.
    """
    if not texts or len(texts) < 2:
        return []

    from app.analytics.semantic_provider import TFIDFLocalSemanticProvider
    provider = TFIDFLocalSemanticProvider(max_features=300, ngram_range=(1, 2))
    embeddings = provider.embed_texts(texts)

    sim_matrix = cosine_similarity(embeddings)
    n = len(texts)
    visited = set()
    groups = []

    for i in range(n):
        if i in visited:
            continue
        group = [i]
        for j in range(i + 1, n):
            if j not in visited and sim_matrix[i, j] >= similarity_threshold:
                group.append(j)
                visited.add(j)
        if len(group) > 1:
            visited.add(i)
            groups.append(group)

    return groups


class ClusterOptimizer:
    """
    Handles clustering execution, parameter evaluation across ranges (K=3..12),
    algorithm comparisons (KMeans vs Agglomerative), and selects optimal reproducible cluster configuration.
    """
    def __init__(self, min_k: int = cfg.MIN_K, max_k: int = cfg.MAX_K, random_state: int = cfg.RANDOM_STATE):
        self.min_k = min_k
        self.max_k = max_k
        self.random_state = random_state

    def compare_and_evaluate(
        self,
        embeddings: np.ndarray,
        k_min: int = 3,
        k_max: int = 12
    ) -> Dict[str, Any]:
        """
        Evaluates KMeans and Agglomerative across k in [k_min..k_max].
        Returns detailed evaluation metrics for each combination.
        """
        n_samples = len(embeddings)
        if n_samples < 3:
            return {}

        results = []
        eff_min_k = max(2, min(k_min, n_samples - 1))
        eff_max_k = min(k_max, n_samples - 1)

        for algo in ["kmeans", "agglomerative"]:
            for k in range(eff_min_k, eff_max_k + 1):
                labels = self._fit_single(embeddings, k=k, algorithm=algo)
                score = self._compute_safe_silhouette(embeddings, labels)
                
                counts = np.bincount(labels[labels >= 0]) if len(labels) > 0 else np.array([])
                min_size = int(np.min(counts)) if len(counts) > 0 else 0
                max_size = int(np.max(counts)) if len(counts) > 0 else 0
                avg_size = float(np.mean(counts)) if len(counts) > 0 else 0.0
                singletons = int(np.sum(counts == 1)) if len(counts) > 0 else 0

                results.append({
                    "algorithm": algo,
                    "k": k,
                    "silhouette": round(score, 4),
                    "min_cluster_size": min_size,
                    "max_cluster_size": max_size,
                    "average_cluster_size": round(avg_size, 2),
                    "singleton_clusters": singletons,
                    "labels": labels
                })

        return {"evaluations": results}

    def fit_optimal_clusters(
        self,
        embeddings: np.ndarray,
        algorithm: str = "kmeans"
    ) -> Tuple[np.ndarray, str, Dict[str, Any], float]:
        """
        Fits clustering algorithm on embeddings. Evaluates range of K to select optimal K.
        Returns:
            - labels: array of cluster assignments (0..K-1)
            - selected_algorithm_name: str
            - selected_parameters: dict
            - best_silhouette_score: float
        """
        n_samples = len(embeddings)
        if n_samples == 0:
            return np.array([]), algorithm, {"k": 0}, 0.0

        if n_samples < 3:
            labels = np.zeros(n_samples, dtype=int)
            return labels, "SingleClusterFallback", {"k": 1, "n_samples": n_samples}, 1.0

        effective_max_k = min(self.max_k, n_samples - 1)
        effective_min_k = min(max(3, self.min_k), max(2, n_samples // 4))

        if effective_min_k >= n_samples or effective_max_k < effective_min_k:
            labels = self._fit_single(embeddings, k=min(2, n_samples), algorithm=algorithm)
            score = self._compute_safe_silhouette(embeddings, labels)
            return labels, algorithm, {"k": min(2, n_samples)}, score

        best_score = -1.0
        best_k = effective_min_k
        best_labels = None

        for k in range(effective_min_k, effective_max_k + 1):
            labels = self._fit_single(embeddings, k=k, algorithm=algorithm)
            score = self._compute_safe_silhouette(embeddings, labels)
            
            # Penalize single-item clusters slightly to favor cohesive groups
            counts = np.bincount(labels)
            singletons = np.sum(counts == 1)
            adjusted_score = score - (0.04 * singletons)

            if adjusted_score > best_score or best_labels is None:
                best_score = score
                best_k = k
                best_labels = labels

        if best_labels is None:
            best_labels = np.zeros(n_samples, dtype=int)
            best_k = 1
            best_score = 0.0

        params = {
            "k": int(best_k),
            "algorithm": algorithm,
            "min_k_tested": effective_min_k,
            "max_k_tested": effective_max_k,
            "random_state": self.random_state
        }

        return best_labels, algorithm.lower(), params, float(best_score)

    def _fit_single(self, embeddings: np.ndarray, k: int, algorithm: str) -> np.ndarray:
        if algorithm.lower() == "agglomerative":
            model = AgglomerativeClustering(n_clusters=k)
            return model.fit_predict(embeddings)
        elif algorithm.lower() == "dbscan":
            model = DBSCAN(eps=0.5, min_samples=2, metric="cosine")
            return model.fit_predict(embeddings)
        else:
            # Default KMeans
            model = KMeans(n_clusters=k, random_state=self.random_state, n_init=10)
            return model.fit_predict(embeddings)

    def _compute_safe_silhouette(self, embeddings: np.ndarray, labels: np.ndarray) -> float:
        valid_mask = labels >= 0
        if np.sum(valid_mask) < 3:
            return 0.0
        
        filtered_embeddings = embeddings[valid_mask]
        filtered_labels = labels[valid_mask]
        
        unique_labels = np.unique(filtered_labels)
        if len(unique_labels) <= 1 or len(unique_labels) >= len(filtered_embeddings):
            return 0.0
        try:
            return float(silhouette_score(filtered_embeddings, filtered_labels, metric="cosine"))
        except Exception:
            return 0.0

