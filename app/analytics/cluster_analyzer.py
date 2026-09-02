import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter
from app.models.outliers import VideoOutlierResult
from app.config.niche_config import niche_config as cfg


def calculate_median(values: List[float]) -> Optional[float]:
    valid = [v for v in values if v is not None and not np.isnan(v)]
    if not valid:
        return None
    return float(np.median(valid))


def analyze_channel_diversity(channel_ids: List[str]) -> Tuple[int, float, str, List[str]]:
    """
    Calculates unique channels count, dominant channel share, diversity category, and warnings.
    """
    warnings = []
    if not channel_ids:
        return 0, 0.0, "LOW_DIVERSITY", ["Cluster contains no channel data."]

    total_videos = len(channel_ids)
    counts = Counter(channel_ids)
    unique_channels = len(counts)
    most_common_count = counts.most_common(1)[0][1]
    
    dominant_channel_share = round(most_common_count / total_videos, 4)

    if dominant_channel_share > cfg.LOW_DIVERSITY_SHARE:
        diversity_category = "LOW_DIVERSITY"
        warnings.append(f"Cluster is dominated by a single channel ({dominant_channel_share * 100:.1f}% share).")
    elif dominant_channel_share <= cfg.HIGH_DIVERSITY_SHARE and unique_channels >= cfg.MIN_CHANNELS_HIGH_DIVERSITY:
        diversity_category = "HIGH_DIVERSITY"
    else:
        diversity_category = "MEDIUM_DIVERSITY"

    return unique_channels, dominant_channel_share, diversity_category, warnings


def cross_reference_outliers(
    cluster_video_ids: List[str],
    outliers_map: Dict[str, VideoOutlierResult]
) -> Dict[str, Any]:
    """
    Crosses cluster video IDs with Sprint 4 Outlier Engine results.
    Calculates outlier statistics without altering semantic embeddings.
    """
    outlier_count = 0
    strong_count = 0
    major_count = 0
    ratios = []

    for v_id in cluster_video_ids:
        outlier_res = outliers_map.get(v_id)
        if outlier_res:
            if outlier_res.is_strong_outlier:
                strong_count += 1
            if outlier_res.is_major_outlier:
                major_count += 1
            if outlier_res.is_strong_outlier or outlier_res.is_major_outlier or outlier_res.is_extreme_outlier:
                outlier_count += 1

            if outlier_res.outlier_ratio is not None:
                ratios.append(outlier_res.outlier_ratio)

    median_ratio = calculate_median(ratios) if ratios else None
    max_ratio = max(ratios) if ratios else None

    return {
        "outlier_count": outlier_count,
        "strong_outlier_count": strong_count,
        "major_outlier_count": major_count,
        "median_outlier_ratio": round(median_ratio, 4) if median_ratio is not None else None,
        "max_outlier_ratio": round(max_ratio, 4) if max_ratio is not None else None,
    }


def select_representative_titles(
    embeddings: np.ndarray,
    cluster_indices: List[int],
    titles: List[str],
    max_titles: int = cfg.MAX_REPRESENTATIVE_TITLES
) -> List[str]:
    """
    Selects representative titles closest to the cluster semantic centroid in embedding space.
    """
    if not cluster_indices or len(cluster_indices) == 0:
        return []

    cluster_embeddings = embeddings[cluster_indices]
    centroid = np.mean(cluster_embeddings, axis=0, keepdims=True)

    # Compute Euclidean distance to centroid
    dists = np.linalg.norm(cluster_embeddings - centroid, axis=1)
    
    # Sort indices by distance
    sorted_order = np.argsort(dists)

    selected = []
    for idx in sorted_order[:max_titles]:
        real_idx = cluster_indices[idx]
        if real_idx < len(titles):
            selected.append(titles[real_idx])

    return selected


def calculate_cluster_confidence(
    semantic_quality: float,
    video_count: int,
    unique_channels: int,
    dominant_channel_share: float,
    outlier_count: int,
    label_quality_score: float = 100.0
) -> float:
    """
    Calculates ClusterConfidence (0-100) based on cohesion, size, channel diversity, label quality, and evidence.
    """
    score = 0.0

    # 1. Semantic quality (max 25 pts)
    quality_clamped = max(0.0, min(1.0, semantic_quality))
    score += quality_clamped * 25.0

    # 2. Cluster Size (max 20 pts)
    if video_count >= 10:
        score += 20.0
    elif video_count >= 5:
        score += 15.0
    elif video_count >= 3:
        score += 10.0
    else:
        score += 5.0

    # 3. Diversity / Concentration (max 25 pts)
    if dominant_channel_share <= 0.30 and unique_channels >= 3:
        score += 25.0
    elif dominant_channel_share <= 0.50:
        score += 18.0
    elif dominant_channel_share <= 0.75:
        score += 10.0
    else:
        score += 3.0  # Dominant single channel penalty

    # 4. Label quality (max 15 pts)
    l_score = max(0.0, min(100.0, label_quality_score))
    score += (l_score / 100.0) * 15.0

    # 5. Outlier evidence (max 15 pts)
    if outlier_count >= 3:
        score += 15.0
    elif outlier_count >= 1:
        score += 10.0
    else:
        score += 5.0

    return round(min(100.0, score), 2)



def calculate_cluster_signal_score(
    semantic_quality: float,
    outlier_count: int,
    video_count: int,
    dominant_channel_share: float,
    confidence: float
) -> float:
    """
    Calculates exploratory ClusterSignalScore for ranking clusters.
    Combines semantic quality, outlier density, channel diversity, and confidence.
    """
    # 1. Quality (30%)
    q_score = max(0.0, min(1.0, semantic_quality)) * 100.0 * cfg.WEIGHT_SEMANTIC_QUALITY

    # 2. Outlier Density (30%)
    density = (outlier_count / max(1, video_count))
    d_score = min(1.0, density * 2.0) * 100.0 * cfg.WEIGHT_OUTLIER_DENSITY

    # 3. Channel Diversity (20%)
    diversity_factor = 1.0 - min(1.0, dominant_channel_share)
    div_score = diversity_factor * 100.0 * cfg.WEIGHT_CHANNEL_DIVERSITY

    # 4. Confidence (20%)
    conf_score = (confidence / 100.0) * 100.0 * cfg.WEIGHT_CONFIDENCE

    total_score = q_score + d_score + div_score + conf_score
    return round(total_score, 4)
