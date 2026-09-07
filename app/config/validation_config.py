"""
Configurable thresholds and parameters for Sprint 10 Adversarial Opportunity Validator.
"""

from pydantic import BaseModel, Field


class ValidationConfig(BaseModel):
    # Thresholds for validation gate
    pass_validation_score_threshold: float = Field(default=75.0, ge=0.0, le=100.0)
    pass_confidence_threshold: float = Field(default=60.0, ge=0.0, le=100.0)
    pass_max_false_positive_risk: float = Field(default=35.0, ge=0.0, le=100.0)

    watch_validation_score_threshold: float = Field(default=50.0, ge=0.0, le=100.0)
    watch_max_false_positive_risk: float = Field(default=60.0, ge=0.0, le=100.0)

    # Sensitivity thresholds
    one_video_dominance_share_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    channel_dominance_share_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    top_3_channel_share_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    high_hhi_threshold: float = Field(default=3500.0, ge=0.0, le=10000.0)

    # Sample adequacy bands
    sample_adequacy_min_videos: int = Field(default=5, ge=1)
    sample_adequacy_optimal_videos: int = Field(default=15, ge=1)
    sample_adequacy_min_channels: int = Field(default=3, ge=1)

    # Weights for ValidationScore
    weight_sample_adequacy: float = Field(default=0.10, ge=0.0, le=1.0)
    weight_channel_diversity: float = Field(default=0.15, ge=0.0, le=1.0)
    weight_outlier_robustness: float = Field(default=0.15, ge=0.0, le=1.0)
    weight_temporal_robustness: float = Field(default=0.10, ge=0.0, le=1.0)
    weight_expected_views_stability: float = Field(default=0.10, ge=0.0, le=1.0)
    weight_economic_validation: float = Field(default=0.10, ge=0.0, le=1.0)
    weight_production_validation: float = Field(default=0.10, ge=0.0, le=1.0)
    weight_depth_validation: float = Field(default=0.05, ge=0.0, le=1.0)
    weight_semantic_coherence: float = Field(default=0.05, ge=0.0, le=1.0)
    weight_cross_signal_consistency: float = Field(default=0.10, ge=0.0, le=1.0)


validation_config = ValidationConfig()
