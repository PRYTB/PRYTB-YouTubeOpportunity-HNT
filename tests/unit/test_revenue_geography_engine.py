"""Unit tests for the Sprint 6 revenue and geography engine."""

import pytest

from app.analytics.benchmark_provider import (
    ConfiguredBenchmarkProvider,
    EmptyBenchmarkProvider,
)
from app.analytics.revenue_geography_engine import (
    RevenueGeographyEngine,
    classify_content_type,
    detect_language,
    estimate_geography,
)
from app.models.geography import (
    BenchmarkSourceType,
    ContentType,
    GeoSource,
    LanguageCode,
    MarketTier,
    RevenueBenchmark,
)


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [("en-US", LanguageCode.EN), ("ES", LanguageCode.ES), ("pt-BR", LanguageCode.PT)],
)
def test_detect_language_prefers_explicit_audio_metadata(metadata, expected):
    result = detect_language(
        "The best English tutorial guide",
        metadata_language="de",
        audio_language=metadata,
    )

    assert result.language_code == expected
    assert result.confidence == 95.0
    assert result.source == GeoSource.CHANNEL_METADATA
    assert result.details == {"metadata_code": metadata}


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Cómo hacer la mejor guía para tu vídeo", LanguageCode.ES),
        ("Comment faire le meilleur guide pour votre projet", LanguageCode.FR),
        ("Wie ist das beste Tutorial für dein Projekt", LanguageCode.DE),
        ("Como fazer um guia para você com uma dica", LanguageCode.PT),
        ("How to make the best guide for your project", LanguageCode.EN),
    ],
)
def test_detect_language_from_text(title, expected):
    result = detect_language(title)

    assert result.language_code == expected
    assert result.source == GeoSource.TITLE_DESCRIPTION_INFERENCE
    assert result.confidence >= 50.0


def test_detect_language_handles_insufficient_unsupported_and_ambiguous_text():
    insufficient = detect_language("Great video")
    unsupported = detect_language("alpha beta gamma delta epsilon zeta eta theta")
    ambiguous = detect_language("the and how el los como")

    assert insufficient.language_code == LanguageCode.UNKNOWN
    assert insufficient.source == GeoSource.UNKNOWN
    assert insufficient.details["reason"] == "insufficient_text"
    assert unsupported.language_code == LanguageCode.OTHER
    assert unsupported.confidence == 35.0
    assert ambiguous.language_code == LanguageCode.UNKNOWN
    assert ambiguous.details["reason"] == "mixed_or_ambiguous"


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (None, ContentType.UNKNOWN),
        (True, ContentType.UNKNOWN),
        ("invalid", ContentType.UNKNOWN),
        (0, ContentType.UNKNOWN),
        (-1, ContentType.UNKNOWN),
        (1, ContentType.SHORT),
        (180, ContentType.SHORT),
        ("181", ContentType.LONG_FORM),
    ],
)
def test_classify_content_type_boundaries_and_invalid_values(duration, expected):
    assert classify_content_type(duration) == expected


def test_classify_content_type_supports_configured_short_threshold():
    assert classify_content_type(61, short_max_seconds=60) == ContentType.LONG_FORM


def test_estimate_geography_separates_channel_origin_from_inferred_audience():
    result = estimate_geography(
        {
            "video_id": "v1",
            "title": "The best guide for creators in Canada",
            "description": "How to grow your Canadian audience",
        },
        {"country": "US"},
    )

    assert result.channel_origin_country == "US"
    assert result.primary_country == "CA"
    assert result.estimated_audience_market == "CA"
    assert result.region_group == "North America"
    assert result.geo_source == GeoSource.TITLE_DESCRIPTION_INFERENCE
    assert result.country_signals == ["CA"]
    assert result.observed_fields == ["channel_origin_country"]
    assert "primary_country" in result.inferred_fields
    assert not any("channel origin was not used" in warning for warning in result.warnings)


def test_estimate_geography_uses_language_market_but_never_channel_country_as_audience():
    result = estimate_geography(
        {"video_id": "v2", "title": "Cómo hacer una guía para tu canal"},
        {"country": "CL"},
    )

    assert result.channel_origin_country == "CL"
    assert result.primary_country is None
    assert result.estimated_audience_market == "Spanish-language markets"
    assert result.geo_source == GeoSource.LANGUAGE_INFERENCE
    assert result.primary_country_confidence == 0.0
    assert any("channel origin was not used" in warning for warning in result.warnings)


def test_estimate_geography_rejects_conflicting_country_signals():
    result = estimate_geography(
        {"video_id": "v3", "title": "A travel guide from Canada to Mexico"}
    )

    assert set(result.country_signals) == {"CA", "MX"}
    assert result.primary_country is None
    assert result.region_group is None
    assert any("Conflicting audience country signals" in warning for warning in result.warnings)
    assert any("Channel origin country unavailable" in warning for warning in result.warnings)


def make_benchmark(
    market="US",
    content_type=ContentType.LONG_FORM,
    confidence=80.0,
    source_name="Verified source",
):
    return RevenueBenchmark(
        source_type=BenchmarkSourceType.MANUAL_BENCHMARK,
        source_name=source_name,
        market=market,
        content_type=content_type,
        value_low=2.0,
        value_mid=5.0,
        value_high=9.0,
        currency="EUR",
        confidence=confidence,
    )


def test_configured_provider_uses_highest_confidence_and_reports_coverage():
    lower = make_benchmark(confidence=40.0, source_name="Lower")
    higher = make_benchmark(confidence=90.0, source_name="Higher")
    short = make_benchmark(content_type=ContentType.SHORT, source_name="Short")
    provider = ConfiguredBenchmarkProvider([lower, higher, short])

    assert provider.get_benchmark("US", ContentType.LONG_FORM) is higher
    assert provider.get_benchmark("GB", ContentType.LONG_FORM) is None
    assert provider.list_benchmarks() == [lower, higher, short]
    assert provider.get_coverage_stats() == {
        "total_benchmarks": 3,
        "markets_covered": 1,
        "content_types_covered": 2,
        "source_types": {"manual_benchmark": 3},
        "markets": ["US"],
        "content_types": ["LONG_FORM", "SHORT"],
    }


def test_empty_provider_never_fabricates_revenue():
    provider = EmptyBenchmarkProvider()

    assert provider.get_benchmark("US", ContentType.LONG_FORM) is None
    assert provider.list_benchmarks() == []
    assert provider.get_coverage_stats()["total_benchmarks"] == 0


def test_analyze_video_links_benchmark_provenance_and_values():
    benchmark = make_benchmark()
    engine = RevenueGeographyEngine(ConfiguredBenchmarkProvider([benchmark]))

    result = engine.analyze_video(
        {
            "video_id": "v1",
            "title": "The best guide for creators in the United States",
            "duration_seconds": 600,
            "default_language": "en-US",
        },
        {"country": "CA"},
    )

    assert result.video_id == "v1"
    assert result.geography.primary_country == "US"
    assert result.revenue.content_type == ContentType.LONG_FORM
    assert result.revenue.estimated_market_tier == MarketTier.TIER_A
    assert (
        result.revenue.revenue_signal_low,
        result.revenue.revenue_signal_mid,
        result.revenue.revenue_signal_high,
    ) == (2.0, 5.0, 9.0)
    assert result.revenue.currency == "EUR"
    assert result.revenue.method == "documented_benchmark"
    assert result.revenue.benchmark_source_name == "Verified source"
    assert result.revenue.benchmark_confidence == 80.0
    assert result.economic_value.value == 100.0
    assert result.economic_value.inputs["benchmark_available"] is True
    assert result.revenue.warnings == []


def test_analyze_video_reports_unknown_format_and_missing_benchmark():
    result = RevenueGeographyEngine().analyze_video(
        {"video_id": "missing", "title": "Untitled", "duration_seconds": None}
    )

    assert result.revenue.content_type == ContentType.UNKNOWN
    assert result.revenue.estimated_market_tier == MarketTier.UNKNOWN
    assert result.revenue.revenue_signal_mid is None
    assert result.revenue.method == "unavailable"
    assert result.economic_value.value == 15.0
    assert len(result.revenue.warnings) == 2
    assert result.revenue.confidence == 0.0


def test_analyze_aggregates_clusters_and_quality_metrics():
    benchmark = make_benchmark()
    engine = RevenueGeographyEngine(ConfiguredBenchmarkProvider([benchmark]))
    videos = [
        {
            "video_id": "known",
            "channel_id": "channel-1",
            "title": "The best guide in the United States",
            "duration_seconds": 600,
            "default_language": "en",
        },
        {
            "video_id": "unknown",
            "channel_id": "channel-2",
            "title": "Tiny title",
            "duration_seconds": None,
        },
        {
            "video_id": "not-clustered",
            "channel_id": "channel-1",
            "title": "Cómo hacer la guía para México",
            "duration_seconds": 30,
        },
    ]
    clusters = [
        {"cluster_id": 7, "video_ids": ["known", "unknown", "missing-id"]},
        {"cluster_id": 8, "video_ids": []},
    ]

    result = engine.analyze(
        videos,
        [{"channel_id": "channel-1", "country": "CA"}],
        clusters,
        source_cluster_run_id="sprint5-source",
    )

    assert result.run_id.startswith("sprint6-")
    assert result.source_cluster_run_id == "sprint5-source"
    assert result.quality.model_dump() == {
        "language_unknown_rate": 33.3,
        "geo_unknown_rate": 33.3,
        "content_type_unknown_rate": 33.3,
        "benchmark_missing_rate": 66.7,
        "total_videos": 3,
        "total_clusters": 2,
    }
    aggregate = result.clusters[0]
    assert aggregate.cluster_id == 7
    assert aggregate.video_count == 2
    assert aggregate.language_distribution == {"en": 1, "unknown": 1}
    assert aggregate.estimated_market_distribution == {"US": 1, "UNKNOWN": 1}
    assert aggregate.market_tier_distribution == {"Tier A": 1, "Unknown": 1}
    assert aggregate.long_form_count == 1
    assert aggregate.unknown_format_count == 1
    assert aggregate.benchmark_coverage == 50.0
    assert "Small cluster sample reduces confidence." in aggregate.warnings

    empty = result.clusters[1]
    assert empty.video_count == 0
    assert empty.dominant_language == LanguageCode.UNKNOWN
    assert empty.estimated_market_distribution == {"UNKNOWN": 0}
    assert empty.audience_economic_value == 0.0
    assert empty.revenue_confidence == 0.0


def test_cluster_country_distribution_is_suppressed_when_majority_unknown():
    engine = RevenueGeographyEngine()
    videos = [
        {"video_id": "known", "title": "Guide for Canada", "duration_seconds": 200},
        {"video_id": "u1", "title": "Tiny title", "duration_seconds": 20},
        {"video_id": "u2", "title": "Other title", "duration_seconds": 20},
    ]

    aggregate = engine.analyze(
        videos,
        [],
        [{"cluster_id": 1, "video_ids": ["known", "u1", "u2"]}],
    ).clusters[0]

    assert aggregate.estimated_market_distribution == {"UNKNOWN": 3}
    assert any("distribution suppressed" in warning for warning in aggregate.warnings)
