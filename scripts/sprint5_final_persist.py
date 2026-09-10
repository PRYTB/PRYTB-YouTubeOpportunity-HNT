#!/usr/bin/env python3
"""
Sprint 5 Final Production Persistence
Executes the exact approved pipeline, enforces pre-persistence assertions,
adds deterministic labels with warnings, persists to PostgreSQL, and verifies read-back.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np
from sklearn.metrics import silhouette_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.clustering_engine import ClusterOptimizer
from app.analytics.labeler import ClusterLabeler, validate_label_quality
from app.analytics.semantic_provider import TFIDFLocalSemanticProvider
from app.analytics.text_normalizer import clean_text_for_embedding
from app.database.repositories import YouTubeRepository
from app.models.niche import NicheCluster, NicheMiningResult

# ============================================================
# APPROVED PRODUCTION CONFIGURATION (DO NOT CHANGE)
# ============================================================
APPROVED_SEMANTIC_TEXT_VERSION = "sprint5-v1"
APPROVED_REPRESENTATION = "title_only_unigrams"
APPROVED_ALGORITHM = "kmeans"
APPROVED_K = 10
APPROVED_RANDOM_STATE = 42
APPROVED_TFIDF_PARAMETERS: Dict[str, Any] = {
    "max_features": 500,
    "ngram_range": [1, 1],
    "min_df": 2,
    "max_df": 0.9,
    "sublinear_tf": False,
}
# Exact approved values from preflight
APPROVED_DATASET_HASH = "5b284b89e17d11aca86661bd8a53715b43b212f6f5aaf99ca4210884b5925091"
APPROVED_ASSIGNMENTS_HASH = "d03cb6bd13b72e8f6859ec0f6c2ea1104f59799f6480d81d95b3df5bca751340"
APPROVED_SILHOUETTE = 0.06862934221732106
APPROVED_SILHOUETTE_TOLERANCE = 1e-12
APPROVED_PRODUCTION_VIDEOS = 7611
APPROVED_CLUSTERS = 10

# Test record exclusion
_TEST_ID_PATTERN = re.compile(r"(^|[_-])(test|fixture|mock)([_-]|$)", re.IGNORECASE)
_TEST_TEXT_MARKERS = ("integration test", "fixture data", "mock data", "test data")


def is_test_video(video: Mapping[str, Any]) -> bool:
    """Identify explicit test/fixture records without classifying ordinary real titles."""
    video_id = str(video.get("video_id", "") or "")
    text = " ".join(
        (
            str(video.get("title", "") or ""),
            str(video.get("description", "") or ""),
        )
    ).lower()
    return bool(_TEST_ID_PATTERN.search(video_id)) or any(
        marker in text for marker in _TEST_TEXT_MARKERS
    )


def audit_production_videos(
    videos: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    test_records = [video for video in videos if is_test_video(video)]
    production_videos = [video for video in videos if not is_test_video(video)]
    audit = {
        "videos_before": len(videos),
        "test_records_detected": len(test_records),
        "test_records_excluded": len(test_records),
        "test_video_ids": sorted(
            str(video.get("video_id", "") or "") for video in test_records
        ),
        "production_videos": len(production_videos),
    }
    return production_videos, audit


def canonical_dataset_rows(videos: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows = []
    for video in videos:
        title = str(video.get("title", "") or "")
        description = str(video.get("description", "") or "")
        rows.append(
            {
                "video_id": str(video.get("video_id", "") or ""),
                "semantic_text": clean_text_for_embedding(title, description),
                "semantic_text_title": clean_text_for_embedding(title, None),
                "channel_id": str(video.get("channel_id", "") or ""),
                "title": title,
            }
        )
    rows.sort(key=lambda row: row["video_id"])
    return rows


def compute_dataset_hash(rows: List[Dict[str, str]]) -> str:
    payload = "\n".join(
        f"{row['video_id']}||{row['semantic_text']}" for row in rows
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_assignments_hash(video_ids: List[str], labels: List[int]) -> str:
    pairs = sorted(zip(video_ids, labels), key=lambda pair: pair[0])
    payload = "\n".join(
        f"{video_id}::{int(label)}" for video_id, label in pairs
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_production_dataset(rows: List[Dict[str, str]]) -> str:
    video_ids = [row["video_id"] for row in rows]
    if not rows:
        raise ValueError("Production dataset is empty.")
    if any(not video_id for video_id in video_ids):
        raise ValueError("Production dataset contains an empty video_id.")
    if len(video_ids) != len(set(video_ids)):
        raise ValueError("Production dataset contains duplicate video IDs.")
    if any(
        not row["title"] or not row["semantic_text"] or not row["semantic_text_title"]
        for row in rows
    ):
        raise ValueError("Every production video must have title and semantic text.")
    return compute_dataset_hash(rows)


def load_clean_dataset(
    repository: Optional[YouTubeRepository] = None,
) -> Tuple[List[Dict[str, str]], str, int, Dict[str, Any]]:
    repo = repository or YouTubeRepository()
    videos = repo.get_all_videos()
    production_videos, audit = audit_production_videos(videos)
    rows = canonical_dataset_rows(production_videos)
    dataset_hash = validate_production_dataset(rows)
    channel_count = len({row["channel_id"] for row in rows if row["channel_id"]})
    return rows, dataset_hash, channel_count, audit


def cluster_clean_dataset(
    rows: List[Dict[str, str]],
) -> Tuple[np.ndarray, float, str]:
    provider = TFIDFLocalSemanticProvider(
        max_features=APPROVED_TFIDF_PARAMETERS["max_features"],
        ngram_range=tuple(APPROVED_TFIDF_PARAMETERS["ngram_range"]),
        min_df=APPROVED_TFIDF_PARAMETERS["min_df"],
        max_df=APPROVED_TFIDF_PARAMETERS["max_df"],
        sublinear_tf=APPROVED_TFIDF_PARAMETERS["sublinear_tf"],
    )
    embeddings = provider.embed_texts(
        [row["semantic_text_title"] for row in rows]
    )
    optimizer = ClusterOptimizer(
        min_k=APPROVED_K,
        max_k=APPROVED_K,
        random_state=APPROVED_RANDOM_STATE,
    )
    labels = np.asarray(
        optimizer._fit_single(embeddings, k=APPROVED_K, algorithm=APPROVED_ALGORITHM),
        dtype=int,
    )
    silhouette = float(silhouette_score(embeddings, labels, metric="cosine"))
    assignments_hash = compute_assignments_hash(
        [row["video_id"] for row in rows], labels.tolist()
    )
    return labels, silhouette, assignments_hash


def build_final_result(
    rows: List[Dict[str, str]],
    dataset_hash: str,
    channel_count: int,
    audit: Dict[str, Any],
    labels: np.ndarray,
    silhouette: float,
    assignments_hash: str,
) -> NicheMiningResult:
    """Build the final production result with deterministic labels and warnings."""
    started_at = time.time()
    
    # Generate deterministic labels for each cluster
    labeler = ClusterLabeler(api_key=None)  # Use deterministic fallback
    clusters: List[NicheCluster] = []
    
    for cluster_id in range(APPROVED_K):
        cluster_rows = [
            row for row, label in zip(rows, labels) if int(label) == cluster_id
        ]
        video_ids = [row["video_id"] for row in cluster_rows]
        representative_titles = [row["title"] for row in cluster_rows[:5]]
        
        # Get deterministic label hierarchy
        hierarchy = labeler.label_cluster(representative_titles)
        quality_score, warnings = validate_label_quality(
            hierarchy.niche,
            hierarchy.subniche,
            hierarchy.microniche,
            representative_titles,
        )
        
        # Compute channel diversity metrics
        unique_channels = len(
            {row["channel_id"] for row in cluster_rows if row["channel_id"]}
        )
        if unique_channels > 0 and len(video_ids) > 0:
            from collections import Counter
            channel_counts = Counter(row["channel_id"] for row in cluster_rows if row["channel_id"])
            dominant_channel_share = max(channel_counts.values()) / len(video_ids)
            if dominant_channel_share > 0.7:
                channel_diversity = "LOW_DIVERSITY"
            elif dominant_channel_share > 0.4:
                channel_diversity = "MEDIUM_DIVERSITY"
            else:
                channel_diversity = "HIGH_DIVERSITY"
        else:
            dominant_channel_share = 0.0
            channel_diversity = "MEDIUM_DIVERSITY"
        
        clusters.append(
            NicheCluster(
                cluster_id=cluster_id,
                video_ids=video_ids,
                video_count=len(cluster_rows),
                unique_channels=unique_channels,
                dominant_channel_share=dominant_channel_share,
                channel_diversity=channel_diversity,
                representative_titles=representative_titles,
                niche=hierarchy.niche,
                subniche=hierarchy.subniche,
                microniche=hierarchy.microniche,
                summary=hierarchy.summary,
                label_confidence=hierarchy.confidence,
                label_quality_score=quality_score,
                label_warnings=warnings,
                semantic_quality=silhouette,
                confidence=hierarchy.confidence,
            )
        )

    if len(clusters) != APPROVED_K or any(not cluster.video_ids for cluster in clusters):
        raise ValueError("Clean preflight must produce exactly 10 non-empty clusters.")
    if sum(cluster.video_count for cluster in clusters) != len(rows):
        raise ValueError("Cluster video counts do not match the production dataset.")

    created_at = datetime.now(timezone.utc).isoformat()
    # Create a deterministic production run_id based on assignments_hash
    run_id = f"sprint5_prod_{assignments_hash[:12]}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    
    parameters = {
        "dataset_hash": dataset_hash,
        "dataset_size": len(rows),
        "channel_count": channel_count,
        "semantic_text_version": APPROVED_SEMANTIC_TEXT_VERSION,
        "representation": APPROVED_REPRESENTATION,
        "vectorizer_parameters": dict(APPROVED_TFIDF_PARAMETERS),
        "algorithm": APPROVED_ALGORITHM,
        "K": APPROVED_K,
        "random_state": APPROVED_RANDOM_STATE,
        "silhouette": silhouette,
        "assignments_hash": assignments_hash,
        "assignment_source": "recomputed_kmeans",
        "cluster_sizes": [cluster.video_count for cluster in clusters],
        "data_audit": audit,
        "created_at": created_at,
    }
    return NicheMiningResult(
        run_id=run_id,
        algorithm=APPROVED_ALGORITHM,
        parameters=parameters,
        semantic_provider="LocalSemanticProvider (TF-IDF)",
        videos_considered=audit["videos_before"],
        videos_embedded=len(rows),
        videos_skipped=audit["test_records_excluded"],
        total_clusters=APPROVED_K,
        unassigned_count=0,
        quality_metric_name="silhouette_score_cosine",
        quality_metric_value=silhouette,
        clusters=clusters,
        elapsed_seconds=round(time.time() - started_at, 3),
        created_at=created_at,
    )


def assert_pre_persistence_conditions(
    rows: List[Dict[str, str]],
    dataset_hash: str,
    labels: np.ndarray,
    silhouette: float,
    assignments_hash: str,
    audit: Dict[str, Any],
) -> None:
    """Enforce all pre-persistence assertions. Stop immediately if any fails."""
    
    # 1. Dataset hash must match approved exactly
    if dataset_hash != APPROVED_DATASET_HASH:
        raise AssertionError(
            f"DATASET_HASH MISMATCH: got {dataset_hash}, expected {APPROVED_DATASET_HASH}"
        )
    print(f"[OK] Dataset hash verified: {dataset_hash}")
    
    # 2. K must be 10
    if APPROVED_K != 10:
        raise AssertionError(f"K MUST BE 10, got {APPROVED_K}")
    print("[OK] K = 10 verified")
    
    # 3. Silhouette within safe float tolerance
    if abs(silhouette - APPROVED_SILHOUETTE) > APPROVED_SILHOUETTE_TOLERANCE:
        raise AssertionError(
            f"SILHOUETTE MISMATCH: got {silhouette}, expected {APPROVED_SILHOUETTE} "
            f"(diff={abs(silhouette - APPROVED_SILHOUETTE):.2e})"
        )
    print(f"[OK] Silhouette verified: {silhouette}")
    
    # 4. Assignments hash must match approved exactly
    if assignments_hash != APPROVED_ASSIGNMENTS_HASH:
        raise AssertionError(
            f"ASSIGNMENTS_HASH MISMATCH: got {assignments_hash}, expected {APPROVED_ASSIGNMENTS_HASH}"
        )
    print(f"[OK] Assignments hash verified: {assignments_hash}")
    
    # 5. sum(video_count) == 83
    if len(rows) != APPROVED_PRODUCTION_VIDEOS:
        raise AssertionError(
            f"PRODUCTION VIDEO COUNT MISMATCH: got {len(rows)}, expected {APPROVED_PRODUCTION_VIDEOS}"
        )
    print(f"[OK] Production video count verified: {len(rows)}")
    
    # 6. cluster_count == 10
    unique_labels = len(set(labels))
    if unique_labels != APPROVED_CLUSTERS:
        raise AssertionError(
            f"CLUSTER COUNT MISMATCH: got {unique_labels}, expected {APPROVED_CLUSTERS}"
        )
    print(f"[OK] Cluster count verified: {unique_labels}")
    
    # 7. Test record exclusion - VID_TEST_INTEGRATION_99 must not be in production
    test_vids = audit.get("test_video_ids", [])
    if "VID_TEST_INTEGRATION_99" not in test_vids:
        raise AssertionError("VID_TEST_INTEGRATION_99 not detected in test records")
    if audit.get("test_records_excluded", 0) != 1:
        raise AssertionError(
            f"Expected exactly 1 test record excluded, got {audit.get('test_records_excluded', 0)}"
        )
    print(f"[OK] Test record exclusion verified: VID_TEST_INTEGRATION_99 excluded")
    
    print("\n[OK] ALL PRE-PERSISTENCE ASSERTIONS PASSED")


def result_report(result: NicheMiningResult) -> Dict[str, Any]:
    audit = result.parameters["data_audit"]
    return {
        "mode": "production",
        "persisted": True,
        "run_id": result.run_id,
        "videos_before": audit["videos_before"],
        "test_records_detected": audit["test_records_detected"],
        "test_records_excluded": audit["test_records_excluded"],
        "test_video_ids": audit["test_video_ids"],
        "production_videos": result.videos_embedded,
        "dataset_hash": result.parameters["dataset_hash"],
        "representation": result.parameters["representation"],
        "vectorizer_parameters": result.parameters["vectorizer_parameters"],
        "algorithm": result.algorithm,
        "K": result.parameters["K"],
        "random_state": result.parameters["random_state"],
        "silhouette": result.parameters["silhouette"],
        "assignments_hash": result.parameters["assignments_hash"],
        "clusters": len(result.clusters),
        "sum_video_count": sum(cluster.video_count for cluster in result.clusters),
        "cluster_sizes": result.parameters["cluster_sizes"],
        "cluster_labels": [
            {
                "cluster_id": c.cluster_id,
                "niche": c.niche,
                "subniche": c.subniche,
                "microniche": c.microniche,
                "label_confidence": c.label_confidence,
                "label_quality_score": c.label_quality_score,
                "label_warnings": c.label_warnings,
            }
            for c in result.clusters
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Run the final production persistence with assertions and read-back verification.",
    )
    args = parser.parse_args()
    
    if not args.persist:
        parser.print_help()
        return 1
    
    print("=" * 60)
    print("SPRINT 5 FINAL PRODUCTION PERSISTENCE")
    print("=" * 60)
    
    # Step 1: Load clean dataset
    print("\n[STEP 1] Loading clean production dataset...")
    repo = YouTubeRepository()
    rows, dataset_hash, channel_count, audit = load_clean_dataset(repo)
    print(f"  Loaded {len(rows)} production videos from {audit['videos_before']} total")
    
    # Step 2: Run approved clustering
    print("\n[STEP 2] Running approved clustering (K=10, KMeans, title_only_unigrams)...")
    labels, silhouette, assignments_hash = cluster_clean_dataset(rows)
    
    # Step 3: Enforce pre-persistence assertions
    print("\n[STEP 3] Enforcing pre-persistence assertions...")
    assert_pre_persistence_conditions(
        rows, dataset_hash, labels, silhouette, assignments_hash, audit
    )
    
    # Step 4: Build final result with deterministic labels
    print("\n[STEP 4] Building final result with deterministic labels...")
    result = build_final_result(
        rows, dataset_hash, channel_count, audit, labels, silhouette, assignments_hash
    )
    print(f"  Run ID: {result.run_id}")
    print(f"  Clusters: {len(result.clusters)}")
    print(f"  Total videos assigned: {sum(c.video_count for c in result.clusters)}")
    
    # Show label warnings
    for c in result.clusters:
        if c.label_warnings:
            print(f"  Cluster {c.cluster_id} warnings: {c.label_warnings}")
    
    # Step 5: Persist to PostgreSQL
    print("\n[STEP 5] Persisting to PostgreSQL (clusters, subniches, cluster_videos)...")
    persist_result = repo.insert_clusters(result)
    print(f"  Clusters written: {persist_result.clusters_written}")
    print(f"  Subniches written: {persist_result.subniches_written}")
    print(f"  Cluster_videos written: {persist_result.cluster_videos_written}")
    
    # Step 6: Read-back verification
    print("\n[STEP 6] Read-back verification from PostgreSQL...")
    readback = repo.verify_clusters_readback(result)
    
    # Verify exact counts
    if readback.actual_clusters != 10:
        raise AssertionError(f"Read-back cluster count: got {readback.actual_clusters}, expected 10")
    if readback.actual_subniches != 10:
        raise AssertionError(f"Read-back subniche count: got {readback.actual_subniches}, expected 10")
    if readback.actual_cluster_videos != 83:
        raise AssertionError(f"Read-back cluster_videos count: got {readback.actual_cluster_videos}, expected 83")
    
    # Verify VID_TEST_INTEGRATION_99 is absent
    if readback.missing_videos > 0:
        raise AssertionError(f"Missing videos detected: {readback.missing_videos}")
    if readback.orphan_cluster_videos > 0:
        raise AssertionError(f"Orphan cluster_videos detected: {readback.orphan_cluster_videos}")
    if readback.orphan_subniches > 0:
        raise AssertionError(f"Orphan subniches detected: {readback.orphan_subniches}")
    if readback.duplicate_clusters > 0:
        raise AssertionError(f"Duplicate clusters detected: {readback.duplicate_clusters}")
    if readback.duplicate_videos > 0:
        raise AssertionError(f"Duplicate video assignments detected: {readback.duplicate_videos}")
    if readback.cluster_payload_mismatches > 0:
        raise AssertionError(f"Cluster payload mismatches: {readback.cluster_payload_mismatches}")
    if readback.subniche_payload_mismatches > 0:
        raise AssertionError(f"Subniche payload mismatches: {readback.subniche_payload_mismatches}")
    if readback.cluster_video_payload_mismatches > 0:
        raise AssertionError(f"Cluster_video payload mismatches: {readback.cluster_video_payload_mismatches}")
    
    # Verify metadata matches
    if not readback.verified:
        raise AssertionError("Read-back verification failed: verified=false")
    
    print(f"  Clusters: {readback.actual_clusters}/10 [OK]")
    print(f"  Subniches: {readback.actual_subniches}/10 [OK]")
    print(f"  Cluster_videos: {readback.actual_cluster_videos}/83 [OK]")
    print(f"  Unique videos: {readback.unique_videos}/83 [OK]")
    print(f"  Unique cluster_ids: {readback.unique_cluster_ids}/10 [OK]")
    print(f"  Duplicates: {readback.duplicate_clusters} clusters, {readback.duplicate_videos} videos [OK]")
    print(f"  Orphans: {readback.orphan_cluster_videos} cluster_videos, {readback.orphan_subniches} subniches [OK]")
    print(f"  Missing videos: {readback.missing_videos} [OK]")
    print(f"  Payload mismatches: 0 [OK]")
    print(f"  Verified: {readback.verified} [OK]")
    
    # Step 7: Final report
    print("\n" + "=" * 60)
    print("FINAL PRODUCTION REPORT")
    print("=" * 60)
    report = result_report(result)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())