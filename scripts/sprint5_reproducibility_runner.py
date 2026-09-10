"""Run the clean, non-persisting Sprint 5 reproducibility preflight."""

import argparse
import hashlib
import json
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
from app.analytics.semantic_provider import TFIDFLocalSemanticProvider
from app.analytics.text_normalizer import clean_text_for_embedding
from app.database.repositories import YouTubeRepository
from app.models.niche import NicheCluster, NicheMiningResult

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

# Approved production values from the final preflight run
APPROVED_SILHOUETTE = 0.06862934221732106
APPROVED_DATASET_HASH = "5b284b89e17d11aca86661bd8a53715b43b212f6f5aaf99ca4210884b5925091"
APPROVED_ASSIGNMENTS_HASH = "d03cb6bd13b72e8f6859ec0f6c2ea1104f59799f6480d81d95b3df5bca751340"
APPROVED_PRODUCTION_VIDEOS = 7611
APPROVED_CLUSTERS = 10

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


def validate_production_dataset(
    rows: List[Dict[str, str]],
    expected_hash: Optional[str] = None,
) -> str:
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
    dataset_hash = compute_dataset_hash(rows)
    if expected_hash is not None and dataset_hash != expected_hash:
        raise ValueError(
            f"Production dataset hash mismatch: got {dataset_hash}, expected {expected_hash}"
        )
    return dataset_hash


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


def build_preflight_result(
    rows: List[Dict[str, str]],
    dataset_hash: str,
    channel_count: int,
    audit: Dict[str, Any],
    labels: np.ndarray,
    silhouette: float,
    assignments_hash: str,
) -> NicheMiningResult:
    started_at = time.time()
    clusters: List[NicheCluster] = []
    for cluster_id in range(APPROVED_K):
        cluster_rows = [
            row for row, label in zip(rows, labels) if int(label) == cluster_id
        ]
        clusters.append(
            NicheCluster(
                cluster_id=cluster_id,
                video_ids=[row["video_id"] for row in cluster_rows],
                video_count=len(cluster_rows),
                unique_channels=len(
                    {row["channel_id"] for row in cluster_rows if row["channel_id"]}
                ),
                representative_titles=[row["title"] for row in cluster_rows[:5]],
                semantic_quality=silhouette,
            )
        )

    if len(clusters) != APPROVED_K or any(not cluster.video_ids for cluster in clusters):
        raise ValueError("Clean preflight must produce exactly 10 non-empty clusters.")
    if sum(cluster.video_count for cluster in clusters) != len(rows):
        raise ValueError("Cluster video counts do not match the production dataset.")

    created_at = datetime.now(timezone.utc).isoformat()
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
        run_id=f"sprint5_clean_preflight_{assignments_hash[:12]}_{uuid.uuid4().hex[:8]}",
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


def run_preflight(
    repository: Optional[YouTubeRepository] = None,
) -> NicheMiningResult:
    rows, dataset_hash, channel_count, audit = load_clean_dataset(repository)
    labels, silhouette, assignments_hash = cluster_clean_dataset(rows)
    return build_preflight_result(
        rows,
        dataset_hash,
        channel_count,
        audit,
        labels,
        silhouette,
        assignments_hash,
    )


def run_approved_final(
    repository: Optional[YouTubeRepository] = None,
    outlier_engine: Optional[Any] = None,
) -> NicheMiningResult:
    del outlier_engine
    return run_preflight(repository=repository)


def result_report(result: NicheMiningResult) -> Dict[str, Any]:
    audit = result.parameters["data_audit"]
    return {
        "mode": "preflight",
        "persisted": False,
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
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run the clean Sprint 5 preflight without persistence.",
    )
    parser.parse_args()
    print(
        json.dumps(
            result_report(run_preflight()),
            ensure_ascii=True,
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
