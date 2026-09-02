"""
Data models for Sprint 5 Niche Mining and Semantic Clustering.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ClusterHierarchy(BaseModel):
    niche: str = ""
    subniche: str = ""
    microniche: str = ""
    summary: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)


class NicheCluster(BaseModel):
    cluster_id: int
    video_ids: List[str] = Field(default_factory=list)
    video_count: int = 0
    unique_channels: int = 0
    dominant_channel_share: float = 0.0
    channel_diversity: str = "MEDIUM_DIVERSITY"  # LOW_DIVERSITY, MEDIUM_DIVERSITY, HIGH_DIVERSITY
    
    representative_titles: List[str] = Field(default_factory=list)

    # Label hierarchy
    niche: str = ""
    subniche: str = ""
    microniche: str = ""
    summary: str = ""
    label_confidence: float = 0.0
    label_quality_score: float = 100.0
    label_warnings: List[str] = Field(default_factory=list)

    # Outlier crossover evidence
    outlier_count: int = 0
    strong_outlier_count: int = 0
    major_outlier_count: int = 0
    median_outlier_ratio: Optional[float] = None
    max_outlier_ratio: Optional[float] = None

    # Scores and confidence
    semantic_quality: float = 0.0  # Silhouette or intra-cluster similarity
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    cluster_signal_score: float = 0.0

    warnings: List[str] = Field(default_factory=list)



class NicheMiningResult(BaseModel):
    run_id: str
    algorithm: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    semantic_provider: str
    
    videos_considered: int = 0
    videos_embedded: int = 0
    videos_skipped: int = 0

    total_clusters: int = 0
    unassigned_count: int = 0
    quality_metric_name: str = "silhouette_score"
    quality_metric_value: float = 0.0

    clusters: List[NicheCluster] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    created_at: str = ""
