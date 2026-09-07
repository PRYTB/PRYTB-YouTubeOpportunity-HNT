"""Sprint 7 competition, accessibility, depth, formats, and longevity analysis."""
from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.analytics.revenue_geography_engine import classify_content_type
from app.config.market_structure_config import MarketStructureConfig, market_structure_config
from app.models.geography import ContentType
from app.models.market_structure import (
    ClusterMarketStructure,
    ContentAtom,
    ContentDepthBand,
    EntryAccessibility,
    EvergreenClass,
    MarketStructureClass,
    Sprint7AnalysisResult,
    Sprint7QualityMetrics,
)
from app.models.outliers import VideoOutlierResult

_WORD_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "de", "del", "el", "en", "for", "how",
    "la", "las", "los", "of", "on", "para", "por", "que", "the", "to", "un", "una",
    "with", "y", "your",
}


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_days(value: Any, as_of: datetime) -> Optional[float]:
    parsed = _datetime(value)
    if parsed is None or parsed > as_of:
        return None
    return (as_of - parsed).total_seconds() / 86400.0


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator * 100.0 / denominator, 4) if denominator else None


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _title_signature(title: Any) -> str:
    words = [
        word for word in _WORD_PATTERN.findall(str(title or "").lower())
        if word not in _STOP_WORDS
    ]
    return " ".join(words[:3])


def _weighted_known(components: Sequence[tuple[Optional[float], float]]) -> float:
    known = [(value, weight) for value, weight in components if value is not None]
    weight_sum = sum(weight for _, weight in known)
    if not weight_sum:
        return 0.0
    return _bounded(sum(value * weight for value, weight in known) / weight_sum)


class MarketStructureEngine:
    """Aggregate observed Sprint 4–6 evidence by approved Sprint 5 cluster."""

    def __init__(self, config: Optional[MarketStructureConfig] = None):
        self.config = config or market_structure_config

    def analyze(
        self,
        videos: Sequence[Mapping[str, Any]],
        channels: Sequence[Mapping[str, Any]],
        clusters: Sequence[Mapping[str, Any]],
        source_cluster_run_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
        outlier_results: Sequence[VideoOutlierResult | Mapping[str, Any]] = (),
    ) -> Sprint7AnalysisResult:
        now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        channels_by_id = {str(item.get("channel_id") or ""): item for item in channels}
        videos_by_id = {str(item.get("video_id") or ""): item for item in videos}
        outliers_by_id: Dict[str, VideoOutlierResult] = {}
        for item in outlier_results:
            result = item if isinstance(item, VideoOutlierResult) else VideoOutlierResult.model_validate(item)
            if result.video_id in outliers_by_id:
                raise ValueError(f"Duplicate Sprint 4 outlier result for video {result.video_id}.")
            outliers_by_id[result.video_id] = result

        aggregates = [
            self._analyze_cluster(cluster, videos_by_id, channels_by_id, outliers_by_id, now)
            for cluster in clusters
        ]
        ranked = sorted(
            aggregates,
            key=lambda item: (-item.market_structure_score, -item.confidence, item.cluster_id),
        )
        rank_by_cluster = {item.cluster_id: rank for rank, item in enumerate(ranked[:5], 1)}
        aggregates = [
            item.model_copy(update={"top_5_rank": rank_by_cluster.get(item.cluster_id)})
            for item in aggregates
        ]

        total = len(videos)
        video_channel_ids = {str(video.get("channel_id") or "") for video in videos}
        relevant_channels = [
            channels_by_id[channel_id] for channel_id in video_channel_ids
            if channel_id in channels_by_id
        ]
        quality = Sprint7QualityMetrics(
            total_videos=total,
            total_clusters=len(aggregates),
            subscriber_unknown_rate=_rate(
                sum(_number(channel.get("subscriber_count")) is None for channel in relevant_channels),
                len(relevant_channels),
            ) or 0.0,
            views_unknown_rate=_rate(
                sum(_number(video.get("view_count")) is None for video in videos), total
            ) or 0.0,
            publication_date_unknown_rate=_rate(
                sum(_age_days(video.get("published_at"), now) is None for video in videos), total
            ) or 0.0,
            duration_unknown_rate=_rate(
                sum(classify_content_type(video.get("duration_seconds")) is ContentType.UNKNOWN for video in videos),
                total,
            ) or 0.0,
            outlier_unknown_rate=_rate(
                sum(str(video.get("video_id") or "") not in outliers_by_id for video in videos), total
            ) or 0.0,
            clusters_without_small_channel_sample=sum(
                item.small_channel_eligible_videos == 0 for item in aggregates
            ),
            clusters_without_microniche=sum(not item.microniche.strip() for item in aggregates),
            clusters_without_content_atoms=sum(not item.content_atoms for item in aggregates),
            clusters_without_temporal_evidence=sum(
                item.evergreen_class is EvergreenClass.UNKNOWN for item in aggregates
            ),
        )
        return Sprint7AnalysisResult(
            run_id=f"sprint7-{uuid.uuid4()}",
            source_cluster_run_id=source_cluster_run_id,
            analyzed_at=now.isoformat(),
            config=self.config.model_dump(),
            clusters=aggregates,
            quality=quality,
        )

    def _analyze_cluster(
        self,
        cluster: Mapping[str, Any],
        videos_by_id: Mapping[str, Mapping[str, Any]],
        channels_by_id: Mapping[str, Mapping[str, Any]],
        outliers_by_id: Mapping[str, VideoOutlierResult],
        as_of: datetime,
    ) -> ClusterMarketStructure:
        video_ids = [str(item) for item in cluster.get("video_ids") or []]
        members = [videos_by_id[video_id] for video_id in video_ids if video_id in videos_by_id]
        member_outliers = [outliers_by_id[video_id] for video_id in video_ids if video_id in outliers_by_id]
        channel_counts = Counter(
            str(video.get("channel_id") or "") for video in members if video.get("channel_id")
        )
        channel_ids = sorted(channel_counts)
        channel_records = [
            channels_by_id[channel_id] for channel_id in channel_ids if channel_id in channels_by_id
        ]
        warnings: List[str] = []
        assumptions = [
            "Sprint 4 outlier classifications and baselines are consumed without recalculation.",
            "Idea capacity is a conservative band estimate from observed titles and thematic atoms.",
            "Market Structure Score is structural, not profitability or expected revenue.",
        ]
        observed_fields = ["cluster video membership", "channel distribution"]
        inferred_fields = [
            "competition_score", "accessibility_score", "content_depth", "trend_score",
            "evergreen_class", "market_structure_score",
        ]

        count = len(members)
        channel_count = len(channel_ids)
        dominant_share = _rate(max(channel_counts.values()), count) if channel_counts and count else 0.0
        shares = [value / count for value in channel_counts.values()] if count else []
        hhi = round(sum(share * share for share in shares) * 100.0, 1)

        subscribers = [_number(channel.get("subscriber_count")) for channel in channel_records]
        known_subscribers = [value for value in subscribers if value is not None]
        average_subscribers = round(mean(known_subscribers), 1) if known_subscribers else None
        if known_subscribers:
            observed_fields.append("channel subscriber counts")
        else:
            warnings.append("Subscriber counts unavailable; channel-size evidence is limited.")

        channel_ages = [_age_days(channel.get("published_at"), as_of) for channel in channel_records]
        known_channel_ages = [value for value in channel_ages if value is not None]
        new_entrant_channels = sum(
            value <= self.config.new_channel_max_age_days for value in known_channel_ages
        )
        new_entrant_rate = _rate(new_entrant_channels, len(known_channel_ages))
        if known_channel_ages:
            observed_fields.append("channel publication dates")
        else:
            warnings.append("Channel age unavailable; new-entrant evidence is unknown.")

        eligible_outliers = [
            item for item in member_outliers
            if item.is_small_channel is True and item.outlier_ratio is not None
        ]
        successes = sum(item.small_channel_outlier for item in eligible_outliers)
        small_success_rate = _rate(successes, len(eligible_outliers))
        ratios = [item.outlier_ratio for item in member_outliers if item.outlier_ratio is not None]
        rank_scores = [item.outlier_rank_score for item in member_outliers]
        if member_outliers:
            observed_fields.append("Sprint 4 outlier results")
        if not eligible_outliers:
            warnings.append("No eligible small-channel videos in supplied Sprint 4 results.")
        if len(member_outliers) < count:
            warnings.append("Sprint 4 outlier results are unavailable for some cluster videos.")

        count_component = min(100.0, channel_count / 20.0 * 100.0)
        concentration_component = 0.6 * (dominant_share or 0.0) + 0.4 * hhi
        size_component = (
            min(100.0, math.log10(average_subscribers + 1.0) / 7.0 * 100.0)
            if average_subscribers is not None else 50.0
        )
        maturity_component = 100.0 - (new_entrant_rate if new_entrant_rate is not None else 50.0)
        competition_score = _bounded(
            count_component * self.config.competition_weight_channel_count
            + concentration_component * self.config.competition_weight_concentration
            + size_component * self.config.competition_weight_channel_size
            + maturity_component * self.config.competition_weight_maturity
        )
        accessibility_components = [
            (small_success_rate, self.config.accessibility_weight_small_success),
            (new_entrant_rate, self.config.accessibility_weight_new_entrants),
            (100.0 - concentration_component if channel_count else None,
             self.config.accessibility_weight_low_concentration),
        ]
        accessibility_score = _weighted_known(accessibility_components)
        accessibility_confidence = _bounded(100.0 * sum(
            weight for value, weight in accessibility_components if value is not None
        ))
        if not channel_count:
            accessibility = EntryAccessibility.UNKNOWN
        elif accessibility_score >= self.config.high_accessibility_min:
            accessibility = EntryAccessibility.HIGH
        elif accessibility_score >= self.config.medium_accessibility_min:
            accessibility = EntryAccessibility.MEDIUM
        else:
            accessibility = EntryAccessibility.LOW

        titles = {
            " ".join(str(video.get("title") or "").lower().split())
            for video in members if str(video.get("title") or "").strip()
        }
        signature_counts = Counter(
            signature for signature in (_title_signature(video.get("title")) for video in members)
            if signature
        )
        content_atoms = [
            ContentAtom(atom=atom, video_count=frequency)
            for atom, frequency in sorted(signature_counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        titled_video_count = sum(bool(str(video.get("title") or "").strip()) for video in members)
        topic_atom_count = len(signature_counts)
        # Conservative lower bound: number of distinct observed title signatures in evidence
        # An lower bound >= 100 requires at least 100 distinct observed title signatures in the cluster members.
        capacity_low = topic_atom_count if titled_video_count else None
        capacity_high = (
            max(capacity_low, topic_atom_count * self.config.idea_multiplier)
            if capacity_low is not None else None
        )
        near_duplicate_count = titled_video_count - topic_atom_count
        semantic_diversity = (
            round(topic_atom_count / titled_video_count, 4) if titled_video_count else None
        )
        depth_confidence = _bounded(
            100.0 * (semantic_diversity or 0.0)
            * min(1.0, titled_video_count / self.config.minimum_cluster_sample)
        )
        estimated_ideas = capacity_low
        if capacity_low is None:
            depth_band = ContentDepthBand.UNKNOWN
        elif capacity_low >= 100:
            depth_band, estimated_ideas = ContentDepthBand.IDEAS_100_PLUS, 100
        elif capacity_low >= 50:
            depth_band, estimated_ideas = ContentDepthBand.IDEAS_50_PLUS, 50
        elif capacity_low >= 20:
            depth_band, estimated_ideas = ContentDepthBand.IDEAS_20_PLUS, 20
        elif capacity_low < 20:
            depth_band = ContentDepthBand.BELOW_20
        else:
            depth_band = ContentDepthBand.UNDETERMINED
        depth_score = _bounded((capacity_low or 0) / 100.0 * 100.0)

        formats = Counter(classify_content_type(video.get("duration_seconds")) for video in members)
        format_facet_count = sum(
            bool(formats[content_type]) for content_type in (ContentType.SHORT, ContentType.LONG_FORM)
        )
        video_ages = [_age_days(video.get("published_at"), as_of) for video in members]
        known_video_ages = [value for value in video_ages if value is not None]
        recent_rate = _rate(
            sum(value <= self.config.recent_video_max_age_days for value in known_video_ages),
            len(known_video_ages),
        )
        mature_rate = _rate(
            sum(value >= self.config.mature_video_min_age_days for value in known_video_ages),
            len(known_video_ages),
        )
        span = round(max(known_video_ages) - min(known_video_ages), 1) if len(known_video_ages) >= 2 else None
        if not known_video_ages:
            warnings.append("Video publication dates unavailable; trend and evergreen are UNKNOWN.")
            trend_score, is_trend = None, None
            evergreen_class, evergreen_score = EvergreenClass.UNKNOWN, 0.0
        else:
            observed_fields.append("video publication dates")
            trend_score = _bounded(0.7 * (recent_rate or 0.0) + 0.3 * (100.0 - (mature_rate or 0.0)))
            is_trend = (
                (recent_rate or 0.0) >= self.config.trend_recent_rate_min
                and (mature_rate or 0.0) == 0
            )
            span_component = min(
                100.0, (span or 0.0) / self.config.evergreen_span_days_min * 100.0
            )
            evergreen_score = _bounded(0.6 * (mature_rate or 0.0) + 0.4 * span_component)
            if (mature_rate or 0.0) >= self.config.evergreen_mature_rate_min and (span or 0.0) >= self.config.evergreen_span_days_min:
                evergreen_class = EvergreenClass.EVERGREEN
            elif is_trend:
                evergreen_class = EvergreenClass.TREND
            else:
                evergreen_class = EvergreenClass.SEMI_EVERGREEN

        views = [_number(video.get("view_count")) for video in members]
        known_views = [value for value in views if value is not None]
        median_views = round(median(known_views), 1) if known_views else None
        if competition_score >= self.config.saturated_competition_min and median_views is not None and median_views >= self.config.viral_median_views_min:
            structure_class = MarketStructureClass.VIRAL_SATURATED
        elif depth_band is ContentDepthBand.BELOW_20:
            structure_class = MarketStructureClass.CONTENT_CONSTRAINED
        elif accessibility in {EntryAccessibility.HIGH, EntryAccessibility.MEDIUM} and evergreen_class not in {EvergreenClass.TREND, EvergreenClass.UNKNOWN}:
            structure_class = MarketStructureClass.SUSTAINABLE_ACCESSIBLE
        else:
            structure_class = MarketStructureClass.UNCERTAIN

        completeness = mean([
            len(known_subscribers) / channel_count if channel_count else 0.0,
            len(known_channel_ages) / channel_count if channel_count else 0.0,
            len(known_video_ages) / count if count else 0.0,
            len(known_views) / count if count else 0.0,
            len(member_outliers) / count if count else 0.0,
        ])
        sample_factor = min(1.0, count / self.config.minimum_cluster_sample)
        confidence = _bounded(
            100.0 * completeness * (0.5 + 0.5 * sample_factor)
            * (0.5 + 0.5 * accessibility_confidence / 100.0)
            * (0.5 + 0.5 * depth_confidence / 100.0)
        )
        market_structure_score = _bounded(
            0.35 * accessibility_score + 0.25 * depth_score
            + 0.20 * evergreen_score + 0.20 * (100.0 - competition_score)
        )
        if count < self.config.minimum_cluster_sample:
            warnings.append("Small cluster sample reduces confidence.")
        if len(members) != len(video_ids):
            warnings.append("Some cluster video IDs were absent from the supplied dataset.")

        return ClusterMarketStructure(
            cluster_id=int(cluster.get("cluster_id", 0)),
            niche=str(cluster.get("niche") or ""),
            subniche=str(cluster.get("subniche") or ""),
            microniche=str(cluster.get("microniche") or ""),
            summary=str(cluster.get("summary") or ""),
            market_structure_score=market_structure_score,
            video_count=count,
            channel_count=channel_count,
            channels_with_subscribers=len(known_subscribers),
            average_subscribers=average_subscribers,
            median_channel_age_days=round(median(known_channel_ages), 1) if known_channel_ages else None,
            new_entrant_channels=new_entrant_channels,
            new_entrant_rate=new_entrant_rate,
            dominant_channel_share=dominant_share or 0.0,
            channel_hhi=hhi,
            outlier_results_available=len(member_outliers),
            strong_outlier_count=sum(item.is_strong_outlier for item in member_outliers),
            major_outlier_count=sum(item.is_major_outlier for item in member_outliers),
            extreme_outlier_count=sum(item.is_extreme_outlier for item in member_outliers),
            small_channel_eligible_videos=len(eligible_outliers),
            small_channel_successes=successes,
            small_channel_success_rate=small_success_rate,
            median_outlier_ratio=round(median(ratios), 4) if ratios else None,
            max_outlier_ratio=round(max(ratios), 4) if ratios else None,
            average_outlier_rank_score=round(mean(rank_scores), 4) if rank_scores else None,
            competition_score=competition_score,
            accessibility_score=accessibility_score,
            accessibility_confidence=accessibility_confidence,
            accessibility=accessibility,
            distinct_title_count=len(titles),
            title_pattern_count=topic_atom_count,
            topic_atom_count=topic_atom_count,
            near_duplicate_count=near_duplicate_count,
            semantic_diversity=semantic_diversity,
            content_atoms=content_atoms,
            short_video_count=formats[ContentType.SHORT],
            long_form_video_count=formats[ContentType.LONG_FORM],
            unknown_format_count=formats[ContentType.UNKNOWN],
            format_facet_count=format_facet_count,
            observed_content_span_days=span,
            estimated_capacity_low=capacity_low,
            estimated_capacity_high=capacity_high,
            estimated_distinct_ideas=estimated_ideas,
            content_depth_score=depth_score,
            depth_confidence=depth_confidence,
            content_depth_band=depth_band,
            recent_video_rate=recent_rate,
            mature_video_rate=mature_rate,
            trend_score=trend_score,
            is_trend=is_trend,
            evergreen_score=evergreen_score,
            evergreen_class=evergreen_class,
            median_views=median_views,
            market_structure_class=structure_class,
            confidence=confidence,
            observed_fields=list(dict.fromkeys(observed_fields)),
            inferred_fields=inferred_fields,
            assumptions=assumptions,
            evidence={
                "channel_count_component": round(count_component, 1),
                "concentration_component": round(concentration_component, 1),
                "channel_size_component": round(size_component, 1),
                "maturity_component": round(maturity_component, 1),
                "content_capacity_low": capacity_low,
                "content_capacity_high": capacity_high,
                "market_structure_score_formula": {
                    "accessibility": 0.35,
                    "content_depth": 0.25,
                    "evergreen": 0.20,
                    "inverse_competition": 0.20,
                },
            },
            warnings=warnings,
        )
