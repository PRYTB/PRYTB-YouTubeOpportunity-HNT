#!/usr/bin/env python3
"""Run Sprint 9 Profitability Analysis against approved Sprint 5 production clusters."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.market_structure_engine import MarketStructureEngine
from app.analytics.outlier_engine import OutlierEngine
from app.analytics.production_risk_engine import ProductionRiskEngine
from app.analytics.profitability_engine import ProfitabilityEngine
from app.analytics.revenue_geography_engine import RevenueGeographyEngine
from app.database.repositories import YouTubeRepository
from app.models.profitability import Sprint9AnalysisResult
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


def run_analysis(
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

    # 3. Load prior evidence (Sprint 6 Revenue, Sprint 7 Market Structure, Sprint 8 Production Risk)
    rev_engine = RevenueGeographyEngine()
    sprint6_res = rev_engine.analyze(
        videos=enriched_videos,
        channels=enriched_channels,
        clusters=[
            {
                "cluster_id": c.cluster_id,
                "video_ids": c.video_ids,
            }
            for c in sprint5.clusters
        ],
        source_cluster_run_id=sprint5.run_id,
    )

    outlier_results = OutlierEngine(repository=repo).analyze_all()
    market_engine = MarketStructureEngine()
    sprint7_res = market_engine.analyze(
        videos=enriched_videos,
        channels=enriched_channels,
        clusters=[
            {
                "cluster_id": c.cluster_id,
                "video_ids": c.video_ids,
            }
            for c in sprint5.clusters
        ],
        source_cluster_run_id=sprint5.run_id,
        outlier_results=outlier_results,
    )

    prod_engine = ProductionRiskEngine()
    sprint8_res = prod_engine.analyze(
        videos=enriched_videos,
        clusters=[
            {
                "cluster_id": c.cluster_id,
                "video_ids": c.video_ids,
            }
            for c in sprint5.clusters
        ],
        source_cluster_run_id=sprint5.run_id,
        source_market_structure_run_id=sprint7_res.run_id,
    )

    market_structures_map = {c.cluster_id: c for c in sprint7_res.clusters}
    production_risks_map = {c.cluster_id: c for c in sprint8_res.clusters}

    # Prepare cluster data tuples
    clusters_data = []
    for cluster in sprint5.clusters:
        c_videos = [videos_by_id[vid] for vid in cluster.video_ids if vid in videos_by_id]
        clusters_data.append({
            "cluster_id": cluster.cluster_id,
            "niche": cluster.niche,
            "subniche": cluster.subniche,
            "microniche": cluster.microniche,
            "videos": c_videos,
        })

    # 4. Run Profitability Engine
    prof_engine = ProfitabilityEngine()
    result: Sprint9AnalysisResult = prof_engine.analyze_all(
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

    persisted = None
    readback = None
    if persist:
        persisted = repo.insert_profitability_analysis(result)
        readback = repo.verify_profitability_readback(result)

    return {
        "result": result,
        "persisted": persisted,
        "readback": readback,
        "source_runs": {
            "cluster": sprint5.run_id,
            "revenue": sprint6_res.run_id,
            "market": sprint7_res.run_id,
            "production": sprint8_res.run_id,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sprint 9 Profitability Analysis CLI")
    parser.add_argument("--persist", action="store_true", help="Persist analysis results to InsForge DB")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    analysis = run_analysis(persist=args.persist)
    res: Sprint9AnalysisResult = analysis["result"]

    if args.json:
        print(json.dumps(res.model_dump(mode="json"), indent=2))
        return

    print("==================================================")
    print("PRYTB — SPRINT 9 PROFITABILITY ANALYSIS")
    print("==================================================")
    print(f"Run ID: {res.run_id}")
    print(f"Dataset Hash: {res.dataset_hash}")
    print(f"Assignments Hash: {res.assignments_hash}")
    print(f"Clusters Analyzed: {len(res.clusters)}")
    print(f"Top 5 Candidates: {res.top_5_candidates}")
    print("--------------------------------------------------")
    for c in sorted(res.clusters, key=lambda x: x.profitability_score, reverse=True):
        print(
            f"Cluster {c.cluster_id:2d} | Score: {c.profitability_score:5.1f} | "
            f"Band: {c.classification.value:11s} | Conf: {c.confidence:4.1f}% | "
            f"Views(base): {c.expected_views_range.base:8,.0f} | "
            f"RPM: {'YES' if c.rpm_range.available else 'NO'} | "
            f"Niche: {c.microniche}"
        )
    print("==================================================")


if __name__ == "__main__":
    main()
