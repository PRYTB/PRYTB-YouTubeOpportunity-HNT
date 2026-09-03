"""Sprint 6 revenue and geography analysis.

All monetary ranges come only from a benchmark provider. With the default empty
provider, monetary signals remain unavailable. AudienceEconomicValue is a
comparative indicator, not revenue and not an Opportunity Score.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from statistics import mean
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.analytics.benchmark_provider import (
    EmptyBenchmarkProvider,
    RevenueBenchmarkProvider,
)
from app.models.geography import (
    AudienceEconomicValue,
    ClusterRevenueAggregate,
    ContentType,
    DataQualityMetrics,
    GeoSource,
    LanguageCode,
    LanguageDetectionResult,
    MarketTier,
    RevenueEstimate,
    Sprint6AnalysisResult,
    VideoGeographyEstimate,
    VideoRevenueAnalysis,
)
from config.market_tiers import get_best_available_tier

SHORT_MAX_SECONDS = 180

_LANGUAGE_WORDS = {
    LanguageCode.EN: {"the", "and", "how", "what", "why", "with", "for", "this", "your", "guide", "tutorial", "best", "new"},
    LanguageCode.ES: {"el", "la", "los", "las", "de", "para", "como", "qué", "por", "con", "una", "guía", "tutorial"},
    LanguageCode.PT: {"o", "a", "os", "as", "de", "para", "como", "que", "por", "com", "uma", "guia", "você"},
    LanguageCode.FR: {"le", "la", "les", "de", "des", "pour", "comment", "avec", "une", "guide", "votre", "est"},
    LanguageCode.DE: {"der", "die", "das", "und", "für", "wie", "mit", "ein", "eine", "ist", "was", "warum"},
}
_LANGUAGE_HINTS = {
    LanguageCode.ES: re.compile(r"[ñ¿¡]|\b(qué|cómo|vídeo|también|español)\b", re.I),
    LanguageCode.PT: re.compile(r"[ãõç]|\b(você|não|português|também)\b", re.I),
    LanguageCode.FR: re.compile(r"[àâçéèêëîïôûùüÿœ]|\b(français|très)\b", re.I),
    LanguageCode.DE: re.compile(r"[äöüß]|\b(deutsch|für|über)\b", re.I),
}
_METADATA_CODES = {code.value: code for code in LanguageCode if code not in {LanguageCode.OTHER, LanguageCode.UNKNOWN}}

_COUNTRY_PATTERNS: Dict[str, re.Pattern[str]] = {
    "US": re.compile(r"\b(united states|u\.?s\.?a?\.?|america)\b|\$\s?\d", re.I),
    "GB": re.compile(r"\b(united kingdom|u\.?k\.?|britain|england)\b|£\s?\d", re.I),
    "CA": re.compile(r"\bcanada|canadian\b|\bCAD\s?\d", re.I),
    "AU": re.compile(r"\baustralia|australian\b|\bAUD\s?\d", re.I),
    "DE": re.compile(r"\bgermany|deutschland\b", re.I),
    "FR": re.compile(r"\bfrance|français\b", re.I),
    "ES": re.compile(r"\bspain|españa\b", re.I),
    "MX": re.compile(r"\bmexico|méxico|mexican[oa]?\b", re.I),
    "BR": re.compile(r"\bbrazil|brasil|brasileir[oa]\b|R\$\s?\d", re.I),
    "CL": re.compile(r"\bchile|chileno|chilena\b", re.I),
    "AR": re.compile(r"\bargentina|argentin[oa]\b", re.I),
    "CO": re.compile(r"\bcolombia|colombian[oa]\b", re.I),
    "PE": re.compile(r"\bperu|perú|peruan[oa]\b", re.I),
    "PT": re.compile(r"\bportugal|português\b", re.I),
}
_REGION_BY_COUNTRY = {
    "US": "North America", "CA": "North America", "GB": "Western Europe",
    "DE": "Western Europe", "FR": "Western Europe", "ES": "Southern Europe",
    "PT": "Southern Europe", "AU": "Australia/NZ", "MX": "Latin America",
    "BR": "Latin America", "CL": "Latin America", "AR": "Latin America",
    "CO": "Latin America", "PE": "Latin America",
}
_LANGUAGE_MARKETS = {
    LanguageCode.EN: "English-language markets",
    LanguageCode.ES: "Spanish-language markets",
    LanguageCode.PT: "Portuguese-language markets",
    LanguageCode.FR: "French-language markets",
    LanguageCode.DE: "German-language markets",
}
_TIER_BASE = {MarketTier.TIER_A: 80, MarketTier.TIER_B: 60, MarketTier.TIER_C: 40, MarketTier.UNKNOWN: 25}


def detect_language(
    title: Optional[str], description: Optional[str] = None,
    metadata_language: Optional[str] = None, audio_language: Optional[str] = None,
) -> LanguageDetectionResult:
    """Detect language deterministically, preferring explicit YouTube metadata."""
    for raw in (audio_language, metadata_language):
        code = str(raw or "").lower().split("-")[0]
        if code in _METADATA_CODES:
            return LanguageDetectionResult(
                language_code=_METADATA_CODES[code], confidence=95.0,
                source=GeoSource.CHANNEL_METADATA, details={"metadata_code": raw},
            )

    text = " ".join(part for part in (title or "", description or "") if part).strip()
    words = re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)
    if len(words) < 3:
        return LanguageDetectionResult(details={"reason": "insufficient_text", "word_count": len(words)})

    scores = {language: sum(word in vocabulary for word in words) for language, vocabulary in _LANGUAGE_WORDS.items()}
    for language, pattern in _LANGUAGE_HINTS.items():
        if pattern.search(text):
            scores[language] += 2
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_language, best_score = ranked[0]
    second_score = ranked[1][1]
    if best_score == 0:
        return LanguageDetectionResult(
            language_code=LanguageCode.OTHER if len(words) >= 8 else LanguageCode.UNKNOWN,
            confidence=35.0 if len(words) >= 8 else 0.0,
            source=GeoSource.TITLE_DESCRIPTION_INFERENCE if len(words) >= 8 else GeoSource.UNKNOWN,
            details={"scores": {key.value: value for key, value in scores.items()}},
        )
    margin = best_score - second_score
    confidence = min(90.0, 50.0 + best_score * 8.0 + margin * 5.0)
    if margin == 0:
        return LanguageDetectionResult(
            language_code=LanguageCode.UNKNOWN, confidence=25.0,
            source=GeoSource.TITLE_DESCRIPTION_INFERENCE,
            details={"reason": "mixed_or_ambiguous", "scores": {key.value: value for key, value in scores.items()}},
        )
    return LanguageDetectionResult(
        language_code=best_language, confidence=round(confidence, 1),
        source=GeoSource.TITLE_DESCRIPTION_INFERENCE,
        details={"scores": {key.value: value for key, value in scores.items()}},
    )


def classify_content_type(duration_seconds: Any, short_max_seconds: int = SHORT_MAX_SECONDS) -> ContentType:
    """Classify only from YouTube duration metadata; title and URL are ignored."""
    if duration_seconds is None or isinstance(duration_seconds, bool):
        return ContentType.UNKNOWN
    try:
        duration = int(duration_seconds)
    except (TypeError, ValueError):
        return ContentType.UNKNOWN
    if duration <= 0:
        return ContentType.UNKNOWN
    return ContentType.SHORT if duration <= short_max_seconds else ContentType.LONG_FORM


def estimate_geography(video: Mapping[str, Any], channel: Optional[Mapping[str, Any]] = None) -> VideoGeographyEstimate:
    """Estimate audience market without treating channel origin as audience country."""
    language = detect_language(
        video.get("title"), video.get("description"),
        video.get("default_language"), video.get("default_audio_language"),
    )
    channel_country = str((channel or {}).get("country") or "").upper() or None
    observed = ["channel_origin_country"] if channel_country else []
    text = f"{video.get('title') or ''} {video.get('description') or ''}"
    signals = [country for country, pattern in _COUNTRY_PATTERNS.items() if pattern.search(text)]
    warnings: List[str] = []

    if len(signals) == 1:
        country = signals[0]
        source = GeoSource.TITLE_DESCRIPTION_INFERENCE
        geo_confidence = 65.0
        audience_market = country
        inferred = ["estimated_audience_market", "primary_country", "region_group"]
    else:
        country = None
        source = GeoSource.LANGUAGE_INFERENCE if language.language_code in _LANGUAGE_MARKETS else GeoSource.UNKNOWN
        geo_confidence = min(40.0, language.confidence * 0.4) if source != GeoSource.UNKNOWN else 0.0
        audience_market = _LANGUAGE_MARKETS.get(language.language_code)
        inferred = ["estimated_audience_market"] if audience_market else []
        if len(signals) > 1:
            warnings.append("Conflicting audience country signals; primary country remains UNKNOWN.")
    if country is None:
        warnings.append("Audience country unavailable; channel origin was not used as audience country.")
    if not channel_country:
        warnings.append("Channel origin country unavailable.")

    overall = round(0.6 * geo_confidence + 0.4 * language.confidence, 1)
    return VideoGeographyEstimate(
        video_id=str(video.get("video_id") or ""), primary_language=language.language_code,
        language_confidence=language.confidence, language_source=language.source,
        channel_origin_country=channel_country, country_signals=signals,
        estimated_audience_market=audience_market, primary_country=country,
        primary_country_confidence=geo_confidence if country else 0.0,
        region_group=_REGION_BY_COUNTRY.get(country), geo_source=source,
        observed_fields=observed, inferred_fields=inferred, confidence=overall, warnings=warnings,
    )


class RevenueGeographyEngine:
    """Analyze videos and aggregate their comparative signals by Sprint 5 cluster."""

    def __init__(self, benchmark_provider: Optional[RevenueBenchmarkProvider] = None, short_max_seconds: int = SHORT_MAX_SECONDS):
        self.benchmark_provider = benchmark_provider or EmptyBenchmarkProvider()
        self.short_max_seconds = short_max_seconds

    def analyze_video(self, video: Mapping[str, Any], channel: Optional[Mapping[str, Any]] = None) -> VideoRevenueAnalysis:
        geography = estimate_geography(video, channel)
        content_type = classify_content_type(video.get("duration_seconds"), self.short_max_seconds)
        tier = get_best_available_tier(
            country_code=geography.primary_country,
            region_group=geography.region_group,
            language_code=geography.primary_language.value,
        )
        lookup_market = geography.primary_country or tier.value
        benchmark = None if content_type == ContentType.UNKNOWN else self.benchmark_provider.get_benchmark(lookup_market, content_type)
        assumptions = ["Market tier is a configurable relative-attractiveness grouping, not revenue truth."]
        warnings = []
        if benchmark is None:
            warnings.append("Revenue benchmark unavailable; monetary signals are unavailable.")
        if content_type == ContentType.UNKNOWN:
            warnings.append("Content type unavailable because duration metadata is missing or invalid.")

        geo_component = geography.confidence
        language_component = geography.language_confidence
        format_component = 100.0 if content_type != ContentType.UNKNOWN else 0.0
        benchmark_component = benchmark.confidence if benchmark else 0.0
        confidence = round(
            geo_component * 0.4 + language_component * 0.2 + format_component * 0.2 + benchmark_component * 0.2,
            1,
        )
        revenue = RevenueEstimate(
            video_id=geography.video_id, content_type=content_type, estimated_market_tier=tier,
            revenue_signal_low=benchmark.value_low if benchmark else None,
            revenue_signal_mid=benchmark.value_mid if benchmark else None,
            revenue_signal_high=benchmark.value_high if benchmark else None,
            currency=benchmark.currency if benchmark else "USD",
            method="documented_benchmark" if benchmark else "unavailable",
            confidence=confidence, assumptions=assumptions, warnings=warnings,
            benchmark_source_type=benchmark.source_type if benchmark else None,
            benchmark_source_name=benchmark.source_name if benchmark else None,
            benchmark_confidence=benchmark.confidence if benchmark else None,
        )
        value = _TIER_BASE[tier]
        value += 5 if content_type == ContentType.LONG_FORM else -5 if content_type == ContentType.SHORT else -10
        value += 5 if geography.primary_language not in {LanguageCode.UNKNOWN, LanguageCode.OTHER} else 0
        value += 10 if benchmark else 0
        value = float(max(0, min(100, round(value / 5) * 5)))
        economic = AudienceEconomicValue(
            video_id=geography.video_id, value=value, confidence=confidence,
            inputs={"market_tier": tier.value, "language": geography.primary_language.value,
                    "content_type": content_type.value, "benchmark_available": benchmark is not None},
            warnings=list(warnings),
        )
        return VideoRevenueAnalysis(
            video_id=geography.video_id, title=str(video.get("title") or ""),
            geography=geography, revenue=revenue, economic_value=economic,
        )

    def analyze(
        self, videos: Sequence[Mapping[str, Any]], channels: Sequence[Mapping[str, Any]],
        clusters: Sequence[Mapping[str, Any]], source_cluster_run_id: Optional[str] = None,
    ) -> Sprint6AnalysisResult:
        channels_by_id = {str(item.get("channel_id")): item for item in channels}
        analyses = [self.analyze_video(video, channels_by_id.get(str(video.get("channel_id")))) for video in videos]
        by_video = {item.video_id: item for item in analyses}
        aggregates = [self._aggregate_cluster(cluster, by_video) for cluster in clusters]
        total = len(analyses)
        unknown_languages = sum(item.geography.primary_language == LanguageCode.UNKNOWN for item in analyses)
        unknown_geo = sum(item.geography.primary_country is None for item in analyses)
        unknown_format = sum(item.revenue.content_type == ContentType.UNKNOWN for item in analyses)
        missing_benchmark = sum(item.revenue.revenue_signal_mid is None for item in analyses)
        rate = lambda count: round(count * 100.0 / total, 1) if total else 0.0
        quality = DataQualityMetrics(
            language_unknown_rate=rate(unknown_languages), geo_unknown_rate=rate(unknown_geo),
            content_type_unknown_rate=rate(unknown_format), benchmark_missing_rate=rate(missing_benchmark),
            total_videos=total, total_clusters=len(aggregates),
        )
        return Sprint6AnalysisResult(
            run_id=f"sprint6-{uuid.uuid4()}", source_cluster_run_id=source_cluster_run_id,
            videos=analyses, clusters=aggregates, quality=quality,
        )

    @staticmethod
    def _aggregate_cluster(cluster: Mapping[str, Any], by_video: Mapping[str, VideoRevenueAnalysis]) -> ClusterRevenueAggregate:
        video_ids = list(cluster.get("video_ids") or [])
        members = [by_video[video_id] for video_id in video_ids if video_id in by_video]
        languages = Counter(item.geography.primary_language.value for item in members)
        markets = Counter(item.geography.primary_country or "UNKNOWN" for item in members)
        tiers = Counter(item.revenue.estimated_market_tier.value for item in members)
        formats = Counter(item.revenue.content_type for item in members)
        benchmark_count = sum(item.revenue.revenue_signal_mid is not None for item in members)
        warnings: List[str] = []
        unknown_geo_rate = markets.get("UNKNOWN", 0) / len(members) if members else 1.0
        if unknown_geo_rate > 0.5:
            markets = Counter({"UNKNOWN": len(members)})
            warnings.append("Country distribution suppressed because most audience countries are UNKNOWN.")
        if len(members) < 5:
            warnings.append("Small cluster sample reduces confidence.")
        if benchmark_count == 0:
            warnings.append("No revenue benchmarks available for cluster members.")
        dominant = LanguageCode(languages.most_common(1)[0][0]) if languages else LanguageCode.UNKNOWN
        average_value = round(mean(item.economic_value.value for item in members) / 5) * 5 if members else 0.0
        average_confidence = mean(item.economic_value.confidence for item in members) if members else 0.0
        sample_factor = min(1.0, len(members) / 10.0)
        unknown_factor = 1.0 - 0.5 * unknown_geo_rate
        cluster_confidence = round(average_confidence * (0.5 + 0.5 * sample_factor) * unknown_factor, 1)
        return ClusterRevenueAggregate(
            cluster_id=int(cluster.get("cluster_id", 0)), video_count=len(members),
            language_distribution=dict(languages), dominant_language=dominant,
            estimated_market_distribution=dict(markets), market_tier_distribution=dict(tiers),
            long_form_count=formats.get(ContentType.LONG_FORM, 0), short_count=formats.get(ContentType.SHORT, 0),
            unknown_format_count=formats.get(ContentType.UNKNOWN, 0),
            benchmark_coverage=round(benchmark_count * 100.0 / len(members), 1) if members else 0.0,
            audience_economic_value=float(average_value), revenue_confidence=cluster_confidence, warnings=warnings,
        )
