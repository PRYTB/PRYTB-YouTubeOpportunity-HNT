from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import math

from app.database.repositories import YouTubeRepository
from app.models.metrics import (
    MetricInterval,
    VideoHistoricalMetrics,
    ChannelHistoricalMetrics,
)
from app.utils.logger import logger


def parse_datetime(dt_val: Any) -> Optional[datetime]:
    if not dt_val:
        return None
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val
    if isinstance(dt_val, str):
        # Clean trailing Z for isoformat parsing if needed
        clean_str = dt_val.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


def compute_delta(curr: Optional[int], prev: Optional[int]) -> Optional[int]:
    if curr is None or prev is None:
        return None
    return curr - prev


def sort_and_deduplicate_snapshots(snapshots: List[Dict[str, Any]]) -> (List[Dict[str, Any]], List[str]):
    warnings = []
    if not snapshots:
        return [], warnings

    # Sort primarily by collected_at timestamp
    def get_ts(s):
        dt = parse_datetime(s.get("collected_at"))
        return dt.timestamp() if dt else 0.0

    sorted_snaps = sorted(snapshots, key=get_ts)

    # Check for duplicates or out-of-order originally
    deduped = []
    seen_timestamps = set()

    for snap in sorted_snaps:
        ts_str = snap.get("collected_at")
        if not ts_str:
            continue
        dt = parse_datetime(ts_str)
        if not dt:
            continue
        ts_key = dt.isoformat()

        if ts_key in seen_timestamps:
            warnings.append(f"Duplicate snapshot ignored for timestamp: {ts_str}")
            continue
        seen_timestamps.add(ts_key)
        deduped.append(snap)

    return deduped, warnings


def calculate_intervals(snapshots: List[Dict[str, Any]], is_channel: bool = False) -> (List[MetricInterval], List[str]):
    intervals: List[MetricInterval] = []
    warnings: List[str] = []

    if len(snapshots) < 2:
        return intervals, warnings

    for i in range(1, len(snapshots)):
        prev_snap = snapshots[i - 1]
        curr_snap = snapshots[i]

        prev_dt = parse_datetime(prev_snap.get("collected_at"))
        curr_dt = parse_datetime(curr_snap.get("collected_at"))

        if not prev_dt or not curr_dt:
            warnings.append(f"Invalid timestamp format in snapshot pair index {i-1} and {i}")
            continue

        elapsed_seconds = (curr_dt - prev_dt).total_seconds()

        if elapsed_seconds <= 0:
            warnings.append(f"Non-positive elapsed time ({elapsed_seconds}s) between {prev_dt.isoformat()} and {curr_dt.isoformat()}")
            continue

        elapsed_hours = elapsed_seconds / 3600.0
        elapsed_days = elapsed_seconds / 86400.0

        if not is_channel:
            view_delta = compute_delta(curr_snap.get("view_count"), prev_snap.get("view_count"))
            like_delta = compute_delta(curr_snap.get("like_count"), prev_snap.get("like_count"))
            comment_delta = compute_delta(curr_snap.get("comment_count"), prev_snap.get("comment_count"))

            if view_delta is not None and view_delta < 0:
                warnings.append(f"Negative view_delta ({view_delta}) recorded between {prev_dt.isoformat()} and {curr_dt.isoformat()}")

            views_per_day = (view_delta / elapsed_days) if (view_delta is not None and elapsed_days > 0) else None
            view_velocity = (view_delta / elapsed_hours) if (view_delta is not None and elapsed_hours > 0) else None

            interval = MetricInterval(
                previous_at=prev_dt.isoformat(),
                current_at=curr_dt.isoformat(),
                elapsed_seconds=elapsed_seconds,
                elapsed_hours=elapsed_hours,
                elapsed_days=elapsed_days,
                view_delta=view_delta,
                like_delta=like_delta,
                comment_delta=comment_delta,
                views_per_day=views_per_day,
                view_velocity=view_velocity,
            )
        else:
            sub_delta = compute_delta(curr_snap.get("subscriber_count"), prev_snap.get("subscriber_count"))
            video_cnt_delta = compute_delta(curr_snap.get("video_count"), prev_snap.get("video_count"))
            view_delta = compute_delta(curr_snap.get("view_count"), prev_snap.get("view_count"))

            views_per_day = (view_delta / elapsed_days) if (view_delta is not None and elapsed_days > 0) else None
            view_velocity = (view_delta / elapsed_hours) if (view_delta is not None and elapsed_hours > 0) else None

            interval = MetricInterval(
                previous_at=prev_dt.isoformat(),
                current_at=curr_dt.isoformat(),
                elapsed_seconds=elapsed_seconds,
                elapsed_hours=elapsed_hours,
                elapsed_days=elapsed_days,
                view_delta=view_delta,
                subscriber_delta=sub_delta,
                video_count_delta=video_cnt_delta,
                views_per_day=views_per_day,
                view_velocity=view_velocity,
            )

        intervals.append(interval)

    return intervals, warnings


def calculate_acceleration(intervals: List[MetricInterval]) -> Optional[float]:
    if len(intervals) < 2:
        return None

    prev_interval = intervals[-2]
    curr_interval = intervals[-1]

    v1 = prev_interval.view_velocity
    v2 = curr_interval.view_velocity

    if v1 is None or v2 is None:
        return None

    # Midpoints of intervals for timestamp difference
    t1_prev = parse_datetime(prev_interval.previous_at)
    t1_curr = parse_datetime(prev_interval.current_at)
    t2_prev = parse_datetime(curr_interval.previous_at)
    t2_curr = parse_datetime(curr_interval.current_at)

    if not t1_prev or not t1_curr or not t2_prev or not t2_curr:
        return None

    mid1 = t1_prev.timestamp() + (t1_curr.timestamp() - t1_prev.timestamp()) / 2.0
    mid2 = t2_prev.timestamp() + (t2_curr.timestamp() - t2_prev.timestamp()) / 2.0

    elapsed_hours_between = (mid2 - mid1) / 3600.0

    if elapsed_hours_between <= 0:
        return None

    acceleration = (v2 - v1) / elapsed_hours_between
    return acceleration


class HistoricalMetricsAnalyzer:
    def __init__(self, repository: Optional[YouTubeRepository] = None):
        self.repository = repository or YouTubeRepository()

    def analyze_video(
        self,
        video_id: str,
        video_info: Optional[Dict[str, Any]] = None,
        snapshots: Optional[List[Dict[str, Any]]] = None
    ) -> VideoHistoricalMetrics:
        if snapshots is None:
            snapshots = self.repository.get_video_metrics_history(video_id)

        clean_snaps, warnings = sort_and_deduplicate_snapshots(snapshots)
        snapshot_count = len(clean_snaps)

        latest_views = clean_snaps[-1].get("view_count") if clean_snaps else None

        # Fetch video metadata for published_at if not provided
        if video_info is None and video_id:
            video_info = self.repository.get_video_by_id(video_id)

        published_at_dt = parse_datetime(video_info.get("published_at")) if video_info else None
        latest_snap_dt = parse_datetime(clean_snaps[-1].get("collected_at")) if clean_snaps else None

        video_age_days: Optional[float] = None
        lifetime_views_per_day: Optional[float] = None

        if published_at_dt and latest_snap_dt:
            age_seconds = (latest_snap_dt - published_at_dt).total_seconds()
            if age_seconds >= 0:
                video_age_days = age_seconds / 86400.0
                if video_age_days > 0 and latest_views is not None:
                    lifetime_views_per_day = latest_views / video_age_days
            else:
                warnings.append(f"Published date {published_at_dt.isoformat()} is after latest snapshot {latest_snap_dt.isoformat()}")

        intervals, interval_warnings = calculate_intervals(clean_snaps, is_channel=False)
        warnings.extend(interval_warnings)

        latest_velocity = intervals[-1].view_velocity if intervals else None
        latest_acceleration = calculate_acceleration(intervals)

        return VideoHistoricalMetrics(
            video_id=video_id,
            snapshot_count=snapshot_count,
            latest_views=latest_views,
            video_age_days=video_age_days,
            lifetime_views_per_day=lifetime_views_per_day,
            latest_velocity=latest_velocity,
            latest_acceleration=latest_acceleration,
            intervals=intervals,
            warnings=warnings,
        )

    def analyze_channel(
        self,
        channel_id: str,
        snapshots: Optional[List[Dict[str, Any]]] = None
    ) -> ChannelHistoricalMetrics:
        if snapshots is None:
            snapshots = self.repository.get_channel_metrics_history(channel_id)

        clean_snaps, warnings = sort_and_deduplicate_snapshots(snapshots)
        snapshot_count = len(clean_snaps)

        latest_snap = clean_snaps[-1] if clean_snaps else {}
        latest_subscribers = latest_snap.get("subscriber_count")
        latest_views = latest_snap.get("view_count")
        latest_video_count = latest_snap.get("video_count")

        intervals, interval_warnings = calculate_intervals(clean_snaps, is_channel=True)
        warnings.extend(interval_warnings)

        return ChannelHistoricalMetrics(
            channel_id=channel_id,
            snapshot_count=snapshot_count,
            latest_subscribers=latest_subscribers,
            latest_views=latest_views,
            latest_video_count=latest_video_count,
            intervals=intervals,
            warnings=warnings,
        )

    def analyze_videos(self, video_ids: List[str]) -> Dict[str, VideoHistoricalMetrics]:
        results = {}
        for v_id in video_ids:
            results[v_id] = self.analyze_video(v_id)
        return results
