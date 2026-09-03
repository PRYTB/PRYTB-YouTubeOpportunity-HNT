"""Tests for Sprint 7 models and editable configuration."""

import pytest
from pydantic import ValidationError

from app.config.market_structure_config import MarketStructureConfig
from app.models.market_structure import (
    ClusterMarketStructure,
    EntryAccessibility,
    Sprint7AnalysisResult,
    Sprint7QualityMetrics,
)


def test_market_structure_defaults_are_valid_and_serializable():
    cluster = ClusterMarketStructure(cluster_id=1)
    result = Sprint7AnalysisResult(
        run_id="run-1",
        analyzed_at="2026-09-03T00:00:00+00:00",
        clusters=[cluster],
        quality=Sprint7QualityMetrics(total_clusters=1),
    )

    payload = result.model_dump(mode="json")

    assert payload["clusters"][0]["accessibility"] == "UNKNOWN"
    assert payload["clusters"][0]["market_structure_class"] == "UNCERTAIN"


@pytest.mark.parametrize(
    "values",
    [
        {"cluster_id": -1},
        {"cluster_id": 0, "competition_score": 101},
        {"cluster_id": 0, "accessibility_score": -1},
        {"cluster_id": 0, "accessibility": "IMPOSSIBLE"},
        {"cluster_id": 0, "channels_with_subscribers": 2, "channel_count": 1},
        {"cluster_id": 0, "new_entrant_channels": 2, "channel_count": 1},
        {"cluster_id": 0, "small_channel_successes": 2, "small_channel_eligible_videos": 1},
        {"cluster_id": 0, "distinct_title_count": 2, "video_count": 1},
    ],
)
def test_market_structure_model_rejects_invalid_values(values):
    with pytest.raises(ValidationError):
        ClusterMarketStructure(**values)


def test_market_structure_config_defaults_and_boundaries():
    config = MarketStructureConfig()

    assert config.small_channel_subscribers_max == 50000
    assert config.small_channel_success_ratio == 5.0
    assert config.medium_accessibility_min < config.high_accessibility_min
    assert config.depth_20_threshold <= config.depth_50_threshold <= config.depth_100_threshold


@pytest.mark.parametrize(
    "values, message",
    [
        ({"small_channel_success_ratio": 0}, "greater than 0"),
        ({"depth_20_threshold": 11, "depth_50_threshold": 10}, "thresholds must be ordered"),
        ({"medium_accessibility_min": 80, "high_accessibility_min": 70}, "thresholds must be ordered"),
        ({"competition_weight_channel_count": 0.4}, "weights must sum to 1.0"),
        ({"accessibility_weight_small_success": 0.4}, "weights must sum to 1.0"),
    ],
)
def test_market_structure_config_rejects_invalid_settings(values, message):
    with pytest.raises(ValidationError, match=message):
        MarketStructureConfig(**values)


def test_explicit_accessibility_enum_is_preserved():
    cluster = ClusterMarketStructure(cluster_id=0, accessibility=EntryAccessibility.HIGH)

    assert cluster.accessibility is EntryAccessibility.HIGH
