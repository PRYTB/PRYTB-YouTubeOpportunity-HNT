"""
Unit tests for Sprint 10 Adversarial Opportunity Validator.
"""

import pytest
from app.analytics.opportunity_validator import OpportunityValidator
from app.config.validation_config import ValidationConfig
from app.models.market_structure import ClusterMarketStructure, ContentDepthBand, EvergreenClass
from app.models.outliers import VideoOutlierResult
from app.models.production_risk import ClusterProductionRisk, RiskLevel
from app.models.profitability import (
    ClusterProfitabilityAnalysis,
    ExpectedViewsRange,
    ProfitabilityClassification,
)
from app.models.validation import ValidationStatus


def _create_mock_prof_analysis(cluster_id: int = 1, prof_score: float = 80.0) -> ClusterProfitabilityAnalysis:
    return ClusterProfitabilityAnalysis(
        run_id="sprint9_test",
        cluster_id=cluster_id,
        niche="test",
        subniche="test",
        microniche="test_niche",
        video_count=5,
        expected_views_range=ExpectedViewsRange(low=1000, base=5000, high=10000),
        demand_score=70.0,
        outlier_score=60.0,
        revenue_potential_score=75.0,
        competition_component=50.0,
        geography_score=60.0,
        evergreen_score=60.0,
        production_score=60.0,
        base_score=70.0,
        risk_penalty=5.0,
        profitability_score=prof_score,
        classification=ProfitabilityClassification.STRONG,
        component_coverage=0.8,
        known_weight=0.8,
        missing_weight=0.2,
        confidence=75.0,
        dataset_hash="dataset_hash_test",
        assignments_hash="assignments_hash_test",
    )


def test_one_video_dominance_synthetic_test_a():
    """Synthetic Test A: False viral opportunity (one video huge views, one dominant channel)."""
    validator = OpportunityValidator()
    prof = _create_mock_prof_analysis(cluster_id=1, prof_score=85.0)

    # 1 video with 100k views, 4 videos with 100 views, all from channel_1
    videos = [
        {"video_id": "v1", "channel_id": "ch1", "view_count": 100000},
        {"video_id": "v2", "channel_id": "ch1", "view_count": 100},
        {"video_id": "v3", "channel_id": "ch1", "view_count": 100},
        {"video_id": "v4", "channel_id": "ch1", "view_count": 100},
        {"video_id": "v5", "channel_id": "ch1", "view_count": 100},
    ]

    res = validator.validate_cluster(
        run_id="val_test",
        profitability_analysis=prof,
        cluster_videos=videos,
        source_profitability_run_id="sprint9_test",
        source_cluster_run_id="c_run",
        source_revenue_run_id="r_run",
        source_market_run_id="m_run",
        source_production_run_id="p_run",
        dataset_hash="h1",
        assignments_hash="h2",
    )

    assert res.top_video_view_share > 0.95
    assert res.dominant_channel_share == 1.0
    assert "ONE_VIDEO_DEPENDENT" in res.warnings
    assert "SINGLE_CHANNEL_DEPENDENT" in res.warnings
    assert res.fragility_score > 60.0
    assert res.false_positive_risk > 50.0


def test_robust_moderate_opportunity_synthetic_test_b():
    """Synthetic Test B: Robust moderate opportunity (multiple channels, stable history)."""
    validator = OpportunityValidator()
    prof = _create_mock_prof_analysis(cluster_id=2, prof_score=75.0)

    videos = [
        {"video_id": "v1", "channel_id": "ch1", "view_count": 5000},
        {"video_id": "v2", "channel_id": "ch2", "view_count": 4800},
        {"video_id": "v3", "channel_id": "ch3", "view_count": 5200},
        {"video_id": "v4", "channel_id": "ch4", "view_count": 5100},
        {"video_id": "v5", "channel_id": "ch5", "view_count": 4900},
    ]
    outliers = [
        VideoOutlierResult(video_id="v1", channel_id="ch1", outlier_rank_score=60.0),
        VideoOutlierResult(video_id="v3", channel_id="ch3", outlier_rank_score=70.0),
    ]
    ms = ClusterMarketStructure(
        cluster_id=2,
        dominant_channel_share=20.0,
        channel_hhi=0.2,
        evergreen_class=EvergreenClass.EVERGREEN,
    )

    res = validator.validate_cluster(
        run_id="val_test",
        profitability_analysis=prof,
        cluster_videos=videos,
        market_structure=ms,
        outlier_results=outliers,
        source_profitability_run_id="sprint9_test",
        source_cluster_run_id="c_run",
        source_revenue_run_id="r_run",
        source_market_run_id="m_run",
        source_production_run_id="p_run",
        dataset_hash="h1",
        assignments_hash="h2",
    )

    assert res.top_video_view_share < 0.25
    assert res.dominant_channel_share == 0.2
    assert res.fragility_score < 40.0
    assert res.validation_score > 50.0


def test_missing_evidence_synthetic_test_c():
    """Synthetic Test C: Missing evidence must NOT become PASS with high confidence."""
    validator = OpportunityValidator()
    prof = _create_mock_prof_analysis(cluster_id=3, prof_score=90.0)
    prof.confidence = 30.0

    videos = [{"video_id": "v1", "channel_id": "ch1", "view_count": 5000}]

    res = validator.validate_cluster(
        run_id="val_test",
        profitability_analysis=prof,
        cluster_videos=videos,
        source_profitability_run_id="sprint9_test",
        source_cluster_run_id="c_run",
        source_revenue_run_id="r_run",
        source_market_run_id="m_run",
        source_production_run_id="p_run",
        dataset_hash="h1",
        assignments_hash="h2",
    )

    assert res.validation_status != ValidationStatus.PASS
    assert res.validation_confidence < 50.0


def test_trend_spike_synthetic_test_d():
    """Synthetic Test D: Recent trend spike reduces temporal validation."""
    validator = OpportunityValidator()
    prof = _create_mock_prof_analysis(cluster_id=4, prof_score=75.0)

    ms = ClusterMarketStructure(
        cluster_id=4,
        evergreen_class=EvergreenClass.TREND,
        is_trend=True,
    )
    videos = [{"video_id": f"v{i}", "channel_id": f"ch{i}", "view_count": 5000} for i in range(5)]

    res = validator.validate_cluster(
        run_id="val_test",
        profitability_analysis=prof,
        cluster_videos=videos,
        market_structure=ms,
        source_profitability_run_id="sprint9_test",
        source_cluster_run_id="c_run",
        source_revenue_run_id="r_run",
        source_market_run_id="m_run",
        source_production_run_id="p_run",
        dataset_hash="h1",
        assignments_hash="h2",
    )

    assert res.temporal_validation == 30.0
    assert "RECENT_TREND_DEPENDENT" in res.warnings
