"""Sprint 8 production feasibility and risk analysis."""
from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.config.production_risk_config import ProductionRiskConfig, production_risk_config
from app.models.production_risk import (
    ClusterProductionRisk,
    ProductionComplexity,
    RiskLevel,
    Sprint8AnalysisResult,
    Sprint8QualityMetrics,
)

_RESEARCH_TERMS = {
    "analysis", "case study", "documentary", "explained", "facts", "history",
    "investigation", "science", "research", "review", "tutorial", "why",
}
_FOOTAGE_TERMS = {
    "anime", "celebrity", "clip", "clips", "film", "football", "gameplay",
    "highlights", "movie", "music", "reaction", "recap", "sports", "trailer",
}
_EDITING_TERMS = {
    "animation", "cinematic", "compilation", "documentary", "explained",
    "highlights", "montage", "reaction", "recap", "top 10", "visualization",
}
_COPYRIGHT_TERMS = {
    "anime", "clip", "clips", "film", "football", "highlights", "movie",
    "music", "reaction", "recap", "song", "sports", "trailer",
}
_REUSED_TERMS = {"clip", "clips", "compilation", "highlights", "reaction", "recap", "reupload"}
_SENSITIVE_TERMS = {
    "alcohol", "crime", "drug", "finance", "financial", "gambling", "gun",
    "health", "legal", "medical", "politics", "suicide", "violence", "war", "weapon",
}
_WORDS = re.compile(r"[^\W_]+", re.UNICODE)


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator * 100.0 / denominator, 4) if denominator else None


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _matches(text: str, terms: set[str]) -> List[str]:
    padded = f" {' '.join(_WORDS.findall(text.lower()))} "
    return sorted(term for term in terms if f" {term} " in padded)


class ProductionRiskEngine:
    """Estimate production effort and policy risk from observable cluster metadata."""

    def __init__(self, config: Optional[ProductionRiskConfig] = None):
        self.config = config or production_risk_config

    def analyze(
        self,
        videos: Sequence[Mapping[str, Any]],
        clusters: Sequence[Mapping[str, Any]],
        source_market_structure_run_id: Optional[str] = None,
        source_cluster_run_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
    ) -> Sprint8AnalysisResult:
        now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        videos_by_id = {str(video.get("video_id") or ""): video for video in videos}
        aggregates = [self._analyze_cluster(cluster, videos_by_id) for cluster in clusters]
        total = len(videos)
        quality = Sprint8QualityMetrics(
            total_videos=total,
            total_clusters=len(aggregates),
            title_unknown_rate=_rate(sum(not str(v.get("title") or "").strip() for v in videos), total) or 0.0,
            description_unknown_rate=_rate(sum(not str(v.get("description") or "").strip() for v in videos), total) or 0.0,
            duration_unknown_rate=_rate(sum(_number(v.get("duration_seconds")) is None for v in videos), total) or 0.0,
            clusters_without_risk_evidence=sum(item.overall_risk_score is None for item in aggregates),
        )
        return Sprint8AnalysisResult(
            run_id=f"sprint8-{uuid.uuid4()}",
            source_market_structure_run_id=source_market_structure_run_id,
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
    ) -> ClusterProductionRisk:
        video_ids = [str(item) for item in cluster.get("video_ids") or []]
        members = [videos_by_id[video_id] for video_id in video_ids if video_id in videos_by_id]
        warnings: List[str] = []
        observed_fields = ["cluster video membership"]
        inferred_fields: List[str] = []
        assumptions = [
            "Scores are metadata-based feasibility estimates, not quoted labor or monetary costs.",
            "Text signals indicate potential production requirements and policy exposure, not confirmed use.",
        ]

        texts = [
            " ".join((str(video.get("title") or ""), str(video.get("description") or ""))).strip()
            for video in members
        ]
        known_texts = [text for text in texts if text]
        durations = [_number(video.get("duration_seconds")) for video in members]
        known_durations = [value for value in durations if value is not None]
        if known_texts:
            observed_fields.append("video titles/descriptions")
        else:
            warnings.append("Titles and descriptions unavailable; textual complexity and risk are UNKNOWN.")
        if known_durations:
            observed_fields.append("video durations")
        else:
            warnings.append("Durations unavailable; hours use the configured output-length assumption.")

        def signal_score(terms: set[str]) -> tuple[Optional[float], List[str], int]:
            if not known_texts:
                return None, [], 0
            matches = [_matches(text, terms) for text in known_texts]
            matched_videos = sum(bool(item) for item in matches)
            found = sorted({term for item in matches for term in item})
            return _bounded(matched_videos * 100.0 / len(known_texts)), found, matched_videos

        research, research_terms, research_videos = signal_score(_RESEARCH_TERMS)
        footage, footage_terms, footage_videos = signal_score(_FOOTAGE_TERMS)
        editing_text, editing_terms, editing_videos = signal_score(_EDITING_TERMS)
        copyright_risk, copyright_terms, copyright_videos = signal_score(_COPYRIGHT_TERMS)
        reused_risk, reused_terms, reused_videos = signal_score(_REUSED_TERMS)
        sensitive_risk, sensitive_terms, sensitive_videos = signal_score(_SENSITIVE_TERMS)

        median_minutes = median(known_durations) / 60.0 if known_durations else None
        duration_component = min(100.0, (median_minutes or 0.0) / 20.0 * 100.0) if known_durations else None
        editing_components = [value for value in (editing_text, duration_component) if value is not None]
        editing = _bounded(mean(editing_components)) if editing_components else None
        production_components = [
            (research, self.config.cost_weight_research),
            (footage, self.config.cost_weight_footage),
            (editing, self.config.cost_weight_editing),
        ]
        known_production = [(value, weight) for value, weight in production_components if value is not None]
        if known_production:
            production_cost = _bounded(
                sum(value * weight for value, weight in known_production)
                / sum(weight for _, weight in known_production)
            )
            if production_cost >= self.config.high_complexity_min:
                complexity = ProductionComplexity.HIGH
            elif production_cost >= self.config.medium_complexity_min:
                complexity = ProductionComplexity.MEDIUM
            else:
                complexity = ProductionComplexity.LOW
            inferred_fields.extend([
                "research_complexity_score", "footage_complexity_score",
                "editing_complexity_score", "production_cost_score", "estimated_hours",
            ])
        else:
            production_cost = 0.0
            complexity = ProductionComplexity.UNKNOWN

        output_minutes = median_minutes or self.config.default_output_minutes
        effort_factor = 0.5 + production_cost / 100.0
        hours_low = round(max(self.config.minimum_hours_low, output_minutes * self.config.hours_per_output_minute_low * effort_factor), 1)
        hours_high = round(max(self.config.minimum_hours_high, output_minutes * self.config.hours_per_output_minute_high * effort_factor), 1)

        risk_components = [
            (copyright_risk, self.config.risk_weight_copyright),
            (reused_risk, self.config.risk_weight_reused_content),
            (sensitive_risk, self.config.risk_weight_regulatory_sensitive),
        ]
        known_risks = [(value, weight) for value, weight in risk_components if value is not None]
        if known_risks:
            overall_risk = _bounded(
                sum(value * weight for value, weight in known_risks)
                / sum(weight for _, weight in known_risks)
            )
            if overall_risk >= self.config.high_risk_min:
                risk_level = RiskLevel.HIGH
            elif overall_risk >= self.config.medium_risk_min:
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW
            inferred_fields.extend([
                "copyright_risk_score", "reused_content_risk_score",
                "regulatory_sensitive_risk_score", "overall_risk_score",
            ])
        else:
            overall_risk = None
            risk_level = RiskLevel.UNKNOWN

        completeness = mean([
            len(known_texts) / len(members) if members else 0.0,
            len(known_durations) / len(members) if members else 0.0,
        ])
        sample_factor = min(1.0, len(members) / self.config.minimum_cluster_sample)
        confidence = _bounded(100.0 * completeness * (0.5 + 0.5 * sample_factor))
        if len(members) < self.config.minimum_cluster_sample:
            warnings.append("Small cluster sample reduces confidence.")
        if len(members) != len(video_ids):
            warnings.append("Some cluster video IDs were absent from the supplied dataset.")

        return ClusterProductionRisk(
            cluster_id=int(cluster.get("cluster_id", 0)),
            niche=str(cluster.get("niche") or ""),
            subniche=str(cluster.get("subniche") or ""),
            microniche=str(cluster.get("microniche") or ""),
            video_count=len(members),
            production_cost_score=production_cost,
            estimated_hours_low=hours_low,
            estimated_hours_high=hours_high,
            research_complexity_score=research,
            footage_complexity_score=footage,
            editing_complexity_score=editing,
            production_complexity=complexity,
            copyright_risk_score=copyright_risk,
            reused_content_risk_score=reused_risk,
            regulatory_sensitive_risk_score=sensitive_risk,
            overall_risk_score=overall_risk,
            risk_level=risk_level,
            confidence=confidence,
            observed_fields=observed_fields,
            inferred_fields=inferred_fields,
            assumptions=assumptions,
            evidence={
                "known_text_count": len(known_texts),
                "known_duration_count": len(known_durations),
                "median_duration_minutes": round(median_minutes, 2) if median_minutes is not None else None,
                "research": {"matched_videos": research_videos, "terms": research_terms},
                "footage": {"matched_videos": footage_videos, "terms": footage_terms},
                "editing": {"matched_videos": editing_videos, "terms": editing_terms},
                "copyright": {"matched_videos": copyright_videos, "terms": copyright_terms},
                "reused_content": {"matched_videos": reused_videos, "terms": reused_terms},
                "regulatory_sensitive": {"matched_videos": sensitive_videos, "terms": sensitive_terms},
            },
            warnings=warnings,
        )
