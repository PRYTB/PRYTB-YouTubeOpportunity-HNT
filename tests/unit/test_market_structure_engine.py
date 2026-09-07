"""Unit tests for Sprint 7 market-structure analysis."""

from datetime import datetime, timezone

import pytest

from app.analytics.market_structure_engine import MarketStructureEngine
from app.config.market_structure_config import MarketStructureConfig
from app.models.market_structure import (
    ContentDepthBand,
    EvergreenClass,
    MarketStructureClass,
)
from app.models.outliers import VideoOutlierResult

AS_OF = datetime(2026, 9, 3, tzinfo=timezone.utc)


def analyze(videos, channels, config=None, outlier_results=(), cluster=None):
    cluster = cluster or {
        "cluster_id": 0,
        "video_ids": [item["video_id"] for item in videos],
    }
    return MarketStructureEngine(config).analyze(
        videos,
        channels,
        [cluster],
        as_of=AS_OF,
        outlier_results=outlier_results,
    ).clusters[0]


def test_competition_concentration_and_hhi_are_observed():
    videos = [
        {"video_id": "v1", "channel_id": "a", "title": "one", "view_count": 10},
        {"video_id": "v2", "channel_id": "a", "title": "two", "view_count": 20},
        {"video_id": "v3", "channel_id": "a", "title": "three", "view_count": 30},
        {"video_id": "v4", "channel_id": "b", "title": "four", "view_count": 40},
    ]

    cluster = analyze(videos, [{"channel_id": "a"}, {"channel_id": "b"}])

    assert cluster.dominant_channel_share == 75.0
    assert cluster.channel_hhi == 62.5
    assert 0 <= cluster.competition_score <= 100


def test_small_channel_metrics_consume_sprint4_results_by_video_identity():
    videos = [
        {"video_id": f"v{i}", "channel_id": "small", "title": f"topic {i}", "view_count": 100}
        for i in range(3)
    ]
    channels = [{"channel_id": "small", "subscriber_count": 1000}]
    outlier_results = [
        VideoOutlierResult(
            video_id="v0",
            channel_id="small",
            is_small_channel=True,
            outlier_ratio=2.0,
            is_strong_outlier=True,
            small_channel_outlier=True,
            outlier_rank_score=60.0,
        ),
        VideoOutlierResult(
            video_id="v1",
            channel_id="small",
            is_small_channel=True,
            outlier_ratio=4.0,
            is_strong_outlier=True,
            is_major_outlier=True,
            small_channel_outlier=True,
            outlier_rank_score=80.0,
        ),
        VideoOutlierResult(
            video_id="v2",
            channel_id="small",
            is_small_channel=True,
            outlier_ratio=6.0,
            is_strong_outlier=True,
            is_major_outlier=True,
            is_extreme_outlier=True,
            small_channel_outlier=False,
            outlier_rank_score=100.0,
        ),
    ]

    cluster = analyze(videos, channels, outlier_results=outlier_results)

    assert cluster.outlier_results_available == 3
    assert cluster.small_channel_eligible_videos == 3
    assert cluster.small_channel_successes == 2
    assert cluster.small_channel_success_rate == pytest.approx(66.6667)
    assert cluster.strong_outlier_count == 3
    assert cluster.major_outlier_count == 2
    assert cluster.extreme_outlier_count == 1
    assert cluster.median_outlier_ratio == 4.0
    assert cluster.max_outlier_ratio == 6.0
    assert cluster.average_outlier_rank_score == 80.0


def test_small_channel_sample_requires_non_zero_sufficient_baseline():
    videos = [
        {"video_id": "v1", "channel_id": "small", "title": "one", "view_count": 500},
        {"video_id": "v2", "channel_id": "small", "title": "two", "view_count": 0},
    ]
    cluster = analyze(videos, [{"channel_id": "small", "subscriber_count": 10}])

    assert cluster.small_channel_eligible_videos == 0
    assert cluster.small_channel_success_rate is None
    assert any("No eligible small-channel" in warning for warning in cluster.warnings)


@pytest.mark.parametrize(
    "signature_count, expected_band, expected_ideas",
    [
        (19, ContentDepthBand.BELOW_20, 19),
        (20, ContentDepthBand.IDEAS_20_PLUS, 20),
        (50, ContentDepthBand.IDEAS_50_PLUS, 50),
        (100, ContentDepthBand.IDEAS_100_PLUS, 100),
    ],
)
def test_content_depth_bands_use_literal_capacity_boundaries(
    signature_count, expected_band, expected_ideas
):
    config = MarketStructureConfig(idea_multiplier=1)
    videos = [
        {
            "video_id": f"v{i}",
            "channel_id": f"c{i}",
            "title": f"alpha beta topic{chr(97 + i // 26)}{chr(97 + i % 26)}",
        }
        for i in range(signature_count)
    ]

    cluster = analyze(videos, [], config)

    assert cluster.topic_atom_count == signature_count
    assert cluster.estimated_capacity_low == signature_count
    assert cluster.content_depth_band is expected_band
    assert cluster.estimated_distinct_ideas == expected_ideas


def test_interval_crossing_literal_boundary_is_below_20():
    videos = [
        {
            "video_id": f"v{i}",
            "channel_id": "c",
            "title": f"alpha beta topic{chr(97 + i)}",
        }
        for i in range(10)
    ]

    cluster = analyze(videos, [{"channel_id": "c"}])

    assert cluster.estimated_capacity_low == 10
    assert cluster.estimated_capacity_high == 50
    assert cluster.content_depth_band is ContentDepthBand.BELOW_20


def test_four_video_weak_diversity_does_not_extrapolate_to_100_plus():
    videos = [
        {"video_id": f"v{i}", "channel_id": "c", "title": f"same topic episode {i}"}
        for i in range(4)
    ]

    cluster = analyze(videos, [{"channel_id": "c"}])

    assert cluster.topic_atom_count == 1
    assert cluster.near_duplicate_count == 3
    assert cluster.semantic_diversity == 0.25
    assert cluster.depth_confidence == 20.0
    assert cluster.estimated_capacity_high < 20
    assert cluster.content_depth_band is ContentDepthBand.BELOW_20
    assert cluster.content_depth_score < 100


def test_exact_duplicates_and_small_samples_reduce_depth_confidence():
    duplicate_cluster = analyze(
        [
            {"video_id": f"duplicate-{i}", "channel_id": "c", "title": "same exact title"}
            for i in range(5)
        ],
        [{"channel_id": "c"}],
    )
    small_cluster = analyze(
        [
            {
                "video_id": f"small-{i}",
                "channel_id": "c",
                "title": f"alpha beta topic{chr(97 + i)}",
            }
            for i in range(2)
        ],
        [{"channel_id": "c"}],
    )

    assert duplicate_cluster.near_duplicate_count == 4
    assert duplicate_cluster.depth_confidence == 20.0
    assert small_cluster.semantic_diversity == 1.0
    assert small_cluster.depth_confidence == 40.0


def test_format_facet_count_uses_observed_known_formats():
    videos = [
        {"video_id": "short", "channel_id": "c", "title": "short topic", "duration_seconds": 30},
        {"video_id": "long", "channel_id": "c", "title": "long topic", "duration_seconds": 600},
        {"video_id": "unknown", "channel_id": "c", "title": "unknown topic"},
    ]

    cluster = analyze(videos, [{"channel_id": "c"}])

    assert cluster.short_video_count == 1
    assert cluster.long_form_video_count == 1
    assert cluster.unknown_format_count == 1
    assert cluster.format_facet_count == 2


def test_depth_score_does_not_clip_all_distinct_clusters_to_100():
    clusters = [
        analyze(
            [
                {
                    "video_id": f"v{size}-{i}",
                    "channel_id": "c",
                    "title": f"distinct topic item{chr(97 + i)}",
                }
                for i in range(size)
            ],
            [{"channel_id": "c"}],
        )
        for size in (4, 5, 10)
    ]

    assert all(cluster.content_depth_score < 100 for cluster in clusters)
    assert len({cluster.content_depth_score for cluster in clusters}) > 1


def test_missing_small_channel_sample_reduces_accessibility_confidence():
    videos = [
        {
            "video_id": f"v{i}",
            "channel_id": "c",
            "title": f"topic {i}",
            "published_at": "2025-01-01T00:00:00Z",
        }
        for i in range(5)
    ]
    channel = {"channel_id": "c", "published_at": "2020-01-01T00:00:00Z"}

    cluster = analyze(videos, [channel])

    assert cluster.small_channel_success_rate is None
    assert cluster.accessibility_confidence == 50.0
    assert cluster.confidence < 100


def test_evergreen_trend_and_unknown_classification():
    recent = analyze(
        [{"video_id": "v", "channel_id": "c", "title": "topic", "published_at": "2026-08-01T00:00:00Z"}],
        [{"channel_id": "c"}],
    )
    unknown = analyze(
        [{"video_id": "v", "channel_id": "c", "title": "topic", "published_at": "invalid"}],
        [{"channel_id": "c"}],
    )
    evergreen = analyze(
        [
            {"video_id": "old", "channel_id": "a", "title": "old topic", "published_at": "2020-01-01T00:00:00Z"},
            {"video_id": "new", "channel_id": "b", "title": "new topic", "published_at": "2025-01-01T00:00:00Z"},
        ],
        [{"channel_id": "a"}, {"channel_id": "b"}],
    )

    assert recent.evergreen_class is EvergreenClass.TREND
    assert unknown.evergreen_class is EvergreenClass.UNKNOWN
    assert evergreen.evergreen_class is EvergreenClass.EVERGREEN


def test_missing_titles_remain_unknown_not_content_constrained():
    cluster = analyze(
        [{"video_id": "v", "channel_id": "c", "title": "", "published_at": "invalid"}],
        [{"channel_id": "c"}],
    )

    assert cluster.content_depth_band is ContentDepthBand.UNKNOWN
    assert cluster.market_structure_class is MarketStructureClass.UNCERTAIN


def test_quality_and_confidence_report_invalid_or_missing_evidence():
    result = MarketStructureEngine().analyze(
        [{"video_id": "v", "channel_id": "c", "title": "topic", "view_count": True, "published_at": "2099-01-01"}],
        [{"channel_id": "c", "subscriber_count": -1, "published_at": "invalid"}],
        [{"cluster_id": 0, "video_ids": ["v", "missing"]}],
        as_of=AS_OF,
    )

    assert result.quality.subscriber_unknown_rate == 100.0
    assert result.quality.views_unknown_rate == 100.0
    assert result.quality.publication_date_unknown_rate == 100.0
    assert result.clusters[0].confidence == 0.0
    assert any("absent" in warning for warning in result.clusters[0].warnings)


def test_market_structure_functional_classes_are_reachable():
    base_video = {
        "video_id": "v",
        "channel_id": "c",
        "title": "specific topic",
        "view_count": 200000,
        "published_at": "2024-01-01T00:00:00Z",
    }
    channel = {
        "channel_id": "c",
        "subscriber_count": 1000,
        "published_at": "2020-01-01T00:00:00Z",
    }

    viral = analyze(
        [base_video],
        [channel],
        MarketStructureConfig(saturated_competition_min=0),
    )
    constrained = analyze(
        [{**base_video, "view_count": 10}],
        [channel],
    )
    sustainable_videos = [
        {
            **base_video,
            "video_id": f"v{i}",
            "title": f"specific topic item{chr(97 + i)}",
            "view_count": 10,
        }
        for i in range(20)
    ]
    sustainable = analyze(
        sustainable_videos,
        [channel],
        MarketStructureConfig(
            idea_multiplier=1,
            medium_accessibility_min=0,
            high_accessibility_min=0,
        ),
    )

    assert viral.market_structure_class is MarketStructureClass.VIRAL_SATURATED
    assert constrained.market_structure_class is MarketStructureClass.CONTENT_CONSTRAINED
    assert sustainable.market_structure_class is MarketStructureClass.SUSTAINABLE_ACCESSIBLE


def test_intermediate_age_is_semi_evergreen_and_large_channels_are_not_eligible():
    videos = [
        {
            "video_id": f"v{i}",
            "channel_id": "large",
            "title": f"topic {i}",
            "view_count": 100,
            "published_at": "2025-09-03T00:00:00Z",
        }
        for i in range(3)
    ]

    cluster = analyze(
        videos,
        [{"channel_id": "large", "subscriber_count": 50001}],
    )

    assert cluster.evergreen_class is EvergreenClass.SEMI_EVERGREEN
    assert cluster.small_channel_eligible_videos == 0
