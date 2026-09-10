#!/usr/bin/env python3
"""Run Sprint 7 against the approved Sprint 5 production clusters."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.market_structure_engine import MarketStructureEngine
from app.analytics.outlier_engine import OutlierEngine
from app.database.repositories import YouTubeRepository
from app.models.market_structure import MarketStructureClass, Sprint7AnalysisResult
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


def _timestamp_key(value: Any) -> tuple[int, float, str]:
    text = str(value or "").strip()
    if not text:
        return (0, 0.0, "")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return (0, 0.0, text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (1, parsed.astimezone(timezone.utc).timestamp(), text)


def _snapshot_key(record: Mapping[str, Any]) -> tuple[tuple[int, float, str], str, str]:
    return (
        _timestamp_key(record.get("collected_at")),
        str(record.get("id") or record.get("created_at") or ""),
        json.dumps(dict(record), sort_keys=True, default=str),
    )


def latest_snapshots(
    records: Iterable[Mapping[str, Any]], entity_field: str
) -> Dict[str, Mapping[str, Any]]:
    latest: Dict[str, Mapping[str, Any]] = {}
    for record in records:
        entity_id = str(record.get(entity_field) or "")
        if not entity_id:
            continue
        current = latest.get(entity_id)
        if current is None or _snapshot_key(record) > _snapshot_key(current):
            latest[entity_id] = record
    return latest


def enrich_with_latest_metrics(
    videos: List[Dict[str, Any]],
    channels: List[Dict[str, Any]],
    video_metrics: Iterable[Mapping[str, Any]],
    channel_metrics: Iterable[Mapping[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    latest_videos = latest_snapshots(video_metrics, "video_id")
    latest_channels = latest_snapshots(channel_metrics, "channel_id")
    enriched_videos = []
    for video in videos:
        enriched = dict(video)
        snapshot = latest_videos.get(str(video.get("video_id") or ""))
        if snapshot is not None:
            for field in ("view_count", "like_count", "comment_count"):
                if field in snapshot:
                    enriched[field] = snapshot[field]
        enriched_videos.append(enriched)
    enriched_channels = []
    for channel in channels:
        enriched = dict(channel)
        snapshot = latest_channels.get(str(channel.get("channel_id") or ""))
        if snapshot is not None:
            for field in ("subscriber_count", "video_count", "view_count"):
                if field in snapshot:
                    enriched[field] = snapshot[field]
        enriched_channels.append(enriched)
    return enriched_videos, enriched_channels


def _validate_approved_contract(
    rows: List[Dict[str, str]], dataset_hash: str, assignments_hash: str, silhouette: float
) -> None:
    if len(rows) != APPROVED_PRODUCTION_VIDEOS:
        raise AssertionError("Approved Sprint 5 production video count changed.")
    if dataset_hash != APPROVED_DATASET_HASH:
        raise AssertionError("Approved Sprint 5 dataset hash changed.")
    if assignments_hash != APPROVED_ASSIGNMENTS_HASH:
        raise AssertionError("Approved Sprint 5 assignments hash changed.")
    if abs(silhouette - APPROVED_SILHOUETTE) > 1e-12:
        raise AssertionError("Approved Sprint 5 silhouette changed.")


def _functional_validation(result: Sprint7AnalysisResult) -> Dict[str, Any]:
    errors = []
    ranks = [cluster.top_5_rank for cluster in result.clusters if cluster.top_5_rank is not None]
    expected_ranks = list(range(1, min(5, len(result.clusters)) + 1))
    if sorted(ranks) != expected_ranks:
        errors.append("Top 5 ranks are incomplete or duplicated")
    for cluster in result.clusters:
        if not cluster.microniche.strip():
            errors.append(f"cluster {cluster.cluster_id}: microniche is missing")
        if not cluster.content_atoms:
            errors.append(f"cluster {cluster.cluster_id}: content atoms are missing")
        if (
            cluster.short_video_count
            + cluster.long_form_video_count
            + cluster.unknown_format_count
            != cluster.video_count
        ):
            errors.append(f"cluster {cluster.cluster_id}: content format counts do not match")
        if cluster.market_structure_class == MarketStructureClass.VIRAL_SATURATED:
            if cluster.median_views is None or cluster.median_views < result.config["viral_median_views_min"]:
                errors.append(f"cluster {cluster.cluster_id}: viral without sufficient observed views")
        if cluster.market_structure_class == MarketStructureClass.CONTENT_CONSTRAINED:
            if cluster.content_depth_score >= result.config["sustainable_depth_min"]:
                errors.append(f"cluster {cluster.cluster_id}: constrained despite sufficient depth")
        if cluster.market_structure_class == MarketStructureClass.SUSTAINABLE_ACCESSIBLE:
            if cluster.accessibility.value not in {"HIGH", "MEDIUM"} or cluster.evergreen_class.value in {"TREND", "UNKNOWN"}:
                errors.append(f"cluster {cluster.cluster_id}: sustainable without accessibility/evergreen evidence")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors}


def run_analysis(
    repository: YouTubeRepository | None = None, persist: bool = False
) -> Dict[str, Any]:
    repo = repository or YouTubeRepository()
    all_videos = repo.get_all_videos()
    channels = repo.get_all_channels()
    production_videos, audit = audit_production_videos(all_videos)
    rows = canonical_dataset_rows(production_videos)
    dataset_hash = validate_production_dataset(rows)
    labels, silhouette, assignments_hash = cluster_clean_dataset(rows)
    _validate_approved_contract(rows, dataset_hash, assignments_hash, silhouette)

    sprint5 = build_final_result(
        rows,
        dataset_hash,
        len({row["channel_id"] for row in rows if row["channel_id"]}),
        audit,
        labels,
        silhouette,
        assignments_hash,
    )
    if len(sprint5.clusters) != APPROVED_CLUSTERS:
        raise AssertionError("Approved Sprint 5 cluster count changed.")

    enriched_videos, enriched_channels = enrich_with_latest_metrics(
        production_videos,
        channels,
        repo.get_all_video_metrics(),
        repo.get_all_channel_metrics(),
    )
    videos_by_id = {str(video.get("video_id") or ""): video for video in enriched_videos}
    ordered_videos = [videos_by_id[row["video_id"]] for row in rows]
    approved_video_ids = {row["video_id"] for row in rows}
    outlier_results = [
        item
        for item in OutlierEngine(repository=repo).analyze_all()
        if item.video_id in approved_video_ids
    ]
    result = MarketStructureEngine().analyze(
        ordered_videos,
        enriched_channels,
        [cluster.model_dump() for cluster in sprint5.clusters],
        source_cluster_run_id=sprint5.run_id,
        outlier_results=outlier_results,
    )
    validation = _functional_validation(result)
    persistence: Dict[str, Any] = {
        "requested": persist,
        "writes": 0,
        "read_back_verified": None,
    }
    if persist:
        written = repo.insert_market_structure_analysis(result)
        readback = repo.verify_market_structure_readback(result)
        if not readback.verified:
            raise RuntimeError("Sprint 7 persisted data failed exact read-back verification.")
        persistence.update(
            writes=written.records_written,
            read_back_verified=True,
            run_id=written.run_id,
        )

    classes = Counter(cluster.market_structure_class.value for cluster in result.clusters)
    return {
        "dataset": {
            "videos": len(rows),
            "clusters": len(result.clusters),
            "dataset_hash": dataset_hash,
            "assignments_hash": assignments_hash,
            "silhouette": silhouette,
        },
        "run_id": result.run_id,
        "source_cluster_run_id": result.source_cluster_run_id,
        "quality": result.quality.model_dump(mode="json"),
        "classification_counts": dict(sorted(classes.items())),
        "top_5": [
            cluster.model_dump(mode="json")
            for cluster in sorted(
                (item for item in result.clusters if item.top_5_rank is not None),
                key=lambda item: item.top_5_rank,
            )
        ],
        "clusters": [cluster.model_dump(mode="json") for cluster in result.clusters],
        "functional_validation": validation,
        "persistence": persistence,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist to PostgreSQL and require exact read-back verification.",
    )
    args = parser.parse_args()
    report = run_analysis(persist=args.persist)
    if report["functional_validation"]["status"] != "PASS":
        raise SystemExit("Sprint 7 functional validation failed.")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    print("rank\tcluster\tmicroniche\tscore\ttrend\tevergreen")
    for cluster in report["top_5"]:
        print(
            f"{cluster['top_5_rank']}\t{cluster['cluster_id']}\t"
            f"{cluster['microniche']}\t{cluster['market_structure_score']:.1f}\t"
            f"{cluster['trend_score']}\t{cluster['evergreen_class']}"
        )


if __name__ == "__main__":
    main()
