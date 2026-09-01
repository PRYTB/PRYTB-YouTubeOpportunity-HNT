"""
Data models for Outlier Engine results in PRYTB Sprint 4.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class VideoOutlierResult(BaseModel):
    video_id: str
    channel_id: str
    video_title: Optional[str] = None
    channel_title: Optional[str] = None

    video_views: Optional[int] = None
    channel_median_views: Optional[float] = None
    channel_mean_views: Optional[float] = None
    channel_median_views_per_day: Optional[float] = None
    baseline_video_count: int = 0
    baseline_confidence: str = "VERY_LOW"  # VERY_LOW, LOW, MEDIUM, HIGH

    outlier_ratio: Optional[float] = None
    age_normalized_outlier_ratio: Optional[float] = None

    latest_velocity: Optional[float] = None
    velocity_ratio: Optional[float] = None
    latest_acceleration: Optional[float] = None

    subscriber_count: Optional[int] = None
    views_to_subscribers_ratio: Optional[float] = None

    is_small_channel: Optional[bool] = None
    is_strong_outlier: bool = False
    is_major_outlier: bool = False
    is_extreme_outlier: bool = False
    small_channel_outlier: bool = False

    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    outlier_rank_score: float = 0.0
    warnings: List[str] = Field(default_factory=list)
