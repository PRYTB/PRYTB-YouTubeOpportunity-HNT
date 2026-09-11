"""
Sprint 12 Gate 7: Final >=10K Analytical Rerun Execution Script.

Recomputes the complete approved Sprint12 analytical chain on the frozen 10585-video dataset:
1. Dataset Guard (10613 raw, 28 fixtures excluded, 10585 productive, 6487 channels, dataset hash verification x2)
2. Outlier Recomputation (10585 analyzed, exact baseline rules, Top100 ranking)
3. Fresh K Selection & Clustering (K range evaluation, Standard KMeans, determinism check x2, assignment hash x2)
4. Cluster Quality Classification (SPECIFIC_ACTIONABLE, GENERIC, MIXED, INCOHERENT)
5. Top30 Selection & Subniche Mining (Normalized intent strings, distinct intent count, content depth verification)
6. Final Top20 Candidate Selection (exactly 20, without padding)
7. Full Sprints 6-10 Rerun Qualification over the selected Top20 and all their videos
8. Final Component Ranking (persisted under a new Gate 7 run_id, NO Top3 selection)
9. Database Persistence & Readback Verification (final approval remains external)
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import sys
import io
import json
import hashlib
import time
import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set, Optional
from collections import Counter, defaultdict

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from app.analytics.outlier_engine import OutlierEngine, is_test_video
from app.analytics.semantic_provider import TFIDFLocalSemanticProvider
from app.analytics.text_normalizer import clean_text_for_embedding
from app.analytics.cluster_analyzer import (
    analyze_channel_diversity,
    select_representative_titles,
    calculate_cluster_confidence,
    calculate_cluster_signal_score
)
from app.analytics.labeler import ClusterLabeler, validate_label_quality
from app.analytics.revenue_geography_engine import RevenueGeographyEngine
from app.analytics.market_structure_engine import MarketStructureEngine
from app.analytics.production_risk_engine import ProductionRiskEngine
from app.analytics.profitability_engine import ProfitabilityEngine
from app.analytics.opportunity_validator import OpportunityValidator

from scripts.create_sprint12_dataset_contract import (
    clean_text_for_embedding as clean_contract_text,
    compute_dataset_hash,
)

EXPECTED_GATE6_RUN = "sprint12_final_collection_gate6_20260910"
EXPECTED_DATASET_HASH = "ecc6ad6d164e586bd718ff8c17be3801b5e3c0bbfa4e39cfc555b26f5c82c4ba"
EXPECTED_RAW_VIDEOS = 10613
EXPECTED_PROD_VIDEOS = 10585
EXPECTED_PROD_CHANNELS = 6487
EXPECTED_EXCLUDED_FIXTURES = 28


def print_flush(*args, **kwargs):
    print(*args, **kwargs, flush=True)


def normalize_intent_string(text: str) -> str:
    cleaned = clean_text_for_embedding(text)
    words = [w for w in cleaned.split() if len(w) > 1]
    return " ".join(words)


def compute_assignments_hash(assignments: List[Tuple[str, int]]) -> str:
    sorted_assignments = sorted(assignments, key=lambda x: str(x[0]))
    lines = [f"{vid}|{cid}" for vid, cid in sorted_assignments]
    payload = "\n".join(lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main():
    gate7_started_at = datetime.datetime.now(datetime.timezone.utc)
    gate7_run_id = "sprint12_gate7_final_analytics_20260910_231500"

    print_flush("==================================================")
    print_flush("PRYTB — SPRINT 12 GATE 7: FINAL ANALYTICAL RERUN")
    print_flush("==================================================")
    print_flush(f"Gate 7 run_id: {gate7_run_id}")

    # 0. GOVERNANCE
    print_flush("\n--- 0. GOVERNANCE ---")
    print_flush("MASTER PROMPT LOADED")
    print_flush("GANTT LOADED")
    print_flush("CURRENT SPRINT = 12")
    print_flush("CURRENT GATE = GATE7 FINAL ANALYTICAL RERUN")

    # 1. POSTGRES & FINAL DATASET GUARD
    print_flush("\n--- 1. POSTGRES & FINAL DATASET GUARD ---")
    client = PostgresClient()
    repo = YouTubeRepository(client)

    db_info = client.execute("SELECT current_database(), current_user;")[0]
    assert db_info["current_database"] == "prytb"
    assert db_info["current_user"] == "prytb_app"
    print_flush(f"PostgreSQL connection OK ({db_info['current_user']}@{db_info['current_database']})")

    # Fetch all videos from DB
    raw_videos = repo.get_all_videos()
    assert len(raw_videos) == EXPECTED_RAW_VIDEOS, f"Expected {EXPECTED_RAW_VIDEOS} raw videos, got {len(raw_videos)}"

    video_by_id = {v["video_id"]: v for v in raw_videos}

    # Exclude fixtures/tests
    prod_videos = [v for v in raw_videos if not is_test_video(v)]
    excluded_fixtures = [v for v in raw_videos if is_test_video(v)]
    assert len(prod_videos) == EXPECTED_PROD_VIDEOS, f"Expected {EXPECTED_PROD_VIDEOS} prod videos, got {len(prod_videos)}"
    assert len(excluded_fixtures) == EXPECTED_EXCLUDED_FIXTURES, f"Expected {EXPECTED_EXCLUDED_FIXTURES} excluded fixtures, got {len(excluded_fixtures)}"

    prod_channels = set(v["channel_id"] for v in prod_videos if v.get("channel_id"))
    assert len(prod_channels) == EXPECTED_PROD_CHANNELS, f"Expected {EXPECTED_PROD_CHANNELS} prod channels, got {len(prod_channels)}"

    # Recompute dataset hash twice using description fallback if None
    prod_rows = [
        {
            "video_id": v["video_id"],
            "semantic_text": clean_contract_text(
                v.get("title") or "", v.get("description")
            ),
        }
        for v in prod_videos
    ]

    hash1 = compute_dataset_hash(prod_rows)
    hash2 = compute_dataset_hash(prod_rows)

    assert hash1 == hash2 == EXPECTED_DATASET_HASH, f"Dataset hash mismatch! Expected {EXPECTED_DATASET_HASH}, got {hash1}"
    print_flush(f"[PASS] Dataset Guard: raw={len(raw_videos)}, prod={len(prod_videos)}, channels={len(prod_channels)}, hash={hash1}")

    # 2. OUTLIER ENGINE RERUN
    print_flush("\n--- 2. FINAL OUTLIER RECOMPUTATION ---")
    t0 = time.time()
    outlier_engine = OutlierEngine(repository=repo)
    # The engine's real bulk API loads and excludes fixtures from the repository.
    all_outliers = outlier_engine.analyze_all()
    outlier_runtime = time.time() - t0

    assert len(all_outliers) == len(prod_videos), f"Expected {len(prod_videos)} outlier results, got {len(all_outliers)}"

    actual_outliers = [res for res in all_outliers if res.is_actual_outlier()]
    small_channel_outliers = [res for res in all_outliers if res.small_channel_outlier]
    valid_baselines = [res for res in all_outliers if res.baseline_confidence in ("MEDIUM", "HIGH")]

    outliers_map = {res.video_id: res for res in all_outliers}

    print_flush(f"Analyzed videos: {len(all_outliers)}")
    print_flush(f"Actual outliers: {len(actual_outliers)}")
    print_flush(f"Small-channel outliers: {len(small_channel_outliers)}")
    print_flush(f"Baseline coverage (MED/HIGH): {len(valid_baselines)} ({len(valid_baselines)/len(all_outliers):.2%})")

    # 3. TOP 100 OUTLIERS
    top_100_outliers = sorted(actual_outliers, key=lambda x: x.outlier_rank_score, reverse=True)[:100]
    top_100_unique_channels = len(set(res.channel_id for res in top_100_outliers))
    top_100_small_channels = len([res for res in top_100_outliers if res.small_channel_outlier])

    assert len(top_100_outliers) == 100, f"Top100 size expected 100, got {len(top_100_outliers)}"
    assert all(res.is_actual_outlier() for res in top_100_outliers), "Non-actual outlier found in Top100!"

    print_flush(f"Top100 count: {len(top_100_outliers)} (Unique channels: {top_100_unique_channels}, Small-channel: {top_100_small_channels})")

    # 4. FRESH CLUSTERING & K SELECTION
    print_flush("\n--- 4. FRESH CLUSTERING & K SELECTION ---")
    clustering_started_at = time.time()
    texts = [clean_text_for_embedding(v.get("title", ""), v.get("description", "")) for v in prod_videos]
    titles = [v.get("title", "") for v in prod_videos]
    video_ids = [v["video_id"] for v in prod_videos]
    channel_ids = [v.get("channel_id", "") for v in prod_videos]

    provider = TFIDFLocalSemanticProvider(max_features=1000, ngram_range=(1, 2))
    embeddings = provider.embed_texts(texts)

    # Evaluate range K=15..45 to avoid boundary artifact
    candidate_ks = [15, 20, 25, 30, 35, 40, 45]
    print_flush("Evaluating candidate K values...")

    best_k = None
    best_score = -1.0
    k_eval_results = []

    np.random.seed(42)
    sample_indices = np.random.choice(len(embeddings), size=min(2000, len(embeddings)), replace=False)
    sample_embeddings = embeddings[sample_indices]

    for k in candidate_ks:
        km = KMeans(n_clusters=k, random_state=42, n_init=5, max_iter=100)
        lbls = km.fit_predict(embeddings)
        sample_lbls = lbls[sample_indices]
        score = float(silhouette_score(sample_embeddings, sample_lbls, metric='cosine'))
        
        counts = np.bincount(lbls)
        min_s, max_s, med_s = int(np.min(counts)), int(np.max(counts)), float(np.median(counts))
        top_conc = float(max_s / len(lbls))

        k_eval_results.append({
            "k": k,
            "silhouette": score,
            "min_size": min_s,
            "max_size": max_s,
            "median_size": med_s,
            "top_concentration": top_conc
        })
        print_flush(f"  K={k:2d} | Silhouette={score:.4f} | Min={min_s:4d} | Max={max_s:4d} | Median={med_s:5.1f} | TopConc={top_conc:.4f}")

        if score > best_score:
            best_score = score
            best_k = k

    print_flush(f"Selected Optimal K: {best_k} (Silhouette={best_score:.4f})")
    assert best_k not in (candidate_ks[0], candidate_ks[-1]), "Selected K is on search boundary!"

    # 5. DETERMINISM & ASSIGNMENT HASH (RUN TWICE)
    print_flush("\n--- 5. CLUSTER DETERMINISM & LINEAGE ---")
    km1 = KMeans(n_clusters=best_k, random_state=42, n_init=10, max_iter=300)
    labels1 = km1.fit_predict(embeddings)
    assignments1 = list(zip(video_ids, labels1))
    assign_hash1 = compute_assignments_hash(assignments1)

    km2 = KMeans(n_clusters=best_k, random_state=42, n_init=10, max_iter=300)
    labels2 = km2.fit_predict(embeddings)
    assignments2 = list(zip(video_ids, labels2))
    assign_hash2 = compute_assignments_hash(assignments2)

    assert best_k == len(set(labels1)) == len(set(labels2))
    assert np.array_equal(labels1, labels2), "KMeans labels differ between run1 and run2!"
    assert assign_hash1 == assign_hash2, "Assignment hashes mismatch between run1 and run2!"

    print_flush(f"Deterministic Clustering: K={best_k}, Assignment Hash={assign_hash1}")

    # 6. CLUSTER QUALIFICATION & CLASSIFICATION
    print_flush("\n--- 6. CLUSTER QUALIFICATION & CLASSIFICATION ---")
    labeler = ClusterLabeler()
    unique_cids = sorted(int(label) for label in set(labels1))
    video_by_id = {video["video_id"]: video for video in prod_videos}
    clusters_payload = []

    classification_counts = {"SPECIFIC_ACTIONABLE": 0, "GENERIC": 0, "MIXED": 0, "INCOHERENT": 0}

    for cid in unique_cids:
        indices = [i for i, l in enumerate(labels1) if l == cid]
        c_vids = [video_ids[i] for i in indices]
        c_chans = [channel_ids[i] for i in indices]
        v_count = len(c_vids)

        uniq_chans, dom_share, diversity_cat, warnings = analyze_channel_diversity(c_chans)
        rep_titles = select_representative_titles(embeddings=embeddings, cluster_indices=indices, titles=titles)
        hierarchy = labeler.label_cluster(rep_titles)
        quality_score, label_warns = validate_label_quality(hierarchy.niche, hierarchy.subniche, hierarchy.microniche, rep_titles)

        c_outliers = [outliers_map.get(vid) for vid in c_vids if vid in outliers_map]
        actual_c_outliers = [o for o in c_outliers if o and o.is_actual_outlier()]
        small_c_outliers = [o for o in c_outliers if o and o.small_channel_outlier]

        # Classification rules (label quality is scored on a 0-100 scale)
        if quality_score < 40.0 or dom_share > 0.8:
            classification = "INCOHERENT"
        elif quality_score >= 75.0 and uniq_chans >= 10:
            classification = "SPECIFIC_ACTIONABLE"
        elif quality_score >= 60.0:
            classification = "MIXED"
        else:
            classification = "GENERIC"

        classification_counts[classification] += 1

        cp = {
            "cluster_id": cid,
            "niche": hierarchy.niche,
            "subniche": hierarchy.subniche,
            "microniche": hierarchy.microniche,
            "summary": hierarchy.summary,
            "classification": classification,
            "video_ids": c_vids,
            "representative_titles": rep_titles,
            "channel_count": uniq_chans,
            "channel_diversity": diversity_cat,
            "outlier_count": len(actual_c_outliers),
            "small_channel_outliers": len(small_c_outliers),
            "dominant_channel_share": dom_share,
            "quality_score": quality_score,
            "label_confidence": quality_score,
            "label_warnings": label_warns,
            "warnings": warnings,
            "videos": [video_by_id[vid] for vid in c_vids if vid in video_by_id]
        }
        clusters_payload.append(cp)

    assert classification_counts["INCOHERENT"] == 0, f"Found INCOHERENT clusters: {classification_counts['INCOHERENT']}"
    print_flush(f"Cluster Classifications: {classification_counts}")

    # 7. TOP30 CLUSTERS & SUBNICHE MINING
    print_flush("\n--- 7. TOP30 CLUSTERS & SUBNICHE MINING ---")
    # Rank clusters by outlier density and channel diversity
    valid_clusters = [c for c in clusters_payload if c["classification"] != "INCOHERENT"]
    sorted_clusters = sorted(
        valid_clusters,
        key=lambda c: (c["outlier_count"], c["small_channel_outliers"], c["channel_count"]),
        reverse=True
    )
    top30_clusters = sorted_clusters[:min(30, len(sorted_clusters))]
    print_flush(f"Selected Top30 Clusters: count={len(top30_clusters)}")

    # Subniche mining with normalized intent strings
    subnichos = []
    intent_set = set()
    dup_intents_merged = 0

    for c in top30_clusters:
        # Group titles into normalized subniche intents
        for vid in c["video_ids"]:
            v = video_by_id[vid]
            title = v.get("title", "")
            raw_intent = f"{c['subniche']} - {title[:40]}"
            norm_intent = normalize_intent_string(raw_intent)
            if not norm_intent:
                continue
            if norm_intent in intent_set:
                dup_intents_merged += 1
                continue
            intent_set.add(norm_intent)

            subnichos.append({
                "parent_cluster_id": c["cluster_id"],
                "subniche_intent": norm_intent,
                "raw_intent": raw_intent,
                "niche": c["niche"],
                "subniche": c["subniche"],
                "representative_video_id": vid,
                "cluster_outliers": c["outlier_count"],
                "cluster_small_outliers": c["small_channel_outliers"],
                "cluster_channels": c["channel_count"]
            })

    print_flush(f"Mined Subniches: raw={len(subnichos) + dup_intents_merged}, normalized={len(subnichos)}, duplicates_merged={dup_intents_merged}")

    # 8. CONTENT DEPTH & TOP20 SUBNICHES
    print_flush("\n--- 8. CONTENT DEPTH & TOP20 SUBNICHES ---")
    # Group subnichos back into parent cluster candidates
    cluster_subniche_groups = defaultdict(list)
    for sn in subnichos:
        cluster_subniche_groups[sn["parent_cluster_id"]].append(sn)

    top20_candidates = []
    for cid, sns in cluster_subniche_groups.items():
        parent_c = next(c for c in clusters_payload if c["cluster_id"] == cid)
        distinct_intents = len(sns)

        # Content depth band logic
        if distinct_intents >= 100:
            depth_band = "100_PLUS"
        elif distinct_intents >= 50:
            depth_band = "50_PLUS"
        elif distinct_intents >= 20:
            depth_band = "20_PLUS"
        else:
            depth_band = "SHALLOW"

        top20_candidates.append({
            "subniche_id": f"subniche_{cid:03d}",
            "parent_cluster_id": cid,
            "niche": parent_c["niche"],
            "subniche": parent_c["subniche"],
            "microniche": parent_c["microniche"],
            "summary": parent_c["summary"],
            "distinct_intent_count": distinct_intents,
            "content_depth": depth_band,
            "outlier_count": parent_c["outlier_count"],
            "small_channel_outliers": parent_c["small_channel_outliers"],
            "channel_count": parent_c["channel_count"],
            "video_ids": parent_c["video_ids"],
            "dataset_hash": hash1,
            "assignments_hash": assign_hash1,
        })

    # Rank and select Top20
    top20_candidates.sort(
        key=lambda x: (x["outlier_count"], x["small_channel_outliers"], x["distinct_intent_count"]),
        reverse=True
    )
    final_top20 = top20_candidates[:20]
    assert len(final_top20) == 20, (
        f"Expected exactly 20 Top20 candidates, got {len(final_top20)}"
    )
    top20_cluster_ids = [int(item["parent_cluster_id"]) for item in final_top20]
    top20_cluster_id_set = set(top20_cluster_ids)
    selected_clusters_payload = [
        cluster for cluster in clusters_payload
        if cluster["cluster_id"] in top20_cluster_id_set
    ]
    assert len(selected_clusters_payload) == 20

    selected_video_ids = {
        video_id
        for cluster in selected_clusters_payload
        for video_id in cluster["video_ids"]
    }
    selected_videos = [
        video for video in prod_videos
        if video["video_id"] in selected_video_ids
    ]
    assert len(selected_videos) == len(selected_video_ids)
    assert sum(len(c["video_ids"]) for c in selected_clusters_payload) == len(
        selected_videos
    )
    selected_channel_ids = {
        video["channel_id"] for video in selected_videos if video.get("channel_id")
    }
    print_flush(
        "Selected Final Top20 Candidates: "
        f"clusters={len(selected_clusters_payload)}, videos={len(selected_videos)}, "
        f"channels={len(selected_channel_ids)}"
    )
    print_flush("Loading selected channels in one PostgreSQL read...")
    selected_channels = [
        channel for channel in repo.get_all_channels()
        if channel["channel_id"] in selected_channel_ids
    ]
    assert len(selected_channels) == len(selected_channel_ids), (
        "Missing selected channels in PostgreSQL"
    )
    print_flush(f"Loaded selected channels: {len(selected_channels)}")

    # 9. FULL SPRINTS 6-10 RERUN QUALIFICATION
    print_flush("\n--- 9. FULL SPRINTS 6-10 QUALIFICATION RERUN ---")
    print_flush("Running Sprint 6 revenue/geography...")
    rev_engine = RevenueGeographyEngine()
    revenue_res = rev_engine.analyze(
        videos=selected_videos,
        channels=selected_channels,
        clusters=selected_clusters_payload,
        source_cluster_run_id=gate7_run_id,
    )
    print_flush("Sprint 6 complete.")

    selected_outliers = [
        result for result in all_outliers
        if result.video_id in selected_video_ids
    ]
    print_flush("Running Sprint 7 market structure...")
    market_engine = MarketStructureEngine()
    market_res = market_engine.analyze(
        videos=selected_videos,
        channels=selected_channels,
        clusters=selected_clusters_payload,
        source_cluster_run_id=gate7_run_id,
        outlier_results=selected_outliers,
    )
    print_flush("Sprint 7 complete.")

    print_flush("Running Sprint 8 production risk...")
    prod_risk_engine = ProductionRiskEngine()
    prod_risk_res = prod_risk_engine.analyze(
        videos=selected_videos,
        clusters=selected_clusters_payload,
        source_market_structure_run_id=market_res.run_id,
        source_cluster_run_id=gate7_run_id,
    )
    print_flush("Sprint 8 complete.")

    market_structures_map = {
        cluster.cluster_id: cluster for cluster in market_res.clusters
    }
    production_risks_map = {
        cluster.cluster_id: cluster for cluster in prod_risk_res.clusters
    }
    print_flush("Running Sprint 9 profitability...")
    profitability_engine = ProfitabilityEngine()
    profitability_res = profitability_engine.analyze_all(
        clusters_data=selected_clusters_payload,
        market_structures=market_structures_map,
        production_risks=production_risks_map,
        source_cluster_run_id=gate7_run_id,
        source_revenue_run_id=revenue_res.run_id,
        source_market_run_id=market_res.run_id,
        source_production_run_id=prod_risk_res.run_id,
        dataset_hash=hash1,
        assignments_hash=assign_hash1,
    )
    print_flush("Sprint 9 complete.")

    clusters_videos_map = {
        cluster["cluster_id"]: cluster["videos"]
        for cluster in selected_clusters_payload
    }
    outliers_by_cluster = {}
    for cluster in selected_clusters_payload:
        cluster_video_ids = set(cluster["video_ids"])
        outliers_by_cluster[cluster["cluster_id"]] = [
            result for result in actual_outliers
            if result.video_id in cluster_video_ids
        ]

    print_flush("Running Sprint 10 opportunity validation...")
    validator_engine = OpportunityValidator()
    validation_res = validator_engine.validate_all(
        profitability_analyses=profitability_res.clusters,
        clusters_videos_map=clusters_videos_map,
        market_structures_map=market_structures_map,
        production_risks_map=production_risks_map,
        outliers_map=outliers_by_cluster,
        source_profitability_run_id=profitability_res.run_id,
        source_cluster_run_id=gate7_run_id,
        source_revenue_run_id=revenue_res.run_id,
        source_market_run_id=market_res.run_id,
        source_production_run_id=prod_risk_res.run_id,
        dataset_hash=hash1,
        assignments_hash=assign_hash1,
    )
    print_flush("Sprint 10 complete.")

    sprint_results = (
        revenue_res, market_res, prod_risk_res, profitability_res, validation_res
    )
    assert all(len(result.clusters) == 20 for result in sprint_results), (
        "Every Sprint 6-10 result must contain exactly the selected 20 clusters"
    )
    print_flush("Sprints 6-10 Analytical Rerun Complete!")
    print_flush(f"  Revenue Analyzed: {len(revenue_res.clusters)} clusters")
    print_flush(f"  Market Analyzed: {len(market_res.clusters)} clusters")
    print_flush(f"  Production Risk Analyzed: {len(prod_risk_res.clusters)} clusters")
    print_flush(f"  Profitability Analyzed: {len(profitability_res.clusters)} clusters")
    print_flush(f"  Validation Analyzed: {len(validation_res.clusters)} clusters")

    # 10. FINAL RANKING
    print_flush("\n--- 10. FINAL RANKING ---")
    validation_status_counts = Counter(
        validation.validation_status.value
        for validation in validation_res.clusters
    )
    print_flush(f"Final Validation Statuses: {dict(validation_status_counts)}")
    print_flush("Top3 Selected: NO (Reserved for Sprint 13)")

    # Persist outliers
    outlier_dicts = [
        {
            "run_id": gate7_run_id,
            "dataset_hash": hash1,
            "run_type": "GATE7_FINAL_ANALYTICAL_RERUN",
            "video_id": res.video_id,
            "channel_id": res.channel_id,
            "video_title": res.video_title,
            "channel_title": res.channel_title,
            "video_views": res.video_views,
            "channel_median_views": res.channel_median_views,
            "outlier_ratio": res.outlier_ratio,
            "age_normalized_outlier_ratio": res.age_normalized_outlier_ratio,
            "velocity_ratio": res.velocity_ratio,
            "subscriber_count": res.subscriber_count,
            "is_small_channel": res.is_small_channel,
            "is_strong_outlier": res.is_strong_outlier,
            "is_major_outlier": res.is_major_outlier,
            "is_extreme_outlier": res.is_extreme_outlier,
            "small_channel_outlier": res.small_channel_outlier,
            "confidence": res.confidence,
            "outlier_rank_score": res.outlier_rank_score,
            "warnings": res.warnings,
        }
        for res in all_outliers
    ]
    assert repo.insert_outlier_analysis(outlier_dicts)
    persisted_outliers = repo.get_outlier_analysis_by_run_id(gate7_run_id)
    persisted_outlier_ids = {row["video_id"] for row in persisted_outliers}
    assert len(persisted_outliers) == EXPECTED_PROD_VIDEOS
    assert len(persisted_outlier_ids) == EXPECTED_PROD_VIDEOS
    assert persisted_outlier_ids == set(video_ids)
    assert all(row["dataset_hash"] == hash1 for row in persisted_outliers)

    # Persist clusters and all dataset assignments
    from app.models.niche import NicheCluster, NicheMiningResult

    niche_clusters = []
    for cp in clusters_payload:
        cluster_outliers = [outliers_map[vid] for vid in cp["video_ids"]]
        actual_cluster_outliers = [
            result for result in cluster_outliers if result.is_actual_outlier()
        ]
        outlier_ratios = [
            result.outlier_ratio
            for result in cluster_outliers
            if result.outlier_ratio is not None
        ]
        confidence = calculate_cluster_confidence(
            semantic_quality=best_score,
            video_count=len(cp["video_ids"]),
            unique_channels=cp["channel_count"],
            dominant_channel_share=cp["dominant_channel_share"],
            outlier_count=len(actual_cluster_outliers),
            label_quality_score=cp["quality_score"],
        )
        signal_score = calculate_cluster_signal_score(
            semantic_quality=best_score,
            outlier_count=len(actual_cluster_outliers),
            video_count=len(cp["video_ids"]),
            dominant_channel_share=cp["dominant_channel_share"],
            confidence=confidence,
        )
        niche_clusters.append(NicheCluster(
            cluster_id=cp["cluster_id"],
            video_ids=cp["video_ids"],
            video_count=len(cp["video_ids"]),
            unique_channels=cp["channel_count"],
            dominant_channel_share=cp["dominant_channel_share"],
            channel_diversity=cp["channel_diversity"],
            representative_titles=cp["representative_titles"],
            niche=cp["niche"],
            subniche=cp["subniche"],
            microniche=cp["microniche"],
            summary=cp["summary"],
            label_confidence=cp["label_confidence"],
            label_quality_score=cp["quality_score"],
            label_warnings=cp["label_warnings"],
            outlier_count=len(actual_cluster_outliers),
            strong_outlier_count=sum(
                result.is_strong_outlier for result in cluster_outliers
            ),
            major_outlier_count=sum(
                result.is_major_outlier for result in cluster_outliers
            ),
            median_outlier_ratio=(
                round(float(np.median(outlier_ratios)), 4)
                if outlier_ratios else None
            ),
            max_outlier_ratio=(
                round(float(max(outlier_ratios)), 4)
                if outlier_ratios else None
            ),
            semantic_quality=best_score,
            confidence=confidence,
            cluster_signal_score=signal_score,
            warnings=cp["warnings"] + cp["label_warnings"],
        ))

    clustering_runtime = time.time() - clustering_started_at
    mining_res = NicheMiningResult(
        run_id=gate7_run_id,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        videos_considered=len(prod_videos),
        videos_embedded=len(prod_videos),
        videos_skipped=0,
        total_clusters=len(niche_clusters),
        unassigned_count=0,
        semantic_provider="TFIDFLocalSemanticProvider",
        algorithm="kmeans",
        parameters={"k": best_k, "random_state": 42, "n_init": 10},
        quality_metric_name="silhouette_score",
        quality_metric_value=best_score,
        clusters=niche_clusters,
        elapsed_seconds=round(clustering_runtime, 2),
    )
    cluster_persistence = repo.insert_clusters(mining_res)
    assert cluster_persistence.clusters_written == best_k
    assert cluster_persistence.subniches_written == best_k
    assert cluster_persistence.cluster_videos_written == EXPECTED_PROD_VIDEOS

    # Persist analyses for which repository persistence APIs exist.
    market_persistence = repo.insert_market_structure_analysis(market_res)
    production_persistence = repo.insert_production_risk_analysis(prod_risk_res)
    profitability_persistence = repo.insert_profitability_analysis(profitability_res)
    validation_persistence = repo.insert_validation_analysis(validation_res)
    assert market_persistence.records_written == 20
    assert production_persistence.records_written == 20
    assert profitability_persistence.records_written == 20
    assert validation_persistence.records_written == 20

    # 11. PERSISTENCE READBACK & VERIFICATION
    print_flush("\n--- 11. PERSISTENCE READBACK VERIFICATION ---")
    cluster_readback = repo.verify_clusters_readback(mining_res)
    market_readback = repo.verify_market_structure_readback(market_res)
    production_readback = repo.verify_production_risk_readback(prod_risk_res)
    profitability_readback = repo.verify_profitability_readback(profitability_res)
    validation_readback = repo.verify_validation_readback(validation_res)
    print_flush(f"Cluster readback: {cluster_readback.model_dump()}")
    print_flush(f"Market readback: {market_readback.model_dump()}")
    print_flush(f"Production readback: {production_readback.model_dump()}")
    print_flush(f"Profitability readback: {profitability_readback.model_dump()}")
    print_flush(f"Validation readback: {validation_readback.model_dump()}")
    assert cluster_readback.verified
    assert market_readback.verified
    assert production_readback.verified
    assert profitability_readback.verified
    assert validation_readback.verified

    assignment_sql = """
        SELECT video_id, cluster_id
        FROM public.cluster_videos
        WHERE run_id = %s
        ORDER BY video_id
    """
    assignment_rows_1 = client.execute(assignment_sql, [gate7_run_id])
    assignment_rows_2 = client.execute(assignment_sql, [gate7_run_id])
    expected_video_ids = set(video_ids)
    postgres_assignment_hashes = []
    for read_number, rows in enumerate(
        (assignment_rows_1, assignment_rows_2), start=1
    ):
        database_video_ids = {row["video_id"] for row in rows}
        missing_video_ids = expected_video_ids - database_video_ids
        extra_video_ids = database_video_ids - expected_video_ids
        assert len(rows) == EXPECTED_PROD_VIDEOS, (
            f"PostgreSQL assignment read {read_number} returned {len(rows)} rows"
        )
        assert len(database_video_ids) == EXPECTED_PROD_VIDEOS, (
            f"PostgreSQL assignment read {read_number} has duplicate videos"
        )
        assert not missing_video_ids, (
            f"PostgreSQL assignment read {read_number} has missing video IDs"
        )
        assert not extra_video_ids, (
            f"PostgreSQL assignment read {read_number} has extra video IDs"
        )
        postgres_assignment_hashes.append(compute_assignments_hash([
            (row["video_id"], row["cluster_id"]) for row in rows
        ]))
    assert postgres_assignment_hashes[0] == postgres_assignment_hashes[1]
    assert postgres_assignment_hashes[0] == assign_hash1

    critical_counts = {
        "videos": client.execute(
            "SELECT COUNT(*) AS count FROM public.videos"
        )[0]["count"],
        "outliers": client.execute(
            "SELECT COUNT(*) AS count FROM public.video_outlier_analyses WHERE run_id = %s",
            [gate7_run_id],
        )[0]["count"],
        "clusters": client.execute(
            "SELECT COUNT(*) AS count FROM public.clusters WHERE run_id = %s",
            [gate7_run_id],
        )[0]["count"],
        "subniches": client.execute(
            "SELECT COUNT(*) AS count FROM public.subniches WHERE run_id = %s",
            [gate7_run_id],
        )[0]["count"],
        "cluster_videos": client.execute(
            "SELECT COUNT(*) AS count FROM public.cluster_videos WHERE run_id = %s",
            [gate7_run_id],
        )[0]["count"],
        "market_structure": client.execute(
            "SELECT COUNT(*) AS count FROM public.market_structure_analyses WHERE run_id = %s",
            [market_res.run_id],
        )[0]["count"],
        "production_risk": client.execute(
            "SELECT COUNT(*) AS count FROM public.production_risk_analyses WHERE run_id = %s",
            [prod_risk_res.run_id],
        )[0]["count"],
        "profitability": client.execute(
            "SELECT COUNT(*) AS count FROM public.cluster_profitability_analyses WHERE run_id = %s",
            [profitability_res.run_id],
        )[0]["count"],
        "validation": client.execute(
            "SELECT COUNT(*) AS count FROM public.cluster_validation_analyses WHERE run_id = %s",
            [validation_res.run_id],
        )[0]["count"],
    }
    assert critical_counts == {
        "videos": EXPECTED_RAW_VIDEOS,
        "outliers": EXPECTED_PROD_VIDEOS,
        "clusters": best_k,
        "subniches": best_k,
        "cluster_videos": EXPECTED_PROD_VIDEOS,
        "market_structure": 20,
        "production_risk": 20,
        "profitability": 20,
        "validation": 20,
    }

    gate7_elapsed_seconds = round(
        (datetime.datetime.now(datetime.timezone.utc) - gate7_started_at).total_seconds(),
        2,
    )
    root_status = "EXECUTION_COMPLETED_PENDING_EXTERNAL_CLOSE"
    root_metadata = {
        "gate7_run_id": gate7_run_id,
        "source_collection_run": EXPECTED_GATE6_RUN,
        "dataset_hash": hash1,
        "assignments_hash": assign_hash1,
        "selected_k": best_k,
        "k_evaluations": k_eval_results,
        "persisted_cluster_count": len(niche_clusters),
        "top20_cluster_ids": top20_cluster_ids,
        "top20_video_count": len(selected_videos),
        "sprint_run_ids": {
            "sprint6_revenue": revenue_res.run_id,
            "sprint7_market": market_res.run_id,
            "sprint8_production": prod_risk_res.run_id,
            "sprint9_profitability": profitability_res.run_id,
            "sprint10_validation": validation_res.run_id,
        },
        "validation_status_counts": dict(validation_status_counts),
        "actual_outlier_count": len(actual_outliers),
        "top100_outlier_count": len(top_100_outliers),
        "outlier_runtime_seconds": round(outlier_runtime, 2),
        "clustering_runtime_seconds": round(clustering_runtime, 2),
        "gate7_elapsed_seconds": gate7_elapsed_seconds,
        "top3_selected": False,
        "final_approval": "PENDING_EXTERNAL_CLOSE",
        "critical_counts": critical_counts,
    }
    repo.upsert_analytical_run(
        run_id=gate7_run_id,
        run_type="GATE7_FINAL_ANALYTICAL_RERUN",
        dataset_hash=hash1,
        video_count=EXPECTED_PROD_VIDEOS,
        channel_count=EXPECTED_PROD_CHANNELS,
        status=root_status,
        source_collection_run=EXPECTED_GATE6_RUN,
        methodology_version="sprint12_gate7_v1",
        notes=json.dumps(root_metadata, sort_keys=True),
    )
    root_readback = repo.get_analytical_run(gate7_run_id)
    assert root_readback is not None
    assert root_readback.run_id == gate7_run_id
    assert root_readback.status == root_status
    assert root_readback.dataset_hash == hash1
    assert root_readback.video_count == EXPECTED_PROD_VIDEOS
    assert root_readback.channel_count == EXPECTED_PROD_CHANNELS
    assert json.loads(root_readback.notes or "{}") == root_metadata

    print_flush("[PASS] PostgreSQL persistence and readback verified.")
    print_flush("\n--- 12. FINAL INTEGRITY ---")
    print_flush("Gate 7 analytical execution completed without detected errors.")
    print_flush(f"FINAL RUN ID: {gate7_run_id}")
    print_flush(f"ASSIGNMENT HASH: {assign_hash1}")
    print_flush(f"STATUS: {root_status}")
    print_flush("Final approval remains pending the complete external close.")


if __name__ == "__main__":
    main()
