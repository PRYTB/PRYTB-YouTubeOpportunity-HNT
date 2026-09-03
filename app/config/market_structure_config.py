"""Editable configuration for Sprint 7 market-structure analysis."""
from pydantic import BaseModel, Field, model_validator

from config.outlier_config import OUTLIER_STRONG_MIN, SMALL_CHANNEL_SUBSCRIBERS_MAX


class MarketStructureConfig(BaseModel):
    small_channel_subscribers_max: int = Field(default=SMALL_CHANNEL_SUBSCRIBERS_MAX, ge=0)
    small_channel_success_ratio: float = Field(default=OUTLIER_STRONG_MIN, gt=0.0)
    minimum_channel_baseline_videos: int = Field(default=2, ge=1)
    new_channel_max_age_days: int = Field(default=730, ge=0)
    recent_video_max_age_days: int = Field(default=180, ge=0)
    mature_video_min_age_days: int = Field(default=730, ge=0)
    minimum_cluster_sample: int = Field(default=5, ge=1)

    depth_20_threshold: int = Field(default=5, ge=1)
    depth_50_threshold: int = Field(default=10, ge=1)
    depth_100_threshold: int = Field(default=20, ge=1)
    idea_multiplier: int = Field(default=5, ge=1)

    competition_weight_channel_count: float = Field(default=0.30, ge=0.0)
    competition_weight_concentration: float = Field(default=0.35, ge=0.0)
    competition_weight_channel_size: float = Field(default=0.20, ge=0.0)
    competition_weight_maturity: float = Field(default=0.15, ge=0.0)
    accessibility_weight_small_success: float = Field(default=0.50, ge=0.0)
    accessibility_weight_new_entrants: float = Field(default=0.25, ge=0.0)
    accessibility_weight_low_concentration: float = Field(default=0.25, ge=0.0)

    high_accessibility_min: float = Field(default=65.0, ge=0.0, le=100.0)
    medium_accessibility_min: float = Field(default=40.0, ge=0.0, le=100.0)
    trend_recent_rate_min: float = Field(default=70.0, ge=0.0, le=100.0)
    evergreen_mature_rate_min: float = Field(default=35.0, ge=0.0, le=100.0)
    evergreen_span_days_min: int = Field(default=730, ge=1)
    saturated_competition_min: float = Field(default=65.0, ge=0.0, le=100.0)
    viral_median_views_min: int = Field(default=100000, ge=0)
    sustainable_depth_min: float = Field(default=50.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_configuration(self):
        if not self.depth_20_threshold <= self.depth_50_threshold <= self.depth_100_threshold:
            raise ValueError("Content-depth thresholds must be ordered.")
        if self.medium_accessibility_min > self.high_accessibility_min:
            raise ValueError("Accessibility thresholds must be ordered.")
        competition_sum = (
            self.competition_weight_channel_count
            + self.competition_weight_concentration
            + self.competition_weight_channel_size
            + self.competition_weight_maturity
        )
        accessibility_sum = (
            self.accessibility_weight_small_success
            + self.accessibility_weight_new_entrants
            + self.accessibility_weight_low_concentration
        )
        if abs(competition_sum - 1.0) > 1e-9 or abs(accessibility_sum - 1.0) > 1e-9:
            raise ValueError("Sprint 7 score weights must sum to 1.0.")
        return self


market_structure_config = MarketStructureConfig()
