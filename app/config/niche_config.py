"""
Configuration settings for Niche Miner (Sprint 5).
"""
from typing import List
from pydantic import BaseModel


class NicheMinerConfig(BaseModel):
    # Clustering Parameters
    MIN_K: int = 2
    MAX_K: int = 15
    DEFAULT_MIN_CLUSTER_SIZE: int = 3
    RANDOM_STATE: int = 42

    # Diversity Thresholds
    LOW_DIVERSITY_SHARE: float = 0.60    # >60% from single channel = LOW_DIVERSITY
    HIGH_DIVERSITY_SHARE: float = 0.30   # <=30% from single channel = HIGH_DIVERSITY
    MIN_CHANNELS_HIGH_DIVERSITY: int = 3

    # Ranking Weights for ClusterSignalScore
    WEIGHT_SEMANTIC_QUALITY: float = 0.30
    WEIGHT_OUTLIER_DENSITY: float = 0.30
    WEIGHT_CHANNEL_DIVERSITY: float = 0.20
    WEIGHT_CONFIDENCE: float = 0.20

    # Labeling settings
    MAX_REPRESENTATIVE_TITLES: int = 5


niche_config = NicheMinerConfig()
