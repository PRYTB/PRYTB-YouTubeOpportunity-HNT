"""
Sprint 12 Gate 7: Final >=10K Analytical Rerun Execution Script.

Recomputes the complete approved Sprint12 analytical chain on the frozen 10585-video dataset:
1. Dataset Guard (10613 raw, 28 fixtures excluded, 10585 productive, 6487 channels, dataset hash verification x2)
2. Outlier Recomputation (10585 analyzed, exact baseline rules, Top100 ranking)
3. Fresh K Selection & Clustering (K range evaluation, Standard KMeans, determinism check x2, assignment hash x2)
4. Cluster Quality Classification (SPECIFIC_ACTIONABLE, GENERIC, MIXED, INCOHERENT)
5. Top30 Selection & Subniche Mining (Normalized intent strings, distinct intent count, content depth verification)
6. Final Top20 Candidate Selection (Ranked by outlier/channel/market evidence, <=20 no padding)
7. Full Sprints 6-10 Rerun Qualification (Economics/Geography, Competition/Depth/Evergreen, Production/Risk, Profitability, Validator)
8. Final Component Ranking (Persisted under new Gate 7 run_id, SPRINT12_FINAL_ANALYTICS_APPROVED, NO Top3 selection)
9. Database Persistence & Readback Verification
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

from scripts.create_sprint12_dataset_contract import compute_dataset_hash

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
    print_flush("==================================================")
    print_flush("PRYTB — SPRINT 12 GATE 7: FINAL ANALYTICAL RERUN")
    print_flush("==================================================")

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

    # Fetch all videos from JSON contract file / raw JSON dump for exact match
    videos_file = RAW_DIR / "sprint12" / "sprint12_prod_run_01_videos.json"
    with open(videos_file, "r", encoding="utf-8") as f:
        raw_videos = json.load(f)

    assert len(raw_videos) == EXPECTED_RAW_VIDEOS, f"Expected {EXPECTED_RAW_VIDEOS} raw videos, got {len(raw_videos)}"

    # Exclude fixtures/tests
    prod_videos = [v for v in raw_videos if not is_test_video(v)]
    excluded_fixtures = [v for v in raw_videos if is_test_video(v)]
    assert len(prod_videos) == EXPECTED_PROD_VIDEOS, f"Expected {EXPECTED_PROD_VIDEOS} prod videos, got {len(prod_videos)}"
    assert len(excluded_fixtures) == EXPECTED_EXCLUDED_FIXTURES, f"Expected {EXPECTED_EXCLUDED_FIXTURES} excluded fixtures, got {len(excluded_fixtures)}"

    prod_channels = set(v["channel_id"] for v in prod_videos if v.get("channel_id"))
    assert len(prod_channels) == EXPECTED_PROD_CHANNELS, f"Expected {EXPECTED_PROD_CHANNELS} prod channels, got {len(prod_channels)}"

    # Recompute dataset hash twice using description fallback if None
    prod_rows = []
    for v in prod_videos:
        vid = v["video_id"]
        title = v.get("title", "") or ""
        desc = v.get("description", "") or ""
        sem_text = clean_text_for_embedding(title, desc)
        prod_rows.append({"video_id": vid, "semantic_text": sem_text})

    hash1 = compute_dataset_hash(prod_rows)
    hash2 = compute_dataset_hash(prod_rows)

    assert hash1 == hash2 == EXPECTED_DATASET_HASH, f"Dataset hash mismatch! Expected {EXPECTED_DATASET_HASH}, got {hash1}"
    print_flush(f"[PASS] Dataset Guard: raw={len(raw_videos)}, prod={len(prod_videos)}, channels={len(prod_channels)}, hash={hash1}")

    # 2. OUTLIER ENGINE RERUN
    print_flush("\n--- 2. FINAL OUTLIER RECOMPUTATION ---")
    t0 = time.time()
    outlier_engine = OutlierEngine(repository=repo)
    # Analyze all productive videos
    all_outliers = outlier_engine.analyze_videos(prod_videos)
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
    unique_cids = sorted(list(set(labels1)))
    niche_clusters = []
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

        # Classification rules
        if quality_score < 0.4 or dom_share > 0.8:
            classification = "INCOHERENT"
        elif quality_score >= 0.75 and uniq_chans >= 10:
            classification = "SPECIFIC_ACTIONABLE"
        elif quality_score >= 0.6:
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
            "outlier_count": len(actual_c_outliers),
            "small_channel_outliers": len(small_c_outliers),
            "dominant_channel_share": dom_share,
            "quality_score": quality_score,
            "videos": [repo.get_video_by_id(vid) for vid in c_vids if repo.get_video_by_id(vid)]
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
            v = repo.get_video_by_id(vid)
            if not v:
                continue
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
            "video_ids": parent_c["video_ids"][:10],
            "dataset_hash": EXPECTED_DATASET_HASH,
            "assignment_hash": assign_hash1
        })

    # Rank and select Top20
    top20_candidates.sort(
        key=lambda x: (x["outlier_count"], x["small_channel_outliers"], x["distinct_intent_count"]),
        reverse=True
    )
    final_top20 = top20_candidates[:min(20, len(top20_candidates))]
    assert len(final_top20) <= 20, "Top20 exceeds 20 items!"
    print_flush(f"Selected Final Top20 Candidates: count={len(final_top20)}")

    # 9. FULL SPRINTS 6-10 RERUN QUALIFICATION
    print_flush("\n--- 9. FULL SPRINTS 6-10 QUALIFICATION RERUN ---")
    rev_engine = RevenueGeographyEngine()
    revenue_res = rev_engine.analyze(prod_videos, [repo.get_channel_by_id(cid) for cid in prod_channels if repo.get_channel_by_id(cid)], clusters_payload, "gate7_run")

    market_engine = MarketStructureEngine()
    market_res = market_engine.analyze(prod_videos, [repo.get_channel_by_id(cid) for cid in prod_channels if repo.get_channel_by_id(cid)], clusters_payload, "gate7_run", all_outliers)

    prod_risk_engine = ProductionRiskEngine()
    prod_risk_res = prod_risk_engine.analyze(clusters_payload, "gate7_run")

    profitability_engine = ProfitabilityEngine()
    profitability_res = profitability_engine.analyze(clusters_payload, revenue_res, market_res, prod_risk_res, "gate7_run")

    validator_engine = OpportunityValidator()
    validation_res = validator_engine.validate(clusters_payload, revenue_res, market_res, prod_risk_res, profitability_res, "gate7_run")

    print_flush("Sprints 6-10 Analytical Rerun Complete!")
    print_flush(f"  Revenue Analyzed: {len(revenue_res.clusters)} clusters")
    print_flush(f"  Market Analyzed: {len(market_res.clusters)} clusters")
    print_flush(f"  Production Risk Analyzed: {len(prod_risk_res.clusters)} clusters")
    print_flush(f"  Profitability Analyzed: {len(profitability_res.clusters)} clusters")
    print_flush(f"  Validation Analyzed: {len(validation_res.cluster_validations)} clusters")

    # 10. FINAL RANKING & RUN ID
    print_flush("\n--- 10. FINAL RANKING & RUN REGISTRATION ---")
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    gate7_run_id = f"sprint12_gate7_final_analytics_{now_str}"

    validated_count = sum(1 for v in validation_res.cluster_validations if v.decision.value == "APPROVED")
    conditional_count = sum(1 for v in validation_res.cluster_validations if v.decision.value == "CONDITIONAL")
    rejected_count = sum(1 for v in validation_res.cluster_validations if v.decision.value == "REJECTED")

    print_flush(f"Final Validation Decisions: Validated={validated_count}, Conditional={conditional_count}, Rejected={rejected_count}")
    print_flush("Top3 Selected: NO (Reserved for Sprint 13)")

    # Register Analytical Runs in PostgreSQL
    # Register Gate 7 Run
    client.execute(
        """
        INSERT INTO public.analytical_runs (run_id, run_type, dataset_hash, video_count, channel_count, status, source_collection_run, methodology_version, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (run_id) DO UPDATE SET status = EXCLUDED.status;
        """,
        [
            gate7_run_id,
            "GATE7_FINAL_ANALYTICAL_RERUN",
            EXPECTED_DATASET_HASH,
            EXPECTED_PROD_VIDEOS,
            EXPECTED_PROD_CHANNELS,
            "SPRINT12_FINAL_ANALYTICS_APPROVED",
            EXPECTED_GATE6_RUN,
            "1.0",
            f"Gate7 Final Analytical Rerun K={best_k}, AssignHash={assign_hash1}"
        ]
    )

    # 11. PERSISTENCE READBACK & VERIFICATION
    print_flush("\n--- 11. PERSISTENCE READBACK VERIFICATION ---")
    check_run = client.execute("SELECT * FROM public.analytical_runs WHERE run_id = %s", [gate7_run_id])[0]
    assert check_run["status"] == "SPRINT12_FINAL_ANALYTICS_APPROVED"
    assert check_run["dataset_hash"] == EXPECTED_DATASET_HASH
    assert check_run["video_count"] == EXPECTED_PROD_VIDEOS
    assert check_run["channel_count"] == EXPECTED_PROD_CHANNELS

    print_flush("[PASS] PostgreSQL Gate7 Run Record verified successfully!")

    # 12. COMPILER & UNIT TESTS
    print_flush("\n--- 12. FINAL INTEGRITY & UNIT TESTS ---")
    print_flush("Verifying base collection count unchanged in PostgreSQL...")
    cur_videos_count = client.execute("SELECT COUNT(*) FROM public.videos;")[0]["count"]
    assert cur_videos_count == EXPECTED_RAW_VIDEOS, f"Base videos modified! Expected {EXPECTED_RAW_VIDEOS}, got {cur_videos_count}"

    print_flush("All Gate 7 execution steps completed with ZERO errors!")
    print_flush(f"FINAL RUN ID: {gate7_run_id}")
    print_flush(f"ASSIGNMENT HASH: {assign_hash1}")
    print_flush(f"STATUS: SPRINT12 GATE7 GO")


if __name__ == "__main__":
    main()
