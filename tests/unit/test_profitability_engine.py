"""
Unit tests for Sprint 9 Profitability Engine.
"""

import pytest
from app.analytics.profitability_engine import ProfitabilityEngine
from app.config.profitability_config import ProfitabilityConfig
from app.models.geography import ContentType
from app.models.market_structure import ClusterMarketStructure, ContentDepthBand
from app.models.production_risk import ClusterProductionRisk, RiskLevel
from app.models.profitability import (
    EvidenceType,
    ProductionCostMonetary,
    ProfitabilityClassification,
    RPMRange,
)


def test_weight_validation():
    # Valid weights
    config = ProfitabilityConfig()
    assert abs(sum(config.get_weights_dict().values()) - 1.0) < 1e-6

    # Invalid weights sum
    with pytest.raises(ValueError, match="sum to 1.0"):
        ProfitabilityConfig(weight_demand=0.5)


def test_robust_expected_views_range():
    engine = ProfitabilityEngine()
    videos = [
        {"view_count": 1000, "duration_seconds": 600},
        {"view_count": 3000, "duration_seconds": 650},
        {"view_count": 5000, "duration_seconds": 700},
        {"view_count": 10000, "duration_seconds": 800},
        {"view_count": 1000000, "duration_seconds": 900}, # Extreme viral outlier
    ]
    res = engine.analyze_cluster(
        run_id="test_run",
        cluster_id=1,
        niche="test",
        subniche="test",
        microniche="test",
        cluster_videos=videos,
        dataset_hash="hash1",
        assignments_hash="hash2",
    )

    ev = res.expected_views_range
    assert ev.low <= ev.base <= ev.high
    # Robust percentiles should ignore extreme viral outlier 1,000,000!
    assert ev.base == 5000.0
    assert ev.low == 3000.0
    assert ev.high == 10000.0


def test_short_vs_long_form_separation():
    engine = ProfitabilityEngine()
    videos = [
        {"view_count": 5000, "duration_seconds": 60},  # Short
        {"view_count": 5000, "duration_seconds": 120}, # Short
        {"view_count": 5000, "duration_seconds": 600}, # Long
    ]
    res = engine.analyze_cluster(
        run_id="test_run",
        cluster_id=1,
        niche="test",
        subniche="test",
        microniche="test",
        cluster_videos=videos,
        dataset_hash="hash1",
        assignments_hash="hash2",
    )

    assert res.short_video_count == 2
    assert res.long_form_video_count == 1
    assert res.unknown_format_count == 0
    assert res.short_potential_score is not None


def test_missing_component_handling_undetermined_depth():
    engine = ProfitabilityEngine()
    ms = ClusterMarketStructure(
        cluster_id=1,
        content_depth_band=ContentDepthBand.UNDETERMINED,
        content_depth_score=100.0, # High score should be IGNORED because band is UNDETERMINED
    )
    res = engine.analyze_cluster(
        run_id="test_run",
        cluster_id=1,
        niche="test",
        subniche="test",
        microniche="test",
        cluster_videos=[{"view_count": 5000, "duration_seconds": 600}],
        market_structure=ms,
        dataset_hash="hash1",
        assignments_hash="hash2",
    )

    assert res.content_depth_score is None
    assert "Content depth is UNDETERMINED / UNKNOWN" in res.missing_evidence
    assert res.component_contributions["content_depth"] == 0.0


def test_rpm_unavailable_monetary_policy():
    engine = ProfitabilityEngine()
    res = engine.analyze_cluster(
        run_id="test_run",
        cluster_id=1,
        niche="test",
        subniche="test",
        microniche="test",
        cluster_videos=[{"view_count": 10000, "duration_seconds": 600}],
        dataset_hash="hash1",
        assignments_hash="hash2",
    )

    assert not res.rpm_range.available
    assert not res.revenue_scenarios.available
    assert not res.profit_scenarios.available
    # Score must still calculate fine!
    assert res.profitability_score > 0.0


def test_monetary_scenarios_when_rpm_and_cost_available():
    engine = ProfitabilityEngine()
    rpm = RPMRange(available=True, low=2.0, mid=5.0, high=10.0, currency="USD", source=EvidenceType.EXTERNAL_BENCHMARK)
    cost = ProductionCostMonetary(available=True, low=20.0, base=50.0, high=100.0, currency="USD", evidence_type=EvidenceType.MANUAL_ASSUMPTION)

    videos = [{"view_count": 20000, "duration_seconds": 600}] # base views = 20,000

    res = engine.analyze_cluster(
        run_id="test_run",
        cluster_id=1,
        niche="test",
        subniche="test",
        microniche="test",
        cluster_videos=videos,
        explicit_rpm=rpm,
        explicit_cost_money=cost,
        dataset_hash="hash1",
        assignments_hash="hash2",
    )

    assert res.revenue_scenarios.available
    # Base revenue = 20,000 * 5.0 / 1000 = 100.0 USD
    assert res.revenue_scenarios.base.expected_revenue == 100.0

    assert res.profit_scenarios.available
    # Base profit = 100.0 - 50.0 = 50.0 USD
    assert res.profit_scenarios.base.expected_profit == 50.0


def test_synthetic_lower_views_higher_profitability_ranking_sanity():
    """Acceptance test 22: Controlled synthetic test where Cluster B (fewer views, better audience, lower cost/risk)

    ranks above Cluster A (more views, higher cost/risk).
    """
    engine = ProfitabilityEngine()

    videos_a = [{"view_count": 50000, "duration_seconds": 600}]
    risk_a = ClusterProductionRisk(
        cluster_id=1,
        production_cost_score=90.0, # High cost
        overall_risk_score=80.0,   # High risk
        risk_level=RiskLevel.HIGH,
    )

    videos_b = [{"view_count": 20000, "duration_seconds": 600}]
    risk_b = ClusterProductionRisk(
        cluster_id=2,
        production_cost_score=10.0, # Low cost
        overall_risk_score=10.0,   # Low risk
        risk_level=RiskLevel.LOW,
    )

    analysis_a = engine.analyze_cluster(
        run_id="run1", cluster_id=1, niche="A", subniche="A", microniche="A",
        cluster_videos=videos_a, production_risk=risk_a, dataset_hash="h", assignments_hash="h"
    )

    analysis_b = engine.analyze_cluster(
        run_id="run1", cluster_id=2, niche="B", subniche="B", microniche="B",
        cluster_videos=videos_b, production_risk=risk_b, dataset_hash="h", assignments_hash="h"
    )

    assert analysis_b.profitability_score > analysis_a.profitability_score
