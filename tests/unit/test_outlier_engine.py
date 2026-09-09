"""
Unit tests for OutlierEngine in PRYTB Sprint 4.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

from app.analytics.outlier_engine import (
    OutlierEngine,
    calculate_median,
    calculate_mean,
    classify_baseline_confidence
)
from app.models.metrics import VideoHistoricalMetrics, MetricInterval
from app.models.outliers import VideoOutlierResult


def test_calculate_median_and_mean():
    # Odd list
    assert calculate_median([10, 20, 30]) == 20.0
    # Even list
    assert calculate_median([10, 20, 30, 40]) == 25.0
    # Single element
    assert calculate_median([50]) == 50.0
    # Empty
    assert calculate_median([]) is None

    # Mean
    assert calculate_mean([10, 20, 30]) == 20.0
    assert calculate_mean([10, 20]) == 15.0
    assert calculate_mean([]) is None


def test_classify_baseline_confidence():
    assert classify_baseline_confidence(1) == "VERY_LOW"
    assert classify_baseline_confidence(2) == "VERY_LOW"
    assert classify_baseline_confidence(3) == "LOW"
    assert classify_baseline_confidence(4) == "LOW"
    assert classify_baseline_confidence(5) == "MEDIUM"
    assert classify_baseline_confidence(9) == "MEDIUM"
    assert classify_baseline_confidence(10) == "HIGH"


def test_outlier_ratios_5x_10x_25x():
    mock_repo = MagicMock()
    mock_metrics = MagicMock()

    mock_repo.get_video_by_id.side_effect = lambda v_id: {
        "video_id": v_id,
        "channel_id": "UC_TEST",
        "title": f"Video {v_id}",
        "published_at": "2026-01-01T00:00:00Z"
    }
    mock_repo.get_channel_by_id.return_value = {
        "channel_id": "UC_TEST",
        "title": "Test Channel"
    }

    # Baseline videos: 10 videos with median = 1000 views
    baseline_vids = [{"video_id": f"v_{i}", "channel_id": "UC_TEST"} for i in range(10)]
    # Target videos: v_5x (5000 views), v_10x (10000 views), v_25x (25000 views)
    all_vids = baseline_vids + [
        {"video_id": "v_5x", "channel_id": "UC_TEST"},
        {"video_id": "v_10x", "channel_id": "UC_TEST"},
        {"video_id": "v_25x", "channel_id": "UC_TEST"},
    ]
    mock_repo.get_all_videos.return_value = all_vids

    def mock_analyze(v_id, video_info=None, snapshots=None):
        views = 1000
        if v_id == "v_5x":
            views = 5000
        elif v_id == "v_10x":
            views = 10000
        elif v_id == "v_25x":
            views = 25000
        return VideoHistoricalMetrics(
            video_id=v_id,
            snapshot_count=2,
            latest_views=views,
            video_age_days=10.0,
            lifetime_views_per_day=views / 10.0,
            latest_velocity=10.0,
            latest_acceleration=None,
            intervals=[],
            warnings=[]
        )

    mock_metrics.analyze_video.side_effect = mock_analyze
    mock_repo.get_latest_channel_metrics.return_value = {"subscriber_count": 10000}

    engine = OutlierEngine(repository=mock_repo, metrics_analyzer=mock_metrics)

    res_5x = engine.analyze_video("v_5x", exclude_self_from_baseline=True)
    assert res_5x.outlier_ratio == 5.0
    assert res_5x.is_strong_outlier is True
    assert res_5x.is_major_outlier is False
    assert res_5x.is_extreme_outlier is False

    res_10x = engine.analyze_video("v_10x", exclude_self_from_baseline=True)
    assert res_10x.outlier_ratio == 10.0
    assert res_10x.is_strong_outlier is True
    assert res_10x.is_major_outlier is True
    assert res_10x.is_extreme_outlier is False

    res_25x = engine.analyze_video("v_25x", exclude_self_from_baseline=True)
    assert res_25x.outlier_ratio == 25.0
    assert res_25x.is_strong_outlier is True
    assert res_25x.is_major_outlier is True
    assert res_25x.is_extreme_outlier is True


def test_exclude_self_from_baseline():
    mock_repo = MagicMock()
    mock_metrics = MagicMock()

    mock_repo.get_video_by_id.side_effect = lambda v_id: {
        "video_id": v_id,
        "channel_id": "UC_EXCLUDE",
        "title": f"Video {v_id}"
    }

    # Channel has 3 videos: 1000, 1000, and viral video 1,000,000
    vids = [
        {"video_id": "v1", "channel_id": "UC_EXCLUDE"},
        {"video_id": "v2", "channel_id": "UC_EXCLUDE"},
        {"video_id": "v_viral", "channel_id": "UC_EXCLUDE"},
    ]
    mock_repo.get_all_videos.return_value = vids

    def mock_analyze(v_id, video_info=None, snapshots=None):
        views = 1000000 if v_id == "v_viral" else 1000
        return VideoHistoricalMetrics(
            video_id=v_id,
            snapshot_count=1,
            latest_views=views,
            video_age_days=5.0,
            lifetime_views_per_day=views / 5.0,
            latest_velocity=None,
            latest_acceleration=None,
            intervals=[],
            warnings=[]
        )

    mock_metrics.analyze_video.side_effect = mock_analyze
    mock_repo.get_latest_channel_metrics.return_value = {"subscriber_count": 5000}

    engine = OutlierEngine(repository=mock_repo, metrics_analyzer=mock_metrics)

    # Exclude self -> baseline median is 1000. Ratio = 1000000 / 1000 = 1000.0
    res_ex = engine.analyze_video("v_viral", exclude_self_from_baseline=True)
    assert res_ex.channel_median_views == 1000.0
    assert res_ex.outlier_ratio == 1000.0

    # Include self -> baseline median of [1000, 1000, 1000000] is 1000.
    res_in = engine.analyze_video("v_viral", exclude_self_from_baseline=False)
    assert res_in.channel_median_views == 1000.0


def test_median_zero_and_none_handling():
    mock_repo = MagicMock()
    mock_metrics = MagicMock()

    mock_repo.get_video_by_id.return_value = {
        "video_id": "v_zero",
        "channel_id": "UC_ZERO",
        "title": "Zero Video"
    }

    mock_repo.get_all_videos.return_value = [
        {"video_id": "v_zero", "channel_id": "UC_ZERO"},
        {"video_id": "v_other", "channel_id": "UC_ZERO"}
    ]

    # Other video has 0 views
    def mock_analyze(v_id, video_info=None, snapshots=None):
        return VideoHistoricalMetrics(
            video_id=v_id,
            snapshot_count=1,
            latest_views=500 if v_id == "v_zero" else 0,
            video_age_days=1.0,
            lifetime_views_per_day=500.0 if v_id == "v_zero" else 0.0,
            latest_velocity=None,
            latest_acceleration=None,
            intervals=[],
            warnings=[]
        )

    mock_metrics.analyze_video.side_effect = mock_analyze
    mock_repo.get_latest_channel_metrics.return_value = {"subscriber_count": 0}

    engine = OutlierEngine(repository=mock_repo, metrics_analyzer=mock_metrics)
    res = engine.analyze_video("v_zero", exclude_self_from_baseline=True)

    assert res.channel_median_views == 0.0
    assert res.outlier_ratio is None
    assert res.age_normalized_outlier_ratio is None
    assert res.views_to_subscribers_ratio is None
    assert any("Division by zero" in w for w in res.warnings)


def test_small_channel_and_hidden_subscribers():
    mock_repo = MagicMock()
    mock_metrics = MagicMock()

    mock_repo.get_video_by_id.return_value = {
        "video_id": "v_small",
        "channel_id": "UC_SMALL"
    }
    mock_repo.get_all_videos.return_value = [
        {"video_id": "v_small", "channel_id": "UC_SMALL"},
        {"video_id": "v_b1", "channel_id": "UC_SMALL"},
        {"video_id": "v_b2", "channel_id": "UC_SMALL"},
        {"video_id": "v_b3", "channel_id": "UC_SMALL"}
    ]

    mock_metrics.analyze_video.side_effect = lambda v_id, video_info=None, snapshots=None: VideoHistoricalMetrics(
        video_id=v_id,
        snapshot_count=1,
        latest_views=50000 if v_id == "v_small" else 1000,
        video_age_days=10.0,
        lifetime_views_per_day=5000.0 if v_id == "v_small" else 100.0,
        latest_velocity=None,
        latest_acceleration=None,
        intervals=[],
        warnings=[]
    )

    # 1. Small channel with subscribers = 10,000 (<= 50,000)
    mock_repo.get_latest_channel_metrics.return_value = {"subscriber_count": 10000}
    engine = OutlierEngine(repository=mock_repo, metrics_analyzer=mock_metrics)
    res1 = engine.analyze_video("v_small")
    assert res1.is_small_channel is True
    assert res1.small_channel_outlier is True
    assert res1.views_to_subscribers_ratio == 5.0

    # 2. Hidden subscribers (subscriber_count = None)
    mock_repo.get_latest_channel_metrics.return_value = {"subscriber_count": None}
    res2 = engine.analyze_video("v_small")
    assert res2.is_small_channel is None
    assert res2.small_channel_outlier is False
    assert res2.views_to_subscribers_ratio is None
    assert any("hidden or unavailable" in w for w in res2.warnings)


def test_short_acceleration_interval():
    mock_repo = MagicMock()
    mock_metrics = MagicMock()

    mock_repo.get_video_by_id.return_value = {
        "video_id": "v_short",
        "channel_id": "UC_SHORT"
    }
    mock_repo.get_all_videos.return_value = [
        {"video_id": "v_short", "channel_id": "UC_SHORT"},
        {"video_id": "v_b1", "channel_id": "UC_SHORT"}
    ]

    interval_short = MetricInterval(
        previous_at="2026-01-01T10:00:00Z",
        current_at="2026-01-01T10:15:00Z",  # 0.25 hours < 1.0 hour
        elapsed_seconds=900.0,
        elapsed_hours=0.25,
        elapsed_days=0.0104,
        view_delta=100,
        view_velocity=400.0
    )

    mock_metrics.analyze_video.return_value = VideoHistoricalMetrics(
        video_id="v_short",
        snapshot_count=3,
        latest_views=5000,
        video_age_days=1.0,
        lifetime_views_per_day=5000.0,
        latest_velocity=400.0,
        latest_acceleration=100.0,
        intervals=[interval_short],
        warnings=[]
    )

    mock_repo.get_latest_channel_metrics.return_value = {"subscriber_count": 5000}

    engine = OutlierEngine(repository=mock_repo, metrics_analyzer=mock_metrics)
    res = engine.analyze_video("v_short")

    assert res.latest_acceleration == 100.0
    assert any("short interval" in w for w in res.warnings)


def test_analyze_all_and_ranking():
    mock_repo = MagicMock()
    mock_metrics = MagicMock()

    vids = [
        {"video_id": "v1", "channel_id": "c1", "title": "Vid 1"},
        {"video_id": "v2", "channel_id": "c1", "title": "Vid 2"},
        {"video_id": "v3", "channel_id": "c2", "title": "Vid 3"},
        {"video_id": "v4", "channel_id": "c2", "title": "Vid 4"},
    ]
    channels = [
        {"channel_id": "c1", "title": "Channel 1"},
        {"channel_id": "c2", "title": "Channel 2"},
    ]

    mock_repo.get_all_videos.return_value = vids
    mock_repo.get_all_channels.return_value = channels
    mock_repo.get_all_video_metrics.return_value = []
    mock_repo.get_all_channel_metrics.return_value = []

    def mock_analyze(v_id, video_info=None, snapshots=None):
        views = 1000
        if v_id == "v2":
            views = 20000  # 20X outlier
        elif v_id == "v4":
            views = 5000   # 5X outlier

        return VideoHistoricalMetrics(
            video_id=v_id,
            snapshot_count=1,
            latest_views=views,
            video_age_days=10.0,
            lifetime_views_per_day=views / 10.0,
            latest_velocity=None,
            latest_acceleration=None,
            intervals=[],
            warnings=[]
        )

    mock_metrics.analyze_video.side_effect = mock_analyze
    mock_repo.get_latest_channel_metrics.return_value = {"subscriber_count": 5000}

    engine = OutlierEngine(repository=mock_repo, metrics_analyzer=mock_metrics)
    results = engine.analyze_all()

    assert len(results) == 4

    ranked = engine.rank_outliers(limit=10)
    # Out of 4 videos, only v2 (20x) and v4 (5x) are actual outliers (ratio >= 5.0).
    # v1 and v3 (1000/1000 = 1.0x) are not actual outliers.
    # Therefore limit=10 returns exactly 2 items without padding.
    assert len(ranked) == 2
    assert ranked[0].video_id == "v2"  # Highest outlier rank score
    assert ranked[1].video_id == "v4"
    assert all(r.is_actual_outlier() for r in ranked)


def test_rank_outliers_excludes_non_outliers():
    mock_repo = MagicMock()
    mock_metrics = MagicMock()

    vids = [
        {"video_id": "v_normal1", "channel_id": "c1"},
        {"video_id": "v_normal2", "channel_id": "c1"},
        {"video_id": "v_outlier", "channel_id": "c1"},
    ]
    mock_repo.get_all_videos.return_value = vids
    mock_repo.get_all_channels.return_value = [{"channel_id": "c1"}]
    mock_repo.get_all_video_metrics.return_value = []
    mock_repo.get_all_channel_metrics.return_value = []

    def mock_analyze(v_id, video_info=None, snapshots=None):
        views = 10000 if v_id == "v_outlier" else 1000
        return VideoHistoricalMetrics(
            video_id=v_id,
            snapshot_count=1,
            latest_views=views,
            video_age_days=10.0,
            lifetime_views_per_day=views / 10.0,
            latest_velocity=None,
            latest_acceleration=None,
            intervals=[],
            warnings=[]
        )

    mock_metrics.analyze_video.side_effect = mock_analyze
    mock_repo.get_latest_channel_metrics.return_value = {"subscriber_count": 5000}

    engine = OutlierEngine(repository=mock_repo, metrics_analyzer=mock_metrics)
    ranked = engine.rank_outliers(limit=100)

    # Only 1 video is an actual outlier, 2 normal videos must be excluded
    assert len(ranked) == 1
    assert ranked[0].video_id == "v_outlier"
    assert ranked[0].is_actual_outlier() is True
