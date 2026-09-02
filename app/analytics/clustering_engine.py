import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score
from app.config.niche_config import niche_config as cfg


class ClusterOptimizer:
    """
    Handles clustering execution, parameter evaluation across ranges (K),
    and selects the optimal reproducible cluster configuration based on silhouette score
    and cluster distribution constraints.
    """
    def __init__(self, min_k: int = cfg.MIN_K, max_k: int = cfg.MAX_K, random_state: int = cfg.RANDOM_STATE):
        self.min_k = min_k
        self.max_k = max_k
        self.random_state = random_state

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
            # Too small to evaluate K range
            labels = np.zeros(n_samples, dtype=int)
            return labels, "SingleClusterFallback", {"k": 1, "n_samples": n_samples}, 1.0

        # Adjust max_k dynamically based on sample size
        effective_max_k = min(self.max_k, n_samples - 1)
        effective_min_k = min(self.min_k, max(2, n_samples // 3))

        if effective_min_k >= n_samples or effective_max_k < effective_min_k:
            # Fallback for very small datasets (e.g. n=3..5)
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
            adjusted_score = score - (0.05 * singletons)

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
        else:
            # Default KMeans
            model = KMeans(n_clusters=k, random_state=self.random_state, n_init=10)
            return model.fit_predict(embeddings)

    def _compute_safe_silhouette(self, embeddings: np.ndarray, labels: np.ndarray) -> float:
        unique_labels = np.unique(labels)
        if len(unique_labels) <= 1 or len(unique_labels) >= len(embeddings):
            return 0.0
        try:
            return float(silhouette_score(embeddings, labels, metric="cosine"))
        except Exception:
            return 0.0
