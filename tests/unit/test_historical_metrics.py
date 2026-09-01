import pytest
from datetime import datetime, timezone
from app.analytics.historical_metrics import (
    compute_delta,
    calculate_intervals,
    calculate_acceleration,
    HistoricalMetricsAnalyzer,
)
from app.models.metrics import MetricInterval


def test_delta_computations():
    assert compute_delta(100, 50) == 50
    assert compute_delta(50, 50) == 0
    assert compute_delta(40, 50) == -10
    assert compute_delta(None, 50) is None
    assert compute_delta(100, None) is None


def test_interval_and_velocity_controlled_math():
    snapshots = [
        {"collected_at": "2026-09-01T10:00:00Z", "view_count": 1000, "like_count": 10, "comment_count": 2},
        {"collected_at": "2026-09-01T12:00:00Z", "view_count": 1400, "like_count": 14, "comment_count": 4},
    ]

    intervals, warnings = calculate_intervals(snapshots, is_channel=False)

    assert len(intervals) == 1
    assert len(warnings) == 0

    interval = intervals[0]
    assert interval.view_delta == 400
    assert interval.like_delta == 4
    assert interval.comment_delta == 2
    assert interval.elapsed_hours == 2.0
    assert interval.view_velocity == 200.0  # 400 views / 2 hours
    assert interval.views_per_day == 4800.0  # 200 * 24


def test_acceleration_3_snapshots():
    # Snap A: 10:00, views=1000
    # Snap B: 12:00, views=1400  -> Velocity 1 = 400/2 = 200 views/h. Midpoint = 11:00
    # Snap C: 14:00, views=2000  -> Velocity 2 = 600/2 = 300 views/h. Midpoint = 13:00
    # Elapsed between midpoints = 2 hours
    # Acceleration = (300 - 200) / 2 = 50 views/hour^2

    snapshots = [
        {"collected_at": "2026-09-01T10:00:00Z", "view_count": 1000},
        {"collected_at": "2026-09-01T12:00:00Z", "view_count": 1400},
        {"collected_at": "2026-09-01T14:00:00Z", "view_count": 2000},
    ]

    intervals, warnings = calculate_intervals(snapshots, is_channel=False)
    assert len(intervals) == 2
    accel = calculate_acceleration(intervals)

    assert accel == 50.0


def test_insufficient_snapshots_for_acceleration():
    snapshots = [
        {"collected_at": "2026-09-01T10:00:00Z", "view_count": 1000},
        {"collected_at": "2026-09-01T12:00:00Z", "view_count": 1400},
    ]
    intervals, _ = calculate_intervals(snapshots)
    accel = calculate_acceleration(intervals)
    assert accel is None


def test_edge_cases_and_anomalies():
    # Negative delta, duplicate timestamps, out of order
    snapshots = [
        {"collected_at": "2026-09-01T12:00:00Z", "view_count": 1400},
        {"collected_at": "2026-09-01T10:00:00Z", "view_count": 1000},
        {"collected_at": "2026-09-01T12:00:00Z", "view_count": 1400},  # Duplicate
        {"collected_at": "2026-09-01T14:00:00Z", "view_count": 800},   # Negative delta
    ]

    analyzer = HistoricalMetricsAnalyzer()
    metrics = analyzer.analyze_video(video_id="test_vid", video_info=None, snapshots=snapshots)

    assert metrics.snapshot_count == 3  # Duplicated 12:00 removed
    assert len(metrics.warnings) > 0  # Duplicate and negative delta warning
    assert metrics.intervals[-1].view_delta == -600  # 800 - 1400


def test_lifetime_views_and_age():
    video_info = {
        "video_id": "vid1",
        "published_at": "2026-08-01T00:00:00Z"
    }
    snapshots = [
        {"collected_at": "2026-08-31T00:00:00Z", "view_count": 30000}
    ]

    analyzer = HistoricalMetricsAnalyzer()
    metrics = analyzer.analyze_video(video_id="vid1", video_info=video_info, snapshots=snapshots)

    assert metrics.video_age_days == 30.0
    assert metrics.lifetime_views_per_day == 1000.0  # 30000 / 30
