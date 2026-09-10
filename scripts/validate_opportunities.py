#!/usr/bin/env python3
"""Run Sprint 10 Adversarial Opportunity Validation against Sprint 9 profitability candidates."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.market_structure_engine import MarketStructureEngine
from app.analytics.opportunity_validator import OpportunityValidator
from app.analytics.outlier_engine import OutlierEngine
from app.analytics.production_risk_engine import ProductionRiskEngine
from app.analytics.profitability_engine import ProfitabilityEngine
from app.analytics.revenue_geography_engine import RevenueGeographyEngine
from app.database.repositories import YouTubeRepository
from app.models.validation import Sprint10AnalysisResult
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


def run_validation(
    repository: YouTubeRepository | None = None, persist: bool = False
) -> Dict[str, Any]:
    repo = repository or YouTubeRepository()

    # 1. Load canonical Sprint 5 production contract
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

    # 2. Enrich videos with latest metrics
    enriched_videos, enriched_channels = enrich_with_latest_metrics(
        production_videos,
        channels,
        repo.get_all_video_metrics(),
        repo.get_all_channel_metrics(),
    )
    videos_by_id = {str(video.get("video_id") or ""): video for video in enriched_videos}

    # 3. Load prior evidence (Sprint 6, 7, 8)
    rev_engine = RevenueGeographyEngine()
    sprint6_res = rev_engine.analyze(
        videos=enriched_videos,
        channels=enriched_channels,
        clusters=[
            {"cluster_id": c.cluster_id, "video_ids": c.video_ids}
            for c in sprint5.clusters
        ],
        source_cluster_run_id=sprint5.run_id,
    )

    outlier_engine = OutlierEngine(repository=repo)
    outlier_results = outlier_engine.analyze_all()
    outliers_by_video = {o.video_id: o for o in outlier_results}

    market_engine = MarketStructureEngine()
    sprint7_res = market_engine.analyze(
        videos=enriched_videos,
        channels=enriched_channels,
        clusters=[
            {"cluster_id": c.cluster_id, "video_ids": c.video_ids}
            for c in sprint5.clusters
        ],
        source_cluster_run_id=sprint5.run_id,
        outlier_results=outlier_results,
    )

    prod_engine = ProductionRiskEngine()
    sprint8_res = prod_engine.analyze(
        videos=enriched_videos,
        clusters=[
            {"cluster_id": c.cluster_id, "video_ids": c.video_ids}
            for c in sprint5.clusters
        ],
        source_cluster_run_id=sprint5.run_id,
        source_market_structure_run_id=sprint7_res.run_id,
    )

    market_structures_map = {c.cluster_id: c for c in sprint7_res.clusters}
    production_risks_map = {c.cluster_id: c for c in sprint8_res.clusters}

    clusters_data = []
    clusters_videos_map = {}
    outliers_map = {}

    for cluster in sprint5.clusters:
        c_videos = [videos_by_id[vid] for vid in cluster.video_ids if vid in videos_by_id]
        clusters_data.append({
            "cluster_id": cluster.cluster_id,
            "niche": cluster.niche,
            "subniche": cluster.subniche,
            "microniche": cluster.microniche,
            "videos": c_videos,
        })
        clusters_videos_map[cluster.cluster_id] = c_videos
        outliers_map[cluster.cluster_id] = [outliers_by_video[vid] for vid in cluster.video_ids if vid in outliers_by_video]

    # 4. Run Sprint 9 Profitability Analysis
    prof_engine = ProfitabilityEngine()
    sprint9_res = prof_engine.analyze_all(
        clusters_data=clusters_data,
        market_structures=market_structures_map,
        production_risks=production_risks_map,
        source_cluster_run_id=sprint5.run_id,
        source_revenue_run_id=sprint6_res.run_id,
        source_market_run_id=sprint7_res.run_id,
        source_production_run_id=sprint8_res.run_id,
        dataset_hash=dataset_hash,
        assignments_hash=assignments_hash,
    )

    # 5. Run Sprint 10 Opportunity Validator
    validator = OpportunityValidator()
    val_res: Sprint10AnalysisResult = validator.validate_all(
        profitability_analyses=sprint9_res.clusters,
        clusters_videos_map=clusters_videos_map,
        market_structures_map=market_structures_map,
        production_risks_map=production_risks_map,
        outliers_map=outliers_map,
        source_profitability_run_id=sprint9_res.run_id,
        source_cluster_run_id=sprint5.run_id,
        source_revenue_run_id=sprint6_res.run_id,
        source_market_run_id=sprint7_res.run_id,
        source_production_run_id=sprint8_res.run_id,
        dataset_hash=dataset_hash,
        assignments_hash=assignments_hash,
    )

    persisted = None
    readback = None
    if persist:
        persisted = repo.insert_validation_analysis(val_res)
        readback = repo.verify_validation_readback(val_res)

    return {
        "result": val_res,
        "sprint9_result": sprint9_res,
        "sprint5_clusters": sprint5.clusters,
        "sprint6_result": sprint6_res,
        "sprint7_result": sprint7_res,
        "sprint8_result": sprint8_res,
        "outlier_results": outlier_results,
        "ordered_videos": [videos_by_id[row["video_id"]] for row in rows],
        "enriched_channels": enriched_channels,
        "persisted": persisted,
        "readback": readback,
        "source_runs": {
            "profitability": sprint9_res.run_id,
            "cluster": sprint5.run_id,
            "revenue": sprint6_res.run_id,
            "market": sprint7_res.run_id,
            "production": sprint8_res.run_id,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sprint 10 Opportunity Validator CLI")
    parser.add_argument("--persist", action="store_true", help="Persist analysis results to PostgreSQL")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    analysis = run_validation(persist=args.persist)
    res: Sprint10AnalysisResult = analysis["result"]

    if args.json:
        print(json.dumps(res.model_dump(mode="json"), indent=2))
        return

    print("==================================================")
    print("PRYTB — SPRINT 10 ADVERSARIAL OPPORTUNITY VALIDATOR")
    print("==================================================")
    print(f"Run ID: {res.run_id}")
    print(f"Profitability Run ID: {res.source_profitability_run_id}")
    print(f"Dataset Hash: {res.dataset_hash}")
    print(f"Assignments Hash: {res.assignments_hash}")
    print(f"Validated Candidates: {res.validated_candidates}")
    print("--------------------------------------------------")
    for c in sorted(res.clusters, key=lambda x: x.validation_score, reverse=True):
        print(
            f"Cluster {c.cluster_id:2d} | ValScore: {c.validation_score:5.1f} | "
            f"Status: {c.validation_status.value:18s} | Conf: {c.validation_confidence:4.1f}% | "
            f"Fragility: {c.fragility_score:4.1f} | FpRisk: {c.false_positive_risk:4.1f} | "
            f"ProfScore: {c.profitability_score:5.1f} | Niche: {c.microniche}"
        )
    print("==================================================")


if __name__ == "__main__":
    main()
