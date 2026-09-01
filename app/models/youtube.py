from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class YouTubeVideo(BaseModel):
    video_id: str
    channel_id: str
    title: str
    description: Optional[str] = None
    published_at: Optional[str] = None
    category_id: Optional[str] = None

    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None

    duration_iso: Optional[str] = None
    duration_seconds: Optional[int] = None

    definition: Optional[str] = None
    caption: Optional[str] = None
    licensed_content: Optional[bool] = None

    default_language: Optional[str] = None
    default_audio_language: Optional[str] = None


class YouTubeChannel(BaseModel):
    channel_id: str
    channel_title: str
    channel_description: Optional[str] = None
    published_at: Optional[str] = None
    country: Optional[str] = None
    subscriber_count: Optional[int] = None
    hidden_subscriber_count: bool = False
    video_count: Optional[int] = None
    view_count: Optional[int] = None


class CollectionStats(BaseModel):
    requested_videos: int = 0
    search_results: int = 0
    videos_resolved: int = 0
    videos_missing: int = 0
    unique_channels: int = 0
    channels_resolved: int = 0
    search_pages: int = 0
    video_batches: int = 0
    channel_batches: int = 0
    api_requests: int = 0
    estimated_quota_units: int = 0
    elapsed_seconds: float = 0.0


class CollectionResult(BaseModel):
    query: str
    collected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    videos: List[YouTubeVideo] = Field(default_factory=list)
    channels: List[YouTubeChannel] = Field(default_factory=list)
    stats: CollectionStats = Field(default_factory=CollectionStats)
    warnings: List[str] = Field(default_factory=list)
