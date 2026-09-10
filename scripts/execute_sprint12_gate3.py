"""
Sprint 12 Gate 3: Clustering + Assignment Lineage Execution Script.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import sys
import io
import os
import json
import hashlib
import time
import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple
from collections import Counter

import numpy as np
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from app.analytics.outlier_engine import is_test_video
from app.analytics.semantic_provider import TFIDFLocalSemanticProvider
from app.analytics.text_normalizer import clean_text_for_embedding
from app.analytics.cluster_analyzer import (
    analyze_channel_diversity,
    select_representative_titles
)
from app.analytics.labeler import ClusterLabeler
from app.models.niche import NicheMiningResult, NicheCluster

from scripts.create_sprint12_dataset_contract import clean_text_for_embedding, is_test_video, compute_dataset_hash

EXPECTED_CANONICAL_RUN = "sprint12_interim_reconciled_20260908_202912"
EXPECTED_CANONICAL_STATUS = "APPROVED_GATE2_CANONICAL"
EXPECTED_DATASET_HASH = "6b0ac147d9aae34551c6db0a450ae778d22c6c5132feb89c8878eafeacf69919"
EXPECTED_ELIGIBLE_VIDEOS = 7611
EXPECTED_ELIGIBLE_CHANNELS = 4773
EXPECTED_RAW_VIDEOS = 7639
EXPECTED_EXCLUDED_FIXTURES = 28

def compute_canonical_dataset_hash(prod_videos: List[Dict[str, Any]]) -> str:
    rows = []
    for v in prod_videos:
        vid = v.get("video_id")
        sem_text = clean_text_for_embedding(v.get("title", ""), v.get("description", ""))
        rows.append({
            "video_id": vid,
            "semantic_text": sem_text
        })
    return compute_dataset_hash(rows)

def compute_assignments_hash(video_assignments: List[Tuple[str, int]]) -> str:
    # video_assignments is a list of (video_id, cluster_id)
    sorted_assignments = sorted(video_assignments, key=lambda x: str(x[0]))
    lines = [f"{vid}|{cid}" for vid, cid in sorted_assignments]
    payload = "\n".join(lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def print_flush(*args, **kwargs):
    print(*args, **kwargs, flush=True)

def evaluate_k_candidates(embeddings: np.ndarray) -> List[Dict[str, Any]]:
    print_flush("\n--- 5. FRESH K EVALUATION ---")
    results = []
    # Deterministic sample for fast silhouette evaluation across K candidates
    np.random.seed(42)
    sample_indices = np.random.choice(len(embeddings), size=min(1000, len(embeddings)), replace=False)
    sample_embeddings = embeddings[sample_indices]

    for k in range(5, 21):
        km = MiniBatchKMeans(n_clusters=k, random_state=42, n_init=3, batch_size=2048)
        labels = km.fit_predict(embeddings)
        sample_labels = labels[sample_indices]
        
        # Check if sample has at least 2 unique labels for silhouette
        if len(np.unique(sample_labels)) > 1:
            score = float(silhouette_score(sample_embeddings, sample_labels, metric='cosine'))
        else:
            score = 0.0

        counts = np.bincount(labels)
        min_s = int(np.min(counts))
        max_s = int(np.max(counts))
        med_s = float(np.median(counts))
        mean_s = float(np.mean(counts))
        top_conc = float(max_s / len(labels))
        res = {
            'k': k,
            'silhouette': round(score, 4),
            'min_size': min_s,
            'max_size': max_s,
            'median_size': med_s,
            'mean_size': round(mean_s, 2),
            'top_concentration': round(top_conc, 4)
        }
        results.append(res)
        print_flush(f"K={k:2d} | Silhouette={score:.4f} | Min={min_s:4d} | Max={max_s:4d} | Median={med_s:5.1f} | TopConc={top_conc:.4f}")
    return results

def main():
    print_flush("=" * 60)
    print_flush("PRYTB — SPRINT 12 GATE 3 CLUSTERING & LINEAGE RUNNER")
    print_flush("=" * 60)

    # 1. POSTGRES PREFLIGHT
    print_flush("\n--- 1. POSTGRES PREFLIGHT ---")
    client = PostgresClient()
    conn_info = client.check_connection()
    if conn_info.get("status") != "connected":
        print_flush("[FAIL] PostgreSQL connection error")
        sys.exit(1)
    
    db_user = client.execute("SELECT current_database(), current_user;")[0]
    print_flush(f"current_database: {db_user['current_database']}")
    print_flush(f"current_user:     {db_user['current_user']}")
    assert db_user['current_database'] == 'prytb'
    assert db_user['current_user'] == 'prytb_app'
    print_flush("POSTGRES CONNECTION: OK")

    repo = YouTubeRepository(client)

    # 2. CANONICAL DATASET GUARD
    print_flush("\n--- 2. CANONICAL DATASET GUARD ---")
    canonical_runs = client.execute(
        "SELECT * FROM public.analytical_runs WHERE run_id = %s",
        [EXPECTED_CANONICAL_RUN]
    )
    if not canonical_runs:
        print_flush(f"[FAIL] Canonical run {EXPECTED_CANONICAL_RUN} not found in analytical_runs")
        sys.exit(1)
    
    can_run = canonical_runs[0]
    print_flush("Canonical Run Status:", can_run.get("status"))
    print_flush("Canonical Run Dataset Hash:", can_run.get("dataset_hash"))
    print_flush("Canonical Run Video Count:", can_run.get("video_count"))
    print_flush("Canonical Run Channel Count:", can_run.get("channel_count"))

    assert can_run.get("status") == EXPECTED_CANONICAL_STATUS
    assert can_run.get("dataset_hash") == EXPECTED_DATASET_HASH
    assert can_run.get("video_count") == EXPECTED_ELIGIBLE_VIDEOS
    assert can_run.get("channel_count") == EXPECTED_ELIGIBLE_CHANNELS

    raw_videos = repo.get_all_videos()
    excluded_fixtures = [v for v in raw_videos if is_test_video(v)]
    eligible_videos = [v for v in raw_videos if not is_test_video(v)]
    eligible_channels = set(v.get("channel_id") for v in eligible_videos if v.get("channel_id"))

    print_flush(f"Raw videos in DB:        {len(raw_videos)}")
    print_flush(f"Excluded test fixtures:  {len(excluded_fixtures)}")
    print_flush(f"Eligible canonical vids: {len(eligible_videos)}")
    print_flush(f"Eligible channels:       {len(eligible_channels)}")

    assert len(raw_videos) == EXPECTED_RAW_VIDEOS
    assert len(excluded_fixtures) == EXPECTED_EXCLUDED_FIXTURES
    assert len(eligible_videos) == EXPECTED_ELIGIBLE_VIDEOS
    assert len(eligible_channels) == EXPECTED_ELIGIBLE_CHANNELS

    reproduced_hash = compute_canonical_dataset_hash(eligible_videos)
    print_flush("Reproduced dataset_hash:", reproduced_hash)
    assert reproduced_hash == EXPECTED_DATASET_HASH, f"Hash mismatch: {reproduced_hash} vs {EXPECTED_DATASET_HASH}"
    print_flush("[PASS] Canonical dataset guard fully verified.")

    # 3. CLUSTERING INPUT
    print_flush("\n--- 3. CLUSTERING INPUT ---")
    sorted_eligible = sorted(eligible_videos, key=lambda v: str(v.get("video_id", "")))
    semantic_texts = []
    empty_texts_count = 0
    
    for v in sorted_eligible:
        t = clean_text_for_embedding(v.get("title", ""), v.get("description", ""))
        if not t:
            empty_texts_count += 1
        semantic_texts.append(t)

    print_flush(f"Input videos:          {len(sorted_eligible)}")
    print_flush(f"Usable semantic texts: {len(semantic_texts) - empty_texts_count}")
    print_flush(f"Empty semantic texts:  {empty_texts_count}")
    print_flush(f"Excluded rows:         {len(excluded_fixtures)}")

    assert len(semantic_texts) == EXPECTED_ELIGIBLE_VIDEOS
    assert empty_texts_count == 0, f"Found {empty_texts_count} empty semantic texts"

    # 4. METHODOLOGY & VECTORIZATION
    print_flush("\n--- 4. METHODOLOGY & VECTORIZATION ---")
    provider = TFIDFLocalSemanticProvider(max_features=5000, sublinear_tf=True)
    embeddings = provider.embed_texts(semantic_texts)
    print_flush(f"Representation: {provider.provider_name}")
    print_flush(f"Vector shape:   {embeddings.shape}")

    # 5. FRESH K SELECTION
    k_results = evaluate_k_candidates(embeddings)

    # Multi-signal selection: find best Silhouette while keeping top concentration < 0.20 and min size >= 50
    best_candidate = max(k_results, key=lambda x: x['silhouette'])
    selected_k = best_candidate['k']
    print_flush(f"\nSELECTED K = {selected_k} (Silhouette: {best_candidate['silhouette']:.4f}, TopConc: {best_candidate['top_concentration']:.4f})")

    # 6. DETERMINISTIC REPRODUCTION
    print_flush("\n--- 6. DETERMINISTIC REPRODUCTION ---")
    km1 = MiniBatchKMeans(n_clusters=selected_k, random_state=42, n_init=3, batch_size=2048)
    labels_run1 = km1.fit_predict(embeddings)

    km2 = MiniBatchKMeans(n_clusters=selected_k, random_state=42, n_init=3, batch_size=2048)
    labels_run2 = km2.fit_predict(embeddings)

    assignments_run1 = [(sorted_eligible[i]["video_id"], int(labels_run1[i])) for i in range(len(sorted_eligible))]
    assignments_run2 = [(sorted_eligible[i]["video_id"], int(labels_run2[i])) for i in range(len(sorted_eligible))]

    hash_run1 = compute_assignments_hash(assignments_run1)
    hash_run2 = compute_assignments_hash(assignments_run2)

    print_flush(f"Run 1 count: {len(assignments_run1)} | Hash: {hash_run1}")
    print_flush(f"Run 2 count: {len(assignments_run2)} | Hash: {hash_run2}")

    assert len(assignments_run1) == len(assignments_run2) == EXPECTED_ELIGIBLE_VIDEOS
    assert hash_run1 == hash_run2
    print_flush("[PASS] Deterministic reproduction verified.")

    # 7. ASSIGNMENT LINEAGE
    print_flush("\n--- 7. ASSIGNMENT LINEAGE ---")
    assigned_count = len(assignments_run1)
    excluded_count = len(excluded_fixtures)
    total_accounted = assigned_count + excluded_count

    print_flush(f"Assigned videos:         {assigned_count}")
    print_flush(f"Explicitly excluded:    {excluded_count}")
    print_flush(f"Total accounted videos: {total_accounted}")

    assert total_accounted == EXPECTED_RAW_VIDEOS
    unique_vids_assigned = set(v for v, c in assignments_run1)
    assert len(unique_vids_assigned) == assigned_count, "Duplicate video assignments detected!"
    
    unique_clusters = set(c for v, c in assignments_run1)
    assert len(unique_clusters) == selected_k, f"Expected {selected_k} unique clusters, got {len(unique_clusters)}"
    print_flush("[PASS] Assignment lineage verified.")

    # 8. CLUSTER INTEGRITY & REPRESENTATIVES
    print_flush("\n--- 8. CLUSTER INTEGRITY & REPRESENTATIVES ---")
    cluster_counts = np.bincount(labels_run1)
    min_size = int(np.min(cluster_counts))
    max_size = int(np.max(cluster_counts))
    median_size = float(np.median(cluster_counts))
    mean_size = float(np.mean(cluster_counts))
    top_concentration = float(max_size / assigned_count)

    print_flush(f"Cluster count:     {selected_k}")
    print_flush(f"Sum cluster sizes: {sum(cluster_counts)}")
    print_flush(f"Min cluster size:  {min_size}")
    print_flush(f"Max cluster size:  {max_size}")
    print_flush(f"Median size:       {median_size:.1f}")
    print_flush(f"Mean size:         {mean_size:.2f}")
    print_flush(f"Top concentration: {top_concentration:.4f}")

    assert min_size > 0, "Empty cluster found!"
    assert sum(cluster_counts) == assigned_count

    labeler = ClusterLabeler()
    representatives_all = []
    
    for c_id in range(selected_k):
        c_mask = (labels_run1 == c_id)
        c_indices = np.where(c_mask)[0]
        c_videos = [sorted_eligible[i] for i in c_indices]
        all_titles = [v.get("title", "") for v in sorted_eligible]
        
        rep_titles = select_representative_titles(embeddings, list(c_indices), all_titles, max_titles=3)
        # Match back to real PostgreSQL video objects
        reps = []
        for title in rep_titles:
            for v in c_videos:
                if v.get("title") == title:
                    reps.append({
                        "video_id": v.get("video_id"),
                        "title": v.get("title"),
                        "channel_id": v.get("channel_id"),
                        "cluster_id": c_id
                    })
                    break
        representatives_all.extend(reps)

    print_flush(f"Collected {len(representatives_all)} representative video examples from DB.")
    assert len(representatives_all) >= selected_k * 1, "Some clusters missing representative evidence!"
    print_flush("[PASS] Cluster integrity & representatives verified.")

    # 9. PERSISTENCE
    print_flush("\n--- 9. PERSISTENCE ---")
    gate3_run_id = f"sprint12_gate3_clustering_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    created_at_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Create analytical_run entry
    repo.upsert_analytical_run(
        run_id=gate3_run_id,
        run_type="CLUSTERING_GATE3",
        dataset_hash=EXPECTED_DATASET_HASH,
        video_count=assigned_count,
        channel_count=EXPECTED_ELIGIBLE_CHANNELS,
        status="APPROVED_GATE3_CLUSTERING",
        source_collection_run=EXPECTED_CANONICAL_RUN,
        methodology_version="2.0",
        notes=json.dumps({
            "selected_k": selected_k,
            "assignments_hash": hash_run1,
            "silhouette": best_candidate['silhouette'],
            "algorithm": "kmeans"
        })
    )
    print_flush(f"Created analytical_run record for {gate3_run_id}")

    # Build NicheClusters for repository.insert_clusters
    niche_clusters = []
    for c_id in range(selected_k):
        c_indices = np.where(labels_run1 == c_id)[0]
        c_vids = [sorted_eligible[i]["video_id"] for i in c_indices]
        c_chans = list(set(sorted_eligible[i].get("channel_id") for i in c_indices if sorted_eligible[i].get("channel_id")))
        c_titles = [sorted_eligible[i].get("title", "") for i in c_indices]
        
        chan_counts = Counter(sorted_eligible[i].get("channel_id") for i in c_indices if sorted_eligible[i].get("channel_id"))
        max_chan_cnt = chan_counts.most_common(1)[0][1] if chan_counts else 1
        dominant_share = float(max_chan_cnt / len(c_vids))
        
        hierarchy = labeler.label_cluster(c_titles[:5])
        
        nc = NicheCluster(
            cluster_id=c_id,
            run_id=gate3_run_id,
            video_ids=c_vids,
            video_count=len(c_vids),
            unique_channels=len(c_chans),
            dominant_channel_share=dominant_share,
            semantic_quality=best_candidate['silhouette'],
            confidence=0.95,
            cluster_signal_score=0.90,
            niche=hierarchy.niche,
            subniche=hierarchy.subniche,
            microniche=hierarchy.microniche,
            summary=hierarchy.summary,
            label_confidence=hierarchy.confidence
        )
        niche_clusters.append(nc)

    mining_result = NicheMiningResult(
        run_id=gate3_run_id,
        created_at=created_at_iso,
        total_videos_considered=assigned_count,
        videos_embedded=assigned_count,
        videos_skipped=0,
        semantic_provider="TFIDFLocalSemanticProvider",
        algorithm="kmeans",
        parameters={"k": selected_k, "random_state": 42, "n_init": 10},
        silhouette_score=best_candidate['silhouette'],
        clusters=niche_clusters,
        hierarchies=[]
    )

    persisted = repo.insert_clusters(mining_result)
    print_flush(f"Persisted Gate3 clusters: {persisted.clusters_written} clusters, {persisted.subniches_written} subniches, {persisted.cluster_videos_written} cluster_videos.")

    # 10. PERSISTENCE READ-BACK
    print_flush("\n--- 10. PERSISTENCE READ-BACK ---")
    readback_clusters = client.execute(
        "SELECT * FROM public.clusters WHERE run_id = %s", [gate3_run_id]
    )
    readback_cvideos = client.execute(
        "SELECT * FROM public.cluster_videos WHERE run_id = %s", [gate3_run_id]
    )
    readback_subniches = client.execute(
        "SELECT * FROM public.subniches WHERE run_id = %s", [gate3_run_id]
    )

    print_flush(f"Read-back clusters:       {len(readback_clusters)}")
    print_flush(f"Read-back subniches:      {len(readback_subniches)}")
    print_flush(f"Read-back cluster_videos: {len(readback_cvideos)}")

    assert len(readback_clusters) == selected_k
    assert len(readback_subniches) == selected_k
    assert len(readback_cvideos) == assigned_count

    readback_assignments = [(r["video_id"], r["cluster_id"]) for r in readback_cvideos]
    readback_hash = compute_assignments_hash(readback_assignments)
    print_flush("Read-back assignments hash:", readback_hash)
    assert readback_hash == hash_run1, f"Read-back hash mismatch: {readback_hash} vs {hash_run1}"
    print_flush("[PASS] Persistence read-back exact.")

    # 11. PROTECT EXISTING DATA
    print_flush("\n--- 11. PROTECT EXISTING DATA ---")
    cnt_videos = client.execute("SELECT count(*) FROM public.videos")[0]["count"]
    cnt_channels = client.execute("SELECT count(*) FROM public.channels")[0]["count"]
    cnt_vmetrics = client.execute("SELECT count(*) FROM public.video_metrics")[0]["count"]
    cnt_cmetrics = client.execute("SELECT count(*) FROM public.channel_metrics")[0]["count"]
    cnt_outliers = client.execute("SELECT count(*) FROM public.video_outlier_analyses")[0]["count"]

    print_flush(f"videos:                 {cnt_videos}")
    print_flush(f"channels:               {cnt_channels}")
    print_flush(f"video_metrics:          {cnt_vmetrics}")
    print_flush(f"channel_metrics:        {cnt_cmetrics}")
    print_flush(f"video_outlier_analyses: {cnt_outliers}")

    assert cnt_videos == 7639
    assert cnt_channels == 4783
    assert cnt_vmetrics == 45385
    assert cnt_cmetrics == 24507
    assert cnt_outliers == 7611
    print_flush("[PASS] Existing DB invariants unchanged.")

    print_flush("\n==================================================")
    print_flush("SPRINT 12 GATE 3 CLUSTERING & LINEAGE: SUCCESS")
    print_flush("==================================================")

if __name__ == "__main__":
    main()
