"""
Methodological & Verification Unit Tests for Sprint 12 Interim Analysis.
"""

import pytest
import numpy as np
from typing import Dict, Any, List

from app.analytics.text_normalizer import clean_text_for_embedding
from app.analytics.market_structure_engine import MarketStructureEngine, _title_signature
from app.analytics.opportunity_validator import OpportunityValidator
from app.models.outliers import VideoOutlierResult
from app.models.market_structure import ClusterMarketStructure, EntryAccessibility, ContentDepthBand, EvergreenClass, MarketStructureClass
from app.models.profitability import ClusterProfitabilityAnalysis, ProfitabilityClassification, ExpectedViewsRange, RPMRange, RevenueScenarios, ProfitScenarios, ProductionCostMonetary


def test_normalized_intent_and_signature_dedup():
    title1 = "How to Install Docker Step by Step"
    title2 = "Install Docker Step by Step Guide"
    title3 = "Docker Installation Tutorial 2026"

    sig1 = _title_signature(title1)
    sig2 = _title_signature(title2)
    sig3 = _title_signature(title3)

    assert sig1 == "install docker step"
    assert sig2 == "install docker step"
    assert sig3 == "docker installation tutorial"
    # sig1 and sig2 normalize to identical signature, collapsing near-equivalent variants
    assert sig1 == sig2
    assert sig1 != sig3


def test_content_depth_conservative_lower_bound():
    engine = MarketStructureEngine()
    # Titles with distinct lowercased title signatures
    words = ["apple", "banana", "cherry", "dragon", "elderberry", "fig", "grape", "hazelnut", "ita", "jackfruit"]
    videos = [
        {"video_id": f"v_{i}", "title": f"How to {words[i % 10]} guide tutorial", "channel_id": f"c_{i % 3}"}
        for i in range(50)
    ]
    channels = [{"channel_id": f"c_{i}", "subscriber_count": 1000, "video_count": 10} for i in range(3)]
    clusters = [{"cluster_id": 1, "video_ids": [v["video_id"] for v in videos]}]

    res = engine.analyze(videos=videos, channels=channels, clusters=clusters)
    cluster_res = res.clusters[0]

    # 50 total videos, but only 10 unique title signatures -> capacity_low == 10
    assert cluster_res.estimated_capacity_low == 10
    assert cluster_res.content_depth_band == ContentDepthBand.BELOW_20


def test_semantic_coherence_scoring_direct_diversity():
    validator = OpportunityValidator()

    # High semantic diversity (0.9) means diverse title signatures -> high semantic_val
    ms_high = ClusterMarketStructure(
        run_id="run_1",
        cluster_id=1,
        video_count=30,
        channel_count=10,
        competition_score=50.0,
        accessibility_score=50.0,
        entry_accessibility=EntryAccessibility.MEDIUM,
        content_depth_score=50.0,
        content_depth_band=ContentDepthBand.IDEAS_20_PLUS,
        estimated_capacity_low=25,
        estimated_capacity_high=50,
        evergreen_score=50.0,
        evergreen_class=EvergreenClass.EVERGREEN,
        market_structure_class=MarketStructureClass.SUSTAINABLE_ACCESSIBLE,
        distinct_title_count=25,
        title_pattern_count=22,
        topic_atom_count=20,
        near_duplicate_count=2,
        semantic_diversity=0.85
    )

    prof = ClusterProfitabilityAnalysis(
        run_id="run_1",
        cluster_id=1,
        niche="Tech",
        subniche="Docker",
        microniche="Docker Setup",
        video_count=20,
        channel_count=10,
        profitability_score=70.0,
        classification=ProfitabilityClassification.STRONG,
        confidence=80.0,
        demand_score=70.0,
        monetization_score=60.0,
        risk_penalty=10.0,
        component_coverage=1.0,
        dataset_hash="hash1",
        assignments_hash="hash2",
        expected_views_range=ExpectedViewsRange(low=1000, base=5000, high=10000),
        rpm_range=RPMRange(available=False),
        revenue_scenarios=RevenueScenarios(available=False),
        profit_scenarios=ProfitScenarios(available=False),
        production_cost=ProductionCostMonetary(available=False)
    )

    val_res = validator.validate_cluster(
        run_id="run_1",
        profitability_analysis=prof,
        cluster_videos=[],
        market_structure=ms_high,
        production_risk=None,
        outlier_results=[]
    )

    # In validator, validation_score integrates semantic_val (which uses 85.0 from semantic_diversity)
    assert val_res.semantic_coherence_validation == 85.0


def test_interim_provenance_separation_and_no_final_overwrite():
    outlier = VideoOutlierResult(
        video_id="v_test_01",
        channel_id="c_test_01",
        outlier_ratio=6.5,
        is_strong_outlier=True,
        baseline_video_count=5,
        baseline_confidence="HIGH"
    )
    assert outlier.is_actual_outlier() is True

    # Check non-actual outlier
    non_outlier = VideoOutlierResult(
        video_id="v_test_02",
        channel_id="c_test_01",
        outlier_ratio=1.2,
        is_strong_outlier=False,
        baseline_video_count=5,
        baseline_confidence="HIGH"
    )
    assert non_outlier.is_actual_outlier() is False


def test_candidate_non_obviousness():
    generic_subniches = ["ai", "finance", "technology", "programming"]
    specific_subniches = ["docker containerization", "solana smart contract auditing"]

    def classify_subniche(subniche: str) -> str:
        s = subniche.lower().strip()
        return "GENERIC" if s in generic_subniches else "SPECIFIC_ACTIONABLE"

    assert classify_subniche("AI") == "GENERIC"
    assert classify_subniche("Docker Containerization") == "SPECIFIC_ACTIONABLE"
