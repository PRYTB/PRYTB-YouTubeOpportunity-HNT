"""
Outlier Engine for PRYTB Sprint 4.
Calculates channel baselines, video outlier ratios, age-normalized ratios, velocity signals,
small channel indicators, confidence scores, and ranks outliers.
"""
import math
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.analytics.historical_metrics import HistoricalMetricsAnalyzer, parse_datetime, sort_and_deduplicate_snapshots
from app.database.repositories import YouTubeRepository
from app.models.outliers import VideoOutlierResult
from config import outlier_config as cfg
from app.utils.logger import logger


def calculate_median(values: List[float]) -> Optional[float]:
    """Calculates median of a list of numbers."""
    valid = [v for v in values if v is not None and not math.isnan(v)]
    if not valid:
        return None
    sorted_vals = sorted(valid)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return float(sorted_vals[mid])
    else:
        return float((sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0)


def calculate_mean(values: List[float]) -> Optional[float]:
    """Calculates arithmetic mean of a list of numbers."""
    valid = [v for v in values if v is not None and not math.isnan(v)]
    if not valid:
        return None
    return float(sum(valid) / len(valid))


def classify_baseline_confidence(video_count: int) -> str:
    """Classifies baseline sample size into confidence category."""
    if video_count <= cfg.BASELINE_VERY_LOW_MAX:
        return "VERY_LOW"
    elif video_count <= cfg.BASELINE_LOW_MAX:
        return "LOW"
    elif video_count <= cfg.BASELINE_MEDIUM_MAX:
        return "MEDIUM"
    else:
        return "HIGH"


class OutlierEngine:
    def __init__(
        self,
        repository: Optional[YouTubeRepository] = None,
        metrics_analyzer: Optional[HistoricalMetricsAnalyzer] = None
    ):
        self.repository = repository or YouTubeRepository()
        self.metrics_analyzer = metrics_analyzer or HistoricalMetricsAnalyzer(self.repository)

    def analyze_video(
        self,
        video_id: str,
        exclude_self_from_baseline: bool = True
    ) -> VideoOutlierResult:
        """Analyzes a single video against its channel baseline."""
        video_info = self.repository.get_video_by_id(video_id)
        if not video_info:
            return VideoOutlierResult(
                video_id=video_id,
                channel_id="",
                warnings=[f"Video {video_id} not found in database."]
            )

        channel_id = video_info.get("channel_id", "")
        channel_info = self.repository.get_channel_by_id(channel_id) if channel_id else None

        # Fetch metrics for target video
        target_video_metrics = self.metrics_analyzer.analyze_video(video_id, video_info=video_info)
        
        # Calculate baseline from channel videos
        baseline = self._compute_channel_baseline(
            channel_id=channel_id,
            exclude_video_id=video_id if exclude_self_from_baseline else None
        )

        return self._build_outlier_result(
            video_info=video_info,
            channel_info=channel_info,
            target_metrics=target_video_metrics,
            baseline=baseline
        )

    def analyze_channel(
        self,
        channel_id: str
    ) -> List[VideoOutlierResult]:
        """Analyzes all known videos for a given channel."""
        channel_info = self.repository.get_channel_by_id(channel_id)
        all_videos = self.repository.get_all_videos()
        channel_videos = [v for v in all_videos if v.get("channel_id") == channel_id]

        if not channel_videos:
            return []

        results = []
        for v in channel_videos:
            v_id = v.get("video_id")
            if v_id:
                res = self.analyze_video(v_id, exclude_self_from_baseline=True)
                results.append(res)

        return results

    def analyze_all(self) -> List[VideoOutlierResult]:
        """Analyzes all videos in the database efficiently using batch data fetching."""
        all_videos = self.repository.get_all_videos()
        all_channels = self.repository.get_all_channels()
        all_v_metrics = self.repository.get_all_video_metrics()
        all_c_metrics = self.repository.get_all_channel_metrics()

        # Map channel_id -> channel_info
        channels_map = {c["channel_id"]: c for c in all_channels if "channel_id" in c}

        # Group videos by channel_id
        channel_videos_map: Dict[str, List[Dict[str, Any]]] = {}
        for v in all_videos:
            c_id = v.get("channel_id")
            if c_id:
                channel_videos_map.setdefault(c_id, []).append(v)

        # Group channel_metrics by channel_id
        channel_metrics_map: Dict[str, List[Dict[str, Any]]] = {}
        for cm in all_c_metrics:
            c_id = cm.get("channel_id")
            if c_id:
                channel_metrics_map.setdefault(c_id, []).append(cm)

        # Group video_metrics by video_id
        video_metrics_map: Dict[str, List[Dict[str, Any]]] = {}
        for vm in all_v_metrics:
            v_id = vm.get("video_id")
            if v_id:
                video_metrics_map.setdefault(v_id, []).append(vm)

        # Pre-compute historical metrics per video
        video_hist_map = {}
        for v in all_videos:
            v_id = v.get("video_id")
            if v_id:
                snaps = video_metrics_map.get(v_id, [])
                video_hist_map[v_id] = self.metrics_analyzer.analyze_video(v_id, video_info=v, snapshots=snaps)

        results = []
        for v in all_videos:
            v_id = v.get("video_id")
            c_id = v.get("channel_id")
            if not v_id or not c_id:
                continue

            c_info = channels_map.get(c_id)
            c_vids = channel_videos_map.get(c_id, [])

            # Compute baseline from channel videos (excluding target video)
            baseline = self._compute_channel_baseline_from_cache(
                channel_id=c_id,
                target_video_id=v_id,
                channel_videos=c_vids,
                video_hist_map=video_hist_map
            )

            v_metrics = video_hist_map[v_id]
            res = self._build_outlier_result(
                video_info=v,
                channel_info=c_info,
                target_metrics=v_metrics,
                baseline=baseline,
                latest_channel_metrics=self._get_latest_c_metrics_from_cache(c_id, channel_metrics_map)
            )
            results.append(res)

        return results

    def rank_outliers(self, limit: int = 20) -> List[VideoOutlierResult]:
        """Ranks only actual outliers by OutlierRankScore without padding."""
        all_results = self.analyze_all()
        actual_outliers = [res for res in all_results if res.is_actual_outlier()]
        sorted_results = sorted(actual_outliers, key=lambda x: x.outlier_rank_score, reverse=True)
        return sorted_results[:limit]

    def _compute_channel_baseline(
        self,
        channel_id: str,
        exclude_video_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Computes baseline metrics for a channel by querying DB."""
        all_videos = self.repository.get_all_videos()
        channel_vids = [v for v in all_videos if v.get("channel_id") == channel_id]

        if exclude_video_id:
            baseline_vids = [v for v in channel_vids if v.get("video_id") != exclude_video_id]
        else:
            baseline_vids = channel_vids

        if not baseline_vids:
            return {
                "video_count": 0,
                "median_views": None,
                "mean_views": None,
                "median_views_per_day": None,
                "median_latest_velocity": None,
            }

        views_list = []
        per_day_list = []
        velocity_list = []

        for v in baseline_vids:
            v_id = v.get("video_id")
            if not v_id:
                continue
            v_hist = self.metrics_analyzer.analyze_video(v_id, video_info=v)
            if v_hist.latest_views is not None:
                views_list.append(float(v_hist.latest_views))
            if v_hist.lifetime_views_per_day is not None:
                per_day_list.append(float(v_hist.lifetime_views_per_day))
            if v_hist.latest_velocity is not None:
                velocity_list.append(float(v_hist.latest_velocity))

        return {
            "video_count": len(views_list),
            "median_views": calculate_median(views_list),
            "mean_views": calculate_mean(views_list),
            "median_views_per_day": calculate_median(per_day_list),
            "median_latest_velocity": calculate_median(velocity_list),
        }

    def _compute_channel_baseline_from_cache(
        self,
        channel_id: str,
        target_video_id: str,
        channel_videos: List[Dict[str, Any]],
        video_hist_map: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Computes baseline from pre-cached video metrics."""
        baseline_vids = [v for v in channel_videos if v.get("video_id") != target_video_id]

        if not baseline_vids:
            return {
                "video_count": 0,
                "median_views": None,
                "mean_views": None,
                "median_views_per_day": None,
                "median_latest_velocity": None,
            }

        views_list = []
        per_day_list = []
        velocity_list = []

        for v in baseline_vids:
            v_id = v.get("video_id")
            if not v_id or v_id not in video_hist_map:
                continue
            v_hist = video_hist_map[v_id]
            if v_hist.latest_views is not None:
                views_list.append(float(v_hist.latest_views))
            if v_hist.lifetime_views_per_day is not None:
                per_day_list.append(float(v_hist.lifetime_views_per_day))
            if v_hist.latest_velocity is not None:
                velocity_list.append(float(v_hist.latest_velocity))

        return {
            "video_count": len(views_list),
            "median_views": calculate_median(views_list),
            "mean_views": calculate_mean(views_list),
            "median_views_per_day": calculate_median(per_day_list),
            "median_latest_velocity": calculate_median(velocity_list),
        }

    def _get_latest_c_metrics_from_cache(
        self,
        channel_id: str,
        channel_metrics_map: Dict[str, List[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        snaps = channel_metrics_map.get(channel_id, [])
        if not snaps:
            return None
        clean_snaps, _ = sort_and_deduplicate_snapshots(snaps)
        return clean_snaps[-1] if clean_snaps else None

    def _build_outlier_result(
        self,
        video_info: Dict[str, Any],
        channel_info: Optional[Dict[str, Any]],
        target_metrics: Any,
        baseline: Dict[str, Any],
        latest_channel_metrics: Optional[Dict[str, Any]] = None
    ) -> VideoOutlierResult:
        warnings = list(target_metrics.warnings)
        video_id = video_info.get("video_id", "")
        channel_id = video_info.get("channel_id", "")
        video_title = video_info.get("title") if isinstance(video_info, dict) else None
        channel_title = channel_info.get("title") if isinstance(channel_info, dict) else None

        video_views = target_metrics.latest_views
        baseline_count = baseline["video_count"]
        confidence_cat = classify_baseline_confidence(baseline_count)

        ch_median_views = baseline["median_views"]
        ch_mean_views = baseline["mean_views"]
        ch_median_per_day = baseline["median_views_per_day"]
        ch_median_velocity = baseline["median_latest_velocity"]

        # Outlier Ratio calculation
        outlier_ratio = None
        if video_views is not None and ch_median_views is not None:
            if ch_median_views == 0:
                warnings.append("Channel median views is 0. Division by zero prevented; outlier_ratio set to None.")
            else:
                outlier_ratio = round(video_views / ch_median_views, 4)

        # Age-normalized Outlier Ratio calculation
        age_normalized_ratio = None
        target_per_day = target_metrics.lifetime_views_per_day
        if target_per_day is not None and ch_median_per_day is not None:
            if ch_median_per_day == 0:
                warnings.append("Channel median views/day is 0. Division by zero prevented; age_normalized_outlier_ratio set to None.")
            else:
                age_normalized_ratio = round(target_per_day / ch_median_per_day, 4)

        # Velocity Ratio
        latest_velocity = target_metrics.latest_velocity
        velocity_ratio = None
        if latest_velocity is not None and ch_median_velocity is not None:
            if ch_median_velocity == 0:
                warnings.append("Channel median velocity is 0. Division by zero prevented; velocity_ratio set to None.")
            else:
                velocity_ratio = round(latest_velocity / ch_median_velocity, 4)

        # Acceleration noise control check
        latest_acceleration = target_metrics.latest_acceleration
        if latest_acceleration is not None:
            # Check minimum intervals or snapshot count
            if target_metrics.snapshot_count < cfg.MIN_ACCELERATION_SNAPSHOT_COUNT:
                warnings.append(f"Acceleration ignored for primary signals due to low snapshot count ({target_metrics.snapshot_count} < {cfg.MIN_ACCELERATION_SNAPSHOT_COUNT}).")
            if target_metrics.intervals:
                last_interval_hours = target_metrics.intervals[-1].elapsed_hours
                if last_interval_hours < cfg.MIN_ACCELERATION_INTERVAL_HOURS:
                    warnings.append(f"Acceleration ignored for primary signals due to short interval ({last_interval_hours:.2f}h < {cfg.MIN_ACCELERATION_INTERVAL_HOURS}h).")

        # Subscriber count and views/subscriber ratio
        latest_c_metrics = latest_channel_metrics if latest_channel_metrics is not None else (
            self.repository.get_latest_channel_metrics(channel_id) if channel_id else None
        )
        subscriber_count = latest_c_metrics.get("subscriber_count") if latest_c_metrics else None

        is_small_channel = None
        views_to_subscribers_ratio = None

        if subscriber_count is not None:
            is_small_channel = (subscriber_count <= cfg.SMALL_CHANNEL_SUBSCRIBERS_MAX)
            if subscriber_count == 0:
                warnings.append("Subscriber count is 0; views_to_subscribers_ratio set to None.")
            elif video_views is not None:
                views_to_subscribers_ratio = round(video_views / subscriber_count, 4)
        else:
            warnings.append("Subscriber count is hidden or unavailable; is_small_channel set to None.")

        # Outlier Classifications
        is_strong = (outlier_ratio is not None and outlier_ratio >= cfg.OUTLIER_STRONG_MIN)
        is_major = (outlier_ratio is not None and outlier_ratio >= cfg.OUTLIER_MAJOR_MIN)
        is_extreme = (outlier_ratio is not None and outlier_ratio >= cfg.OUTLIER_EXTREME_MIN)

        small_channel_outlier = bool(
            is_small_channel is True and
            (is_strong or is_major or is_extreme)
        )

        if baseline_count < 3:
            warnings.append(f"Insufficient baseline video count ({baseline_count} videos).")

        # Calculate Confidence (0 - 100)
        confidence = self._calculate_confidence(
            baseline_count=baseline_count,
            video_views=video_views,
            video_age_days=target_metrics.video_age_days,
            snapshot_count=target_metrics.snapshot_count,
            subscriber_count=subscriber_count
        )

        # Calculate Outlier Rank Score
        rank_score = self._calculate_rank_score(
            outlier_ratio=outlier_ratio,
            age_normalized_ratio=age_normalized_ratio,
            is_small_channel=is_small_channel,
            velocity_ratio=velocity_ratio,
            confidence=confidence
        )

        return VideoOutlierResult(
            video_id=video_id,
            channel_id=channel_id,
            video_title=video_title,
            channel_title=channel_title,
            video_views=video_views,
            channel_median_views=ch_median_views,
            channel_mean_views=ch_mean_views,
            channel_median_views_per_day=ch_median_per_day,
            baseline_video_count=baseline_count,
            baseline_confidence=confidence_cat,
            outlier_ratio=outlier_ratio,
            age_normalized_outlier_ratio=age_normalized_ratio,
            latest_velocity=latest_velocity,
            velocity_ratio=velocity_ratio,
            latest_acceleration=latest_acceleration,
            subscriber_count=subscriber_count,
            views_to_subscribers_ratio=views_to_subscribers_ratio,
            is_small_channel=is_small_channel,
            is_strong_outlier=is_strong,
            is_major_outlier=is_major,
            is_extreme_outlier=is_extreme,
            small_channel_outlier=small_channel_outlier,
            confidence=confidence,
            outlier_rank_score=rank_score,
            warnings=warnings,
        )

    def _calculate_confidence(
        self,
        baseline_count: int,
        video_views: Optional[int],
        video_age_days: Optional[float],
        snapshot_count: int,
        subscriber_count: Optional[int]
    ) -> float:
        """
        Calculates a simple 0-100 statistical confidence score based on data completeness and sample sizes.
        """
        score = 0.0

        # 1. Baseline sample size (max 40 pts)
        if baseline_count >= 10:
            score += 40.0
        elif baseline_count >= 5:
            score += 30.0
        elif baseline_count >= 3:
            score += 20.0
        elif baseline_count >= 1:
            score += 10.0

        # 2. Availability of views and metadata (max 20 pts)
        if video_views is not None and video_views > 0:
            score += 20.0

        # 3. Video age stability (max 15 pts) - extremely recent videos (<1h) are volatile
        if video_age_days is not None:
            age_hours = video_age_days * 24.0
            if age_hours >= 24.0:
                score += 15.0
            elif age_hours >= 1.0:
                score += 10.0
            else:
                score += 5.0

        # 4. Historical snapshots (max 15 pts)
        if snapshot_count >= 3:
            score += 15.0
        elif snapshot_count >= 2:
            score += 10.0
        elif snapshot_count >= 1:
            score += 5.0

        # 5. Subscriber visibility (max 10 pts)
        if subscriber_count is not None:
            score += 10.0

        return round(min(100.0, score), 2)

    def _calculate_rank_score(
        self,
        outlier_ratio: Optional[float],
        age_normalized_ratio: Optional[float],
        is_small_channel: Optional[bool],
        velocity_ratio: Optional[float],
        confidence: float
    ) -> float:
        """
        Calculates explicit OutlierRankScore for ordering anomalies.
        Formula combines ratios, small channel boost, velocity ratio, and confidence.
        """
        score = 0.0

        # Outlier ratio component (35%)
        if outlier_ratio is not None:
            # Cap at 50X for linear scaling in rank score
            ratio_scaled = min(outlier_ratio, 50.0)
            score += ratio_scaled * cfg.RANK_WEIGHT_OUTLIER_RATIO * 2.0

        # Age normalized ratio component (30%)
        if age_normalized_ratio is not None:
            age_scaled = min(age_normalized_ratio, 50.0)
            score += age_scaled * cfg.RANK_WEIGHT_AGE_NORMALIZED_RATIO * 2.0

        # Small channel signal boost (15%)
        if is_small_channel is True:
            score += 15.0 * cfg.RANK_WEIGHT_SMALL_CHANNEL

        # Velocity ratio component (10%)
        if velocity_ratio is not None and velocity_ratio > 0:
            vel_scaled = min(velocity_ratio, 20.0)
            score += vel_scaled * cfg.RANK_WEIGHT_VELOCITY * 0.5

        # Confidence component (10%)
        score += (confidence / 100.0) * (100.0 * cfg.RANK_WEIGHT_CONFIDENCE)

        return round(score, 4)
