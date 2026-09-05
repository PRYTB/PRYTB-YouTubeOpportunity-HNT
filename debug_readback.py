#!/usr/bin/env python3
"""Debug readback issue."""
import json
from app.database.repositories import YouTubeRepository
from app.analytics.production_risk_engine import ProductionRiskEngine
from app.analytics.market_structure_engine import MarketStructureEngine
from app.analytics.outlier_engine import OutlierEngine
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

repo = YouTubeRepository()

all_videos = repo.get_all_videos()
channels = repo.get_all_channels()
production_videos, audit = audit_production_videos(all_videos)
rows = canonical_dataset_rows(production_videos)
dataset_hash = validate_production_dataset(rows)
labels, silhouette, assignments_hash = cluster_clean_dataset(rows)

sprint5 = build_final_result(
    rows,
    dataset_hash,
    len({row["channel_id"] for row in rows if row["channel_id"]}),
    audit,
    labels,
    silhouette,
    assignments_hash,
)

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
sprint8 = ProductionRiskEngine().analyze(
    ordered_videos,
    [cluster.model_dump() for cluster in sprint5.clusters],
    source_market_structure_run_id=sprint7.run_id,
    source_cluster_run_id=sprint5.run_id,
)

# Now write and read back
written = repo.insert_production_risk_analysis(sprint8)
print(f"Written: {written.records_written} records")

readback = repo.verify_production_risk_readback(sprint8)
print(f"Readback: expected={readback.expected_records}, actual={readback.actual_records}, unique={readback.unique_clusters}, duplicates={readback.duplicate_records}, mismatches={readback.payload_mismatches}, verified={readback.verified}")

# Let's also check the actual records in DB
records = repo._get_records("production_risk_analyses", params={"run_id": f"eq.{sprint8.run_id}"})
print(f"DB records: {len(records)}")
for r in records:
    print(f"  cluster_id: {r.get('cluster_id')}")
    print(f"  quality: {r.get('quality')}")
    print()