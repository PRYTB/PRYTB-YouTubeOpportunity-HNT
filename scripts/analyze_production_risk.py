#!/usr/bin/env python3
"""Run Sprint 8 against the approved Sprint 5 production clusters."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.market_structure_engine import MarketStructureEngine
from app.analytics.outlier_engine import OutlierEngine
from app.analytics.production_risk_engine import ProductionRiskEngine
from app.database.repositories import YouTubeRepository
from app.models.production_risk import ProductionComplexity, RiskLevel, Sprint8AnalysisResult
from scripts.analyze_market_structure import enrich_with_latest_metrics
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


def _functional_validation(result: Sprint8AnalysisResult) -> Dict[str, Any]:
    errors = []
    cluster_ids = [cluster.cluster_id for cluster in result.clusters]
    if len(cluster_ids) != len(set(cluster_ids)):
        errors.append("Cluster IDs are duplicated")
    for cluster in result.clusters:
        if not cluster.microniche.strip():
            errors.append(f"cluster {cluster.cluster_id}: microniche is missing")
        if cluster.estimated_hours_low is None or cluster.estimated_hours_high is None:
            errors.append(f"cluster {cluster.cluster_id}: production-hour range is missing")
        elif cluster.estimated_hours_low > cluster.estimated_hours_high:
            errors.append(f"cluster {cluster.cluster_id}: production-hour range is invalid")
        if cluster.risk_level is RiskLevel.UNKNOWN and cluster.overall_risk_score is not None:
            errors.append(f"cluster {cluster.cluster_id}: unknown risk has a score")
        if cluster.risk_level is not RiskLevel.UNKNOWN and cluster.overall_risk_score is None:
            errors.append(f"cluster {cluster.cluster_id}: classified risk has no score")
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
        item for item in OutlierEngine(repository=repo).analyze_all()
        if item.video_id in approved_video_ids
    ]
    sprint7 = MarketStructureEngine().analyze(
        ordered_videos,
        enriched_channels,
        [cluster.model_dump() for cluster in sprint5.clusters],
        source_cluster_run_id=sprint5.run_id,
        outlier_results=outlier_results,
    )
    result = ProductionRiskEngine().analyze(
        ordered_videos,
        [cluster.model_dump() for cluster in sprint5.clusters],
        source_market_structure_run_id=sprint7.run_id,
        source_cluster_run_id=sprint5.run_id,
    )
    validation = _functional_validation(result)
    persistence: Dict[str, Any] = {
        "requested": persist,
        "writes": 0,
        "read_back_verified": None,
    }
    if persist:
        written = repo.insert_production_risk_analysis(result)
        readback = repo.verify_production_risk_readback(result)
        if not readback.verified:
            raise RuntimeError("Sprint 8 persisted data failed exact read-back verification.")
        persistence.update(
            writes=written.records_written,
            read_back_verified=True,
            run_id=written.run_id,
        )

    risk_counts = Counter(cluster.risk_level.value for cluster in result.clusters)
    complexity_counts = Counter(cluster.production_complexity.value for cluster in result.clusters)
    return {
        "dataset": {
            "videos": len(rows),
            "clusters": len(result.clusters),
            "dataset_hash": dataset_hash,
            "assignments_hash": assignments_hash,
            "silhouette": silhouette,
        },
        "run_id": result.run_id,
        "source_market_structure_run_id": result.source_market_structure_run_id,
        "source_cluster_run_id": result.source_cluster_run_id,
        "quality": result.quality.model_dump(mode="json"),
        "risk_counts": dict(sorted(risk_counts.items())),
        "complexity_counts": dict(sorted(complexity_counts.items())),
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
        raise SystemExit("Sprint 8 functional validation failed.")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    print("cluster\tmicroniche\tcost\thours\trisk\tconfidence")
    for cluster in report["clusters"]:
        print(
            f"{cluster['cluster_id']}\t{cluster['microniche']}\t"
            f"{cluster['production_cost_score']:.1f}\t"
            f"{cluster['estimated_hours_low']}-{cluster['estimated_hours_high']}\t"
            f"{cluster['risk_level']}\t{cluster['confidence']:.1f}"
        )


if __name__ == "__main__":
    main()
