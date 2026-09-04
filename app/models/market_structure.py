"""Normalized models for Sprint 7 competition, depth, and evergreen analysis."""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class EvergreenClass(str, Enum):
    TREND = "TREND"
    SEMI_EVERGREEN = "SEMI_EVERGREEN"
    EVERGREEN = "EVERGREEN"
    UNKNOWN = "UNKNOWN"


class ContentDepthBand(str, Enum):
    BELOW_20 = "BELOW_20"
    IDEAS_20_PLUS = "20_PLUS"
    IDEAS_50_PLUS = "50_PLUS"
    IDEAS_100_PLUS = "100_PLUS"
    UNDETERMINED = "UNDETERMINED"
    UNKNOWN = "UNKNOWN"


class EntryAccessibility(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class MarketStructureClass(str, Enum):
    VIRAL_SATURATED = "VIRAL_SATURATED"
    CONTENT_CONSTRAINED = "CONTENT_CONSTRAINED"
    SUSTAINABLE_ACCESSIBLE = "SUSTAINABLE_ACCESSIBLE"
    UNCERTAIN = "UNCERTAIN"


class ContentAtom(BaseModel):
    atom: str = Field(min_length=1)
    video_count: int = Field(ge=1)


class ClusterMarketStructure(BaseModel):
    cluster_id: int = Field(ge=0)
    niche: str = ""
    subniche: str = ""
    microniche: str = ""
    summary: str = ""
    top_5_rank: Optional[int] = Field(default=None, ge=1, le=5)
    market_structure_score: float = Field(default=0.0, ge=0.0, le=100.0)
    video_count: int = Field(default=0, ge=0)
    channel_count: int = Field(default=0, ge=0)
    channels_with_subscribers: int = Field(default=0, ge=0)
    average_subscribers: Optional[float] = Field(default=None, ge=0.0)
    median_channel_age_days: Optional[float] = Field(default=None, ge=0.0)
    new_entrant_channels: int = Field(default=0, ge=0)
    new_entrant_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    dominant_channel_share: float = Field(default=0.0, ge=0.0, le=100.0)
    channel_hhi: float = Field(default=0.0, ge=0.0, le=100.0)

    outlier_results_available: int = Field(default=0, ge=0)
    strong_outlier_count: int = Field(default=0, ge=0)
    major_outlier_count: int = Field(default=0, ge=0)
    extreme_outlier_count: int = Field(default=0, ge=0)
    small_channel_eligible_videos: int = Field(default=0, ge=0)
    small_channel_successes: int = Field(default=0, ge=0)
    small_channel_success_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    median_outlier_ratio: Optional[float] = Field(default=None, ge=0.0)
    max_outlier_ratio: Optional[float] = Field(default=None, ge=0.0)
    average_outlier_rank_score: Optional[float] = Field(default=None, ge=0.0)

    competition_score: float = Field(default=0.0, ge=0.0, le=100.0)
    accessibility_score: float = Field(default=0.0, ge=0.0, le=100.0)
    accessibility_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    accessibility: EntryAccessibility = EntryAccessibility.UNKNOWN

    distinct_title_count: int = Field(default=0, ge=0)
    title_pattern_count: int = Field(default=0, ge=0)
    topic_atom_count: int = Field(default=0, ge=0)
    near_duplicate_count: int = Field(default=0, ge=0)
    semantic_diversity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    content_atoms: List[ContentAtom] = Field(default_factory=list)
    short_video_count: int = Field(default=0, ge=0)
    long_form_video_count: int = Field(default=0, ge=0)
    unknown_format_count: int = Field(default=0, ge=0)
    format_facet_count: int = Field(default=0, ge=0, le=2)
    observed_content_span_days: Optional[float] = Field(default=None, ge=0.0)
    estimated_capacity_low: Optional[int] = Field(default=None, ge=0)
    estimated_capacity_high: Optional[int] = Field(default=None, ge=0)
    estimated_distinct_ideas: Optional[int] = Field(default=None, ge=0)
    content_depth_score: float = Field(default=0.0, ge=0.0, le=100.0)
    depth_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    content_depth_band: ContentDepthBand = ContentDepthBand.UNKNOWN

    recent_video_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    mature_video_rate: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    trend_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    is_trend: Optional[bool] = None
    evergreen_score: float = Field(default=0.0, ge=0.0, le=100.0)
    evergreen_class: EvergreenClass = EvergreenClass.UNKNOWN

    median_views: Optional[float] = Field(default=None, ge=0.0)
    market_structure_class: MarketStructureClass = MarketStructureClass.UNCERTAIN
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    observed_fields: List[str] = Field(default_factory=list)
    inferred_fields: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts(self):
        if self.channels_with_subscribers > self.channel_count:
            raise ValueError("Known subscriber channels cannot exceed channel count.")
        if self.new_entrant_channels > self.channel_count:
            raise ValueError("New entrant channels cannot exceed channel count.")
        if self.small_channel_successes > self.small_channel_eligible_videos:
            raise ValueError("Small-channel successes cannot exceed eligible videos.")
        if self.outlier_results_available > self.video_count:
            raise ValueError("Outlier results cannot exceed video count.")
        if any(count > self.outlier_results_available for count in (
            self.strong_outlier_count,
            self.major_outlier_count,
            self.extreme_outlier_count,
            self.small_channel_eligible_videos,
        )):
            raise ValueError("Outlier classifications cannot exceed available results.")
        if self.distinct_title_count > self.video_count:
            raise ValueError("Distinct title count cannot exceed video count.")
        if self.title_pattern_count > self.distinct_title_count:
            raise ValueError("Title pattern count cannot exceed distinct title count.")
        if self.topic_atom_count > self.title_pattern_count:
            raise ValueError("Topic atom count cannot exceed title pattern count.")
        if self.near_duplicate_count + self.topic_atom_count > self.video_count:
            raise ValueError("Title signatures and near-duplicates cannot exceed video count.")
        if (
            self.estimated_capacity_low is not None
            and self.estimated_capacity_high is not None
            and self.estimated_capacity_low > self.estimated_capacity_high
        ):
            raise ValueError("Content capacity bounds must be ordered.")
        if self.short_video_count + self.long_form_video_count + self.unknown_format_count > self.video_count:
            raise ValueError("Content format counts cannot exceed video count.")
        return self


class Sprint7QualityMetrics(BaseModel):
    total_videos: int = Field(default=0, ge=0)
    total_clusters: int = Field(default=0, ge=0)
    subscriber_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    views_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    publication_date_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    duration_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    outlier_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    clusters_without_small_channel_sample: int = Field(default=0, ge=0)
    clusters_without_microniche: int = Field(default=0, ge=0)
    clusters_without_content_atoms: int = Field(default=0, ge=0)
    clusters_without_temporal_evidence: int = Field(default=0, ge=0)


class Sprint7AnalysisResult(BaseModel):
    run_id: str
    source_cluster_run_id: Optional[str] = None
    analyzed_at: str
    config: Dict[str, Any] = Field(default_factory=dict)
    clusters: List[ClusterMarketStructure] = Field(default_factory=list)
    quality: Sprint7QualityMetrics
