from typing import List, Optional
from pydantic import BaseModel, Field

class MetricInterval(BaseModel):
    previous_at: str
    current_at: str
    elapsed_seconds: float
    elapsed_hours: float
    elapsed_days: float
    view_delta: Optional[int] = None
    like_delta: Optional[int] = None
    comment_delta: Optional[int] = None
    subscriber_delta: Optional[int] = None
    video_count_delta: Optional[int] = None
    views_per_day: Optional[float] = None
    view_velocity: Optional[float] = None

class VideoHistoricalMetrics(BaseModel):
    video_id: str
    snapshot_count: int
    latest_views: Optional[int] = None
    video_age_days: Optional[float] = None
    lifetime_views_per_day: Optional[float] = None
    latest_velocity: Optional[float] = None
    latest_acceleration: Optional[float] = None
    intervals: List[MetricInterval] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class ChannelHistoricalMetrics(BaseModel):
    channel_id: str
    snapshot_count: int
    latest_subscribers: Optional[int] = None
    latest_views: Optional[int] = None
    latest_video_count: Optional[int] = None
    intervals: List[MetricInterval] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
