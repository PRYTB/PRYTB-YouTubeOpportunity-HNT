"""
Sprint 6: Geography and Revenue Models

Normalized models for video geography estimates, revenue signals,
market tiers, and benchmark records.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LanguageCode(str, Enum):
    """Supported language codes for primary content language."""
    EN = "en"
    ES = "es"
    PT = "pt"
    FR = "fr"
    DE = "de"
    OTHER = "other"
    UNKNOWN = "unknown"


class GeoSource(str, Enum):
    """Source classification for geographic/language signals."""
    OBSERVED = "OBSERVED"
    CHANNEL_METADATA = "CHANNEL_METADATA"
    TITLE_DESCRIPTION_INFERENCE = "TITLE_DESCRIPTION_INFERENCE"
    LANGUAGE_INFERENCE = "LANGUAGE_INFERENCE"
    UNKNOWN = "UNKNOWN"


class ContentType(str, Enum):
    """Video content type classification based on duration."""
    SHORT = "SHORT"
    LONG_FORM = "LONG_FORM"
    UNKNOWN = "UNKNOWN"


class MarketTier(str, Enum):
    """Market tier representing relative advertiser-market attractiveness.

    NOT guaranteed RPM. Configuration-driven, editable without code changes.
    """
    TIER_A = "Tier A"
    TIER_B = "Tier B"
    TIER_C = "Tier C"
    UNKNOWN = "Unknown"


class BenchmarkSourceType(str, Enum):
    """Source type for revenue benchmarks."""
    OBSERVED_BENCHMARK = "observed_benchmark"
    EXTERNAL_BENCHMARK = "external_benchmark"
    MANUAL_BENCHMARK = "manual_benchmark"
    UNKNOWN = "unknown"


class LanguageDetectionResult(BaseModel):
    """Result of deterministic language detection."""
    language_code: LanguageCode = LanguageCode.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    source: GeoSource = GeoSource.UNKNOWN
    details: Dict[str, Any] = Field(default_factory=dict)


class VideoGeographyEstimate(BaseModel):
    """Normalized geographic estimate for a single video.

    Strictly separates OBSERVED vs INFERRED data.
    Never labels inferred country as observed.
    """
    video_id: str
    primary_language: LanguageCode = LanguageCode.UNKNOWN
    language_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    language_source: GeoSource = GeoSource.UNKNOWN

    # Channel origin country (observed from YouTube API if available)
    channel_origin_country: Optional[str] = None

    # Estimated audience market (inferred, separate from channel origin)
    country_signals: List[str] = Field(default_factory=list)
    estimated_audience_market: Optional[str] = None
    primary_country: Optional[str] = None
    primary_country_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    region_group: Optional[str] = None

    geo_source: GeoSource = GeoSource.UNKNOWN
    observed_fields: List[str] = Field(default_factory=list)
    inferred_fields: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    warnings: List[str] = Field(default_factory=list)


class RevenueBenchmark(BaseModel):
    """Revenue benchmark record with full provenance.

    Architecture allows: observed, external, manual, unknown.
    If no benchmark exists, revenue estimate = unavailable.
    Never fabricate values.
    """
    source_type: BenchmarkSourceType
    source_name: str
    market: str  # country code or region group
    content_type: ContentType
    value_low: float = Field(ge=0.0)
    value_mid: float = Field(ge=0.0)
    value_high: float = Field(ge=0.0)
    currency: str = "USD"
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    notes: str = ""


class RevenueEstimate(BaseModel):
    """Normalized revenue signal estimate for a single video.

    These are INTERNAL COMPARATIVE SIGNALS unless backed by a documented source.
    Do not call them actual revenue.
    """
    video_id: str
    content_type: ContentType = ContentType.UNKNOWN
    estimated_market_tier: MarketTier = MarketTier.UNKNOWN
    revenue_signal_low: Optional[float] = None
    revenue_signal_mid: Optional[float] = None
    revenue_signal_high: Optional[float] = None
    currency: str = "USD"
    method: str = "comparative_tier_based"
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    # Benchmark linkage if available
    benchmark_source_type: Optional[BenchmarkSourceType] = None
    benchmark_source_name: Optional[str] = None
    benchmark_confidence: Optional[float] = None


class AudienceEconomicValue(BaseModel):
    """Normalized comparative economic value indicator (0-100).

    This is NOT Opportunity Score.
    Based on market tier, language, content type, benchmark availability, confidence.
    Avoid false precision. Round reasonably.
    """
    video_id: str
    value: float = Field(default=0.0, ge=0.0, le=100.0)
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    method: str = "tier_language_format_weighted"
    inputs: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class ClusterRevenueAggregate(BaseModel):
    """Sprint 6 cluster-level revenue and geography aggregation."""
    cluster_id: int
    video_count: int = 0

    # Language distribution
    language_distribution: Dict[str, int] = Field(default_factory=dict)
    dominant_language: LanguageCode = LanguageCode.UNKNOWN

    # Market distribution
    estimated_market_distribution: Dict[str, int] = Field(default_factory=dict)
    market_tier_distribution: Dict[str, int] = Field(default_factory=dict)

    # Content format
    long_form_count: int = 0
    short_count: int = 0
    unknown_format_count: int = 0

    # Benchmark coverage
    benchmark_coverage: float = Field(default=0.0, ge=0.0, le=100.0)

    # Economic value
    audience_economic_value: float = Field(default=0.0, ge=0.0, le=100.0)
    revenue_confidence: float = Field(default=0.0, ge=0.0, le=100.0)

    warnings: List[str] = Field(default_factory=list)


class VideoRevenueAnalysis(BaseModel):
    """Complete Sprint 6 analysis for one video."""
    video_id: str
    title: str = ""
    geography: VideoGeographyEstimate
    revenue: RevenueEstimate
    economic_value: AudienceEconomicValue


class DataQualityMetrics(BaseModel):
    """Explicit data quality metrics for Sprint 6 reporting."""
    language_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    geo_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    content_type_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    benchmark_missing_rate: float = Field(default=0.0, ge=0.0, le=100.0)

    total_videos: int = 0
    total_clusters: int = 0


class Sprint6AnalysisResult(BaseModel):
    """Complete in-memory Sprint 6 analysis result."""
    run_id: str
    source_cluster_run_id: Optional[str] = None
    videos: List[VideoRevenueAnalysis] = Field(default_factory=list)
    clusters: List[ClusterRevenueAggregate] = Field(default_factory=list)
    quality: DataQualityMetrics