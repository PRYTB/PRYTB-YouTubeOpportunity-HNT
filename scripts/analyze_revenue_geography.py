#!/usr/bin/env python3
"""Run Sprint 6 against the approved Sprint 5 production clusters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.benchmark_provider import EmptyBenchmarkProvider
from app.analytics.revenue_geography_engine import RevenueGeographyEngine
from app.database.repositories import YouTubeRepository
from app.models.geography import ContentType, LanguageCode
from scripts.sprint5_final_persist import build_final_result
from scripts.sprint5_reproducibility_runner import (
    APPROVED_ASSIGNMENTS_HASH,
    APPROVED_CLUSTERS,
    APPROVED_DATASET_HASH,
    APPROVED_PRODUCTION_VIDEOS,
    APPROVED_SILHOUETTE,
    audit_production_videos,
    canonical_dataset_rows,
    cluster_clean_dataset,
    validate_production_dataset,
)

MANUAL_VALIDATION_COUNT = 10


def _validate_approved_dataset(
    rows: List[Dict[str, str]],
    dataset_hash: str,
    assignments_hash: str,
    silhouette: float,
) -> None:
    if len(rows) != APPROVED_PRODUCTION_VIDEOS:
        raise AssertionError(
            f"Production video count mismatch: {len(rows)} != {APPROVED_PRODUCTION_VIDEOS}"
        )
    if dataset_hash != APPROVED_DATASET_HASH:
        raise AssertionError(
            f"Dataset hash mismatch: {dataset_hash} != {APPROVED_DATASET_HASH}"
        )
    if assignments_hash != APPROVED_ASSIGNMENTS_HASH:
        raise AssertionError(
            f"Assignments hash mismatch: {assignments_hash} != {APPROVED_ASSIGNMENTS_HASH}"
        )
    if abs(silhouette - APPROVED_SILHOUETTE) > 1e-12:
        raise AssertionError(
            f"Silhouette mismatch: {silhouette} != {APPROVED_SILHOUETTE}"
        )


def _manual_validation(videos: List[Any]) -> Dict[str, Any]:
    checked = []
    for item in videos[:MANUAL_VALIDATION_COUNT]:
        errors = []
        geography = item.geography
        revenue = item.revenue
        if geography.channel_origin_country and geography.primary_country is None:
            if geography.channel_origin_country == geography.estimated_audience_market:
                errors.append("channel origin copied to audience market")
        if revenue.method == "unavailable" and any(
            value is not None
            for value in (
                revenue.revenue_signal_low,
                revenue.revenue_signal_mid,
                revenue.revenue_signal_high,
            )
        ):
            errors.append("monetary value present without benchmark")
        if revenue.content_type == ContentType.UNKNOWN and not any(
            "duration metadata" in warning for warning in revenue.warnings
        ):
            errors.append("unknown content type lacks duration warning")
        checked.append(
            {
                "video_id": item.video_id,
                "title": item.title,
                "channel_origin_country": geography.channel_origin_country,
                "estimated_audience_market": geography.estimated_audience_market,
                "content_type": revenue.content_type.value,
                "benchmark": revenue.method,
                "status": "PASS" if not errors else "FAIL",
                "errors": errors,
            }
        )
    passed = len(checked) >= MANUAL_VALIDATION_COUNT and all(
        item["status"] == "PASS" for item in checked
    )
    return {"videos_checked": len(checked), "status": "PASS" if passed else "FAIL", "videos": checked}


def run_analysis(repository: YouTubeRepository | None = None) -> Dict[str, Any]:
    repo = repository or YouTubeRepository()
    all_videos = repo.get_all_videos()
    channels = repo.get_all_channels()
    production_videos, audit = audit_production_videos(all_videos)
    rows = canonical_dataset_rows(production_videos)
    dataset_hash = validate_production_dataset(rows)
    labels, silhouette, assignments_hash = cluster_clean_dataset(rows)
    _validate_approved_dataset(rows, dataset_hash, assignments_hash, silhouette)

    channel_count = len({row["channel_id"] for row in rows if row["channel_id"]})
    sprint5 = build_final_result(
        rows,
        dataset_hash,
        channel_count,
        audit,
        labels,
        silhouette,
        assignments_hash,
    )
    if len(sprint5.clusters) != APPROVED_CLUSTERS:
        raise AssertionError("Approved Sprint 5 cluster count changed.")

    videos_by_id = {
        str(video.get("video_id") or ""): video for video in production_videos
    }
    ordered_videos = [videos_by_id[row["video_id"]] for row in rows]
    cluster_payloads = [cluster.model_dump() for cluster in sprint5.clusters]
    provider = EmptyBenchmarkProvider()
    result = RevenueGeographyEngine(provider).analyze(
        ordered_videos,
        channels,
        cluster_payloads,
        source_cluster_run_id=sprint5.run_id,
    )

    labels_by_cluster = {cluster.cluster_id: cluster for cluster in sprint5.clusters}
    top_clusters = []
    for aggregate in sorted(
        result.clusters,
        key=lambda cluster: (
            cluster.audience_economic_value,
            cluster.revenue_confidence,
            cluster.video_count,
        ),
        reverse=True,
    )[:5]:
        label = labels_by_cluster[aggregate.cluster_id]
        top_clusters.append(
            {
                "cluster": aggregate.cluster_id,
                "niche": label.niche,
                "videos": aggregate.video_count,
                "dominant_language": aggregate.dominant_language.value,
                "market_tier_distribution": aggregate.market_tier_distribution,
                "long_form": aggregate.long_form_count,
                "shorts": aggregate.short_count,
                "audience_economic_value": aggregate.audience_economic_value,
                "confidence": aggregate.revenue_confidence,
                "warnings": list(dict.fromkeys(aggregate.warnings + label.label_warnings)),
            }
        )

    language_unknown = sum(
        item.geography.primary_language == LanguageCode.UNKNOWN for item in result.videos
    )
    observed_country = sum(
        item.geography.channel_origin_country is not None for item in result.videos
    )
    inferred_market = sum(
        item.geography.estimated_audience_market is not None for item in result.videos
    )
    long_form = sum(
        item.revenue.content_type == ContentType.LONG_FORM for item in result.videos
    )
    shorts = sum(item.revenue.content_type == ContentType.SHORT for item in result.videos)
    unknown_format = sum(
        item.revenue.content_type == ContentType.UNKNOWN for item in result.videos
    )
    available = sum(item.revenue.method == "documented_benchmark" for item in result.videos)
    economic_values = [item.economic_value.value for item in result.videos]
    confidences = [item.economic_value.confidence for item in result.videos]

    return {
        "dataset": {
            "videos": len(result.videos),
            "clusters": len(result.clusters),
            "dataset_hash": dataset_hash,
            "assignments_hash": assignments_hash,
        },
        "language": {
            "detected": len(result.videos) - language_unknown,
            "unknown": language_unknown,
            "unknown_rate": result.quality.language_unknown_rate,
        },
        "geography": {
            "observed_country_signals": observed_country,
            "inferred_market_signals": inferred_market,
            "unknown": sum(item.geography.primary_country is None for item in result.videos),
            "unknown_rate": result.quality.geo_unknown_rate,
            "unknown_rate_definition": "inferred audience country unavailable",
        },
        "content_type": {
            "long_form": long_form,
            "shorts": shorts,
            "unknown": unknown_format,
            "unknown_rate": result.quality.content_type_unknown_rate,
            "short_max_seconds": 180,
        },
        "revenue_benchmarks": {
            "provider": provider.__class__.__name__,
            "benchmarks_available": available,
            "coverage": round(100.0 - result.quality.benchmark_missing_rate, 1),
            "benchmark_missing_rate": result.quality.benchmark_missing_rate,
            "status": "unavailable" if available == 0 else "available",
            "fabricated_values": 0,
        },
        "economic_value": {
            "method": "internal tier/language/content-format/benchmark comparative indicator",
            "range": [min(economic_values), max(economic_values)] if economic_values else [0.0, 0.0],
            "median": round(median(economic_values), 1) if economic_values else 0.0,
            "confidence_median": round(median(confidences), 1) if confidences else 0.0,
        },
        "top_clusters": top_clusters,
        "manual_validation": _manual_validation(result.videos),
        "persistence": {
            "tables": "none (Sprint 6 is in-memory)",
            "writes": 0,
            "read_back": "not applicable",
            "integrity": "not applicable",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()
    report = run_analysis()
    if report["manual_validation"]["status"] != "PASS":
        raise SystemExit("Sprint 6 manual validation failed.")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
