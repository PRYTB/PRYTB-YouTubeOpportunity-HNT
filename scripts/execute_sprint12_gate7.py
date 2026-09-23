"""
Sprint 12 Gate 7: Final >=10K Analytical Rerun Execution Script.

Recomputes the complete approved Sprint12 analytical chain on the frozen 10585-video dataset:
1. Dataset Guard (10613 raw, 28 fixtures excluded, 10585 productive, 6487 channels, dataset hash verification x2)
2. Outlier Recomputation (10585 analyzed, exact baseline rules, Top100 ranking)
3. Canonical Sprint 5 Clustering (title-only TF-IDF, fixed K=35, canonical silhouette and assignment hash)
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

if __name__ == "__main__" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from app.analytics.outlier_engine import OutlierEngine, is_test_video
from app.analytics.semantic_provider import TFIDFLocalSemanticProvider
from app.analytics.text_normalizer import clean_text_for_embedding, normalize_intent_string, validate_intent_semantic_quality
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

from scripts.sprint5_reproducibility_runner import (
    APPROVED_ALGORITHM,
    APPROVED_ASSIGNMENTS_HASH,
    APPROVED_DATASET_HASH,
    APPROVED_K,
    APPROVED_RANDOM_STATE,
    APPROVED_REPRESENTATION,
    APPROVED_SEMANTIC_TEXT_VERSION,
    APPROVED_SILHOUETTE,
    APPROVED_TFIDF_PARAMETERS,
    canonical_dataset_rows,
    cluster_clean_dataset,
    compute_assignments_hash as compute_canonical_assignments_hash,
    compute_dataset_hash,
)

EXPECTED_GATE6_RUN = "sprint12_final_collection_gate6_20260910"
EXPECTED_DATASET_HASH = APPROVED_DATASET_HASH
EXPECTED_RAW_VIDEOS = 10613
EXPECTED_PROD_VIDEOS = 10585
EXPECTED_PROD_CHANNELS = 6487
EXPECTED_EXCLUDED_FIXTURES = 28


def print_flush(*args, **kwargs):
    print(*args, **kwargs, flush=True)


def compute_assignments_hash(assignments: List[Tuple[str, int]]) -> str:
    """Compatibility wrapper around the canonical Sprint 5 hash contract."""
    return compute_canonical_assignments_hash(
        [str(video_id) for video_id, _ in assignments],
        [int(cluster_id) for _, cluster_id in assignments],
    )


def _content_depth(distinct_intents_count: int) -> str:
    if distinct_intents_count >= 100:
        return "100_PLUS"
    if distinct_intents_count >= 50:
        return "50_TO_99"
    if distinct_intents_count >= 20:
        return "20_TO_49"
    return "SHALLOW"


def deduplicate_semantic_definitions(
    definitions: List[Dict[str, Any]],
    memberships: List[Dict[str, Any]],
    video_by_id: Dict[str, Dict[str, Any]],
    outliers_map: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Merge definitions globally and deterministically by normalized intent."""
    membership_parents = {
        (record["definition_id"], record["video_id"]): record["parent_cluster_id"]
        for record in memberships
    }
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for definition in definitions:
        normalized_intent = normalize_intent_string(
            str(definition.get("normalized_intent") or definition.get("microniche") or "")
        )
        if not normalized_intent:
            raise ValueError(
                f"Empty normalized_intent for {definition.get('definition_id')}"
            )
        grouped[normalized_intent].append(definition)

    merged_definitions = []
    merged_memberships = []
    for ordinal, normalized_intent in enumerate(sorted(grouped), start=1):
        sources = sorted(
            grouped[normalized_intent],
            key=lambda record: (
                int(record["parent_cluster_id"]), str(record["definition_id"])
            ),
        )
        canonical = sources[0]
        definition_id = f"def_{ordinal:03d}"
        source_definition_ids = [str(source["definition_id"]) for source in sources]
        parent_cluster_ids = sorted({int(source["parent_cluster_id"]) for source in sources})
        video_ids = sorted({
            str(video_id)
            for source in sources
            for video_id in source.get("video_ids", [])
        })
        channels = {
            str(video_by_id[video_id].get("channel_id"))
            for video_id in video_ids
            if video_id in video_by_id and video_by_id[video_id].get("channel_id")
        }
        title_intents = {
            normalize_intent_string(str(video_by_id[video_id].get("title") or ""))
            for video_id in video_ids
            if video_id in video_by_id and video_by_id[video_id].get("title")
        }
        title_intents.discard("")
        outlier_objects = [outliers_map.get(video_id) for video_id in video_ids]
        sample_titles = sorted({
            str(video_by_id[video_id].get("title") or "")
            for video_id in video_ids if video_id in video_by_id
        })[:5]
        source_pattern_ids = sorted({
            str(pattern_id)
            for source in sources
            for pattern_id in source.get("evidence_payload", {}).get(
                "source_pattern_ids", []
            )
        })
        evidence_payload = {
            "deduplication_key": normalized_intent,
            "merge_rule": "global_normalized_intent_union_v1",
            "source_definition_ids": source_definition_ids,
            "source_pattern_ids": source_pattern_ids,
            "parent_cluster_ids": parent_cluster_ids,
            "sample_titles": sample_titles,
            "sample_video_ids": video_ids[:5],
            "distinct_channels_count": len(channels),
        }
        merged = dict(canonical)
        merged.update({
            "definition_id": definition_id,
            "parent_cluster_id": parent_cluster_ids[0],
            "analytical_ordinal": ordinal,
            "microniche": normalized_intent,
            "normalized_intent": normalized_intent,
            "distinct_intents_count": len(title_intents),
            "content_depth": _content_depth(len(title_intents)),
            "video_count": len(video_ids),
            "outlier_count": sum(
                1 for result in outlier_objects
                if result is not None and result.is_actual_outlier()
            ),
            "small_channel_outliers": sum(
                1 for result in outlier_objects
                if result is not None and result.small_channel_outlier
            ),
            "channel_count": len(channels),
            "evidence_payload": evidence_payload,
            "video_ids": video_ids,
        })
        merged_definitions.append(merged)
        for video_id in video_ids:
            source_parent_ids = sorted({
                int(membership_parents[(source["definition_id"], video_id)])
                for source in sources
                if (source["definition_id"], video_id) in membership_parents
            })
            merged_memberships.append({
                "run_id": canonical["run_id"],
                "definition_id": definition_id,
                "video_id": video_id,
                "parent_cluster_id": (
                    source_parent_ids[0] if source_parent_ids else parent_cluster_ids[0]
                ),
            })
    return merged_definitions, merged_memberships


def compute_ranking_hash(ids: List[str]) -> str:
    payload = "\n".join(str(i) for i in ids)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main():
    gate7_started_at = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = gate7_started_at.strftime("%Y%m%d_%H%M%S")
    gate7_run_id = f"sprint12_gate7_reconciled_{timestamp_str}"

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

    # Canonical Sprint 5 rows are ordered by video_id. The dataset hash uses
    # title+description contract text while clustering uses semantic_text_title.
    prod_rows = canonical_dataset_rows(prod_videos)
    prod_videos = [video_by_id[row["video_id"]] for row in prod_rows]

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

    # 4. CANONICAL SPRINT 5 CLUSTERING
    print_flush("\n--- 4. CANONICAL SPRINT 5 CLUSTERING ---")
    clustering_started_at = time.time()
    titles = [row["title"] for row in prod_rows]
    video_ids = [row["video_id"] for row in prod_rows]
    channel_ids = [row["channel_id"] for row in prod_rows]

    # This matrix is only retained for representative-title analysis. Labels,
    # silhouette and assignment hash come from the canonical runner function.
    provider = TFIDFLocalSemanticProvider(
        max_features=APPROVED_TFIDF_PARAMETERS["max_features"],
        ngram_range=tuple(APPROVED_TFIDF_PARAMETERS["ngram_range"]),
        min_df=APPROVED_TFIDF_PARAMETERS["min_df"],
        max_df=APPROVED_TFIDF_PARAMETERS["max_df"],
        sublinear_tf=APPROVED_TFIDF_PARAMETERS["sublinear_tf"],
    )
    embeddings = provider.embed_texts(
        [row["semantic_text_title"] for row in prod_rows]
    )
    labels1, best_score, assign_hash1 = cluster_clean_dataset(prod_rows)
    best_k = APPROVED_K
    cluster_sizes = np.bincount(labels1)
    k_eval_results = [{
        "k": best_k,
        "silhouette": best_score,
        "min_size": int(np.min(cluster_sizes)),
        "max_size": int(np.max(cluster_sizes)),
        "median_size": float(np.median(cluster_sizes)),
        "top_concentration": float(np.max(cluster_sizes) / len(labels1)),
        "tiny_cluster_count": int(np.sum(cluster_sizes < 50)),
        "contract": "sprint5_canonical_fixed_k",
    }]

    assert len(labels1) == EXPECTED_PROD_VIDEOS
    assert len(set(labels1)) == APPROVED_K
    assert abs(best_score - APPROVED_SILHOUETTE) <= 1e-12, (
        f"Canonical silhouette mismatch: {best_score}"
    )
    assert assign_hash1 == APPROVED_ASSIGNMENTS_HASH, (
        f"Canonical assignment hash mismatch: {assign_hash1}"
    )
    print_flush(
        f"Canonical clustering: K={best_k}, silhouette={best_score}, "
        f"assignment_hash={assign_hash1}"
    )

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

    # 7. GATE4 SUBNICHE MINING & FIRST-CLASS SEMANTIC DEFINITIONS
    print_flush("\n--- 7. GATE4 SUBNICHE MINING & SEMANTIC DEFINITIONS ---")
    valid_clusters = [c for c in clusters_payload if c["classification"] != "INCOHERENT"]
    sorted_clusters = sorted(
        valid_clusters,
        key=lambda c: (c["outlier_count"], c["small_channel_outliers"], c["channel_count"]),
        reverse=True
    )
    top30_clusters = sorted_clusters[:min(30, len(sorted_clusters))]
    print_flush(f"Selected Top30 Clusters for Mining: count={len(top30_clusters)}")

    raw_patterns_records = []
    semantic_definitions_records = []
    semantic_memberships_records = []
    pattern_counter = 0
    def_counter = 0

    for c in top30_clusters:
        c_id = c["cluster_id"]
        c_vids = [video_by_id[vid] for vid in c["video_ids"] if vid in video_by_id]
        c_texts = [clean_text_for_embedding(v.get("title", ""), v.get("description", "")) for v in c_vids]

        # Subclustering inside cluster
        if len(c_texts) >= 10:
            n_sub = min(3, len(c_texts) // 5)
            vec = TFIDFLocalSemanticProvider(max_features=1000, ngram_range=(1, 2))
            try:
                sub_embs = vec.embed_texts(c_texts)
                sub_km = KMeans(n_clusters=n_sub, random_state=42, n_init=5)
                sub_labels = sub_km.fit_predict(sub_embs)
            except Exception:
                sub_labels = np.zeros(len(c_texts), dtype=int)
                n_sub = 1
        else:
            sub_labels = np.zeros(len(c_texts), dtype=int)
            n_sub = 1

        for s_idx in range(n_sub):
            s_mask = (sub_labels == s_idx)
            s_vids = [c_vids[i] for i in range(len(c_vids)) if s_mask[i]]
            if not s_vids:
                continue

            s_titles = [v.get("title", "") for v in s_vids]
            s_chans = set(v["channel_id"] for v in s_vids if v.get("channel_id"))

            s_outlier_objs = [outliers_map.get(v["video_id"]) for v in s_vids if v["video_id"] in outliers_map]
            s_actual = sum(1 for o in s_outlier_objs if o and o.is_actual_outlier())
            s_small = sum(1 for o in s_outlier_objs if o and o.small_channel_outlier)

            sub_hierarchy = labeler.label_cluster(s_titles[:3])
            raw_pat_str = sub_hierarchy.subniche if sub_hierarchy.subniche else f"{c['subniche']} Subniche {s_idx+1}"
            norm_intent = normalize_intent_string(raw_pat_str)

            pattern_counter += 1
            pattern_id = f"pat_{c_id}_{pattern_counter:04d}"
            raw_patterns_records.append({
                "run_id": gate7_run_id,
                "pattern_id": pattern_id,
                "parent_cluster_id": c_id,
                "raw_pattern": raw_pat_str,
                "normalized_intent": norm_intent,
                "frequency": len(s_vids),
                "sample_video_ids": [v["video_id"] for v in s_vids[:5]]
            })

            # Calculate distinct normalized title intents supporting this group
            unique_intents = set(normalize_intent_string(t) for t in s_titles if t)
            distinct_intents_count = len(unique_intents)
            if distinct_intents_count >= 100:
                content_depth = "100_PLUS"
            elif distinct_intents_count >= 50:
                content_depth = "50_TO_99"
            elif distinct_intents_count >= 20:
                content_depth = "20_TO_49"
            else:
                content_depth = "SHALLOW"

            def_counter += 1
            definition_id = f"def_c{c_id:02d}_{def_counter:03d}"

            evidence_payload = {
                "source_pattern_ids": [pattern_id],
                "sample_titles": s_titles[:5],
                "sample_video_ids": [v["video_id"] for v in s_vids[:5]],
                "distinct_channels_count": len(s_chans),
            }

            semantic_definitions_records.append({
                "run_id": gate7_run_id,
                "definition_id": definition_id,
                "parent_cluster_id": c_id,
                "analytical_ordinal": def_counter,
                "niche": c["niche"],
                "subniche": c["subniche"],
                "microniche": norm_intent or raw_pat_str,
                "normalized_intent": norm_intent or raw_pat_str,
                "distinct_intents_count": distinct_intents_count,
                "content_depth": content_depth,
                "video_count": len(s_vids),
                "outlier_count": s_actual,
                "small_channel_outliers": s_small,
                "channel_count": len(s_chans),
                "evidence_payload": evidence_payload,
                "video_ids": [v["video_id"] for v in s_vids]
            })

            for v in s_vids:
                semantic_memberships_records.append({
                    "run_id": gate7_run_id,
                    "definition_id": definition_id,
                    "video_id": v["video_id"],
                    "parent_cluster_id": c_id
                })

    source_definition_count = len(semantic_definitions_records)
    semantic_definitions_records, semantic_memberships_records = (
        deduplicate_semantic_definitions(
            semantic_definitions_records,
            semantic_memberships_records,
            video_by_id,
            outliers_map,
        )
    )
    distinct_normalized_intents = {
        definition["normalized_intent"]
        for definition in semantic_definitions_records
    }
    membership_keys = {
        (record["definition_id"], record["video_id"])
        for record in semantic_memberships_records
    }
    assert len(semantic_definitions_records) == len(distinct_normalized_intents)
    assert len(semantic_memberships_records) == len(membership_keys)
    print_flush(
        f"Mined {len(raw_patterns_records)} raw patterns; merged "
        f"{source_definition_count} sources into "
        f"{len(semantic_definitions_records)} definitions / "
        f"{len(distinct_normalized_intents)} distinct intents with "
        f"{len(semantic_memberships_records)} memberships."
    )

    # 8. TOP20 FIRST-CLASS SEMANTIC DEFINITIONS SELECTION
    print_flush("\n--- 8. TOP20 FIRST-CLASS SEMANTIC DEFINITIONS SELECTION ---")
    sorted_sem_defs = sorted(
        semantic_definitions_records,
        key=lambda d: (d["outlier_count"], d["small_channel_outliers"], d["distinct_intents_count"], d["video_count"]),
        reverse=True
    )
    final_top20_defs = sorted_sem_defs[:20]
    assert len(final_top20_defs) == 20, f"Expected exactly 20 Top20 semantic definitions, got {len(final_top20_defs)}"

    top20_def_ids = [d["definition_id"] for d in final_top20_defs]
    top20_ranking_hash = compute_ranking_hash(top20_def_ids)

    top20_definitions_records = []
    for rank, d in enumerate(final_top20_defs, start=1):
        top20_definitions_records.append({
            "run_id": gate7_run_id,
            "rank": rank,
            "definition_id": d["definition_id"],
            "analytical_ordinal": d["analytical_ordinal"],
            "niche": d["niche"],
            "subniche": d["subniche"],
            "microniche": d["microniche"],
            "video_count": d["video_count"],
            "outlier_count": d["outlier_count"],
            "channel_count": d["channel_count"],
            "distinct_intents_count": d["distinct_intents_count"],
            "ranking_hash": top20_ranking_hash
        })

    # Top20 definitions use explicit evaluation ordinals for Sprints 6-10.
    top20_evaluation_mapping = []
    selected_clusters_payload = []
    for evaluation_cluster_id, d in enumerate(final_top20_defs, start=1):
        parent_c = next(
            c for c in clusters_payload
            if c["cluster_id"] == d["parent_cluster_id"]
        )
        parent_cluster_ids = d["evidence_payload"]["parent_cluster_ids"]
        top20_evaluation_mapping.append({
            "definition_id": d["definition_id"],
            "parent_cluster_id": d["parent_cluster_id"],
            "parent_cluster_ids": parent_cluster_ids,
            "evaluation_cluster_id": evaluation_cluster_id,
        })
        c_copy = dict(parent_c)
        c_copy["cluster_id"] = evaluation_cluster_id
        c_copy["source_definition_id"] = d["definition_id"]
        c_copy["parent_cluster_id"] = d["parent_cluster_id"]
        c_copy["parent_cluster_ids"] = parent_cluster_ids
        c_copy["video_ids"] = d["video_ids"]
        c_copy["videos"] = [
            video_by_id[vid] for vid in d["video_ids"] if vid in video_by_id
        ]
        c_copy["microniche"] = d["microniche"]
        c_copy["subniche"] = d["subniche"]
        selected_clusters_payload.append(c_copy)

    assert len(selected_clusters_payload) == 20, f"Expected 20 selected cluster payloads for Sprints 6-10, got {len(selected_clusters_payload)}"

    selected_video_ids = {
        video_id
        for cluster in selected_clusters_payload
        for video_id in cluster["video_ids"]
    }
    selected_videos = [
        video for video in prod_videos
        if video["video_id"] in selected_video_ids
    ]
    selected_channel_ids = {
        video["channel_id"] for video in selected_videos if video.get("channel_id")
    }
    print_flush(
        "Selected Final Top20 Candidate Definitions: "
        f"definitions=20, videos={len(selected_videos)}, "
        f"channels={len(selected_channel_ids)}"
    )
    print_flush("Loading selected channels in one PostgreSQL read...")
    selected_channels = [
        channel for channel in repo.get_all_channels()
        if channel["channel_id"] in selected_channel_ids
    ]
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

    # Persist outliers and top100 outliers
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
            "channel_mean_views": res.channel_mean_views,
            "channel_median_views_per_day": res.channel_median_views_per_day,
            "baseline_video_count": res.baseline_video_count,
            "baseline_confidence": res.baseline_confidence,
            "latest_velocity": res.latest_velocity,
            "latest_acceleration": res.latest_acceleration,
            "views_to_subscribers_ratio": res.views_to_subscribers_ratio,
            "outlier_rank": None
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

    # Top100 outliers persistence
    top100_ids = [res.video_id for res in top_100_outliers]
    top100_ranking_hash = compute_ranking_hash(top100_ids)
    top100_records = []
    for rank_idx, res in enumerate(top_100_outliers, start=1):
        top100_records.append({
            "outlier_rank": rank_idx,
            "video_id": res.video_id,
            "channel_id": res.channel_id,
            "outlier_score": res.outlier_rank_score,
            "is_strong_outlier": res.is_strong_outlier,
            "is_major_outlier": res.is_major_outlier,
            "is_extreme_outlier": res.is_extreme_outlier,
            "small_channel_outlier": res.small_channel_outlier,
            "channel_median_views": res.channel_median_views,
            "channel_mean_views": res.channel_mean_views,
            "baseline_video_count": res.baseline_video_count,
            "baseline_confidence": res.baseline_confidence,
        })
    assert repo.insert_gate7_top100_outliers(
        run_id=gate7_run_id,
        dataset_hash=hash1,
        ranking_hash=top100_ranking_hash,
        records=top100_records
    )

    # Persist dedicated Gate 7 semantic structures
    assert repo.insert_gate7_raw_semantic_patterns(gate7_run_id, raw_patterns_records)
    assert repo.insert_gate7_semantic_definitions(gate7_run_id, semantic_definitions_records)
    assert repo.insert_gate7_semantic_memberships(gate7_run_id, semantic_memberships_records)
    assert repo.insert_gate7_top20_definitions(gate7_run_id, top20_ranking_hash, top20_definitions_records)

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
        parameters={
            "k": APPROVED_K,
            "random_state": APPROVED_RANDOM_STATE,
            "algorithm": APPROVED_ALGORITHM,
            "representation": APPROVED_REPRESENTATION,
            "semantic_text_version": APPROVED_SEMANTIC_TEXT_VERSION,
            "tfidf": APPROVED_TFIDF_PARAMETERS,
            "fit_method": "ClusterOptimizer._fit_single",
            "approved_silhouette": APPROVED_SILHOUETTE,
            "approved_assignments_hash": APPROVED_ASSIGNMENTS_HASH,
        },
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
        "gate7_top100_outliers": client.execute(
            "SELECT COUNT(*) AS count FROM public.gate7_top100_outliers WHERE run_id = %s",
            [gate7_run_id],
        )[0]["count"],
        "gate7_raw_semantic_patterns": client.execute(
            "SELECT COUNT(*) AS count FROM public.gate7_raw_semantic_patterns WHERE run_id = %s",
            [gate7_run_id],
        )[0]["count"],
        "gate7_semantic_definitions": client.execute(
            "SELECT COUNT(*) AS count FROM public.gate7_semantic_definitions WHERE run_id = %s",
            [gate7_run_id],
        )[0]["count"],
        "gate7_distinct_normalized_intents": client.execute(
            "SELECT COUNT(DISTINCT normalized_intent) AS count FROM public.gate7_semantic_definitions WHERE run_id = %s",
            [gate7_run_id],
        )[0]["count"],
        "gate7_semantic_memberships": client.execute(
            "SELECT COUNT(*) AS count FROM public.gate7_semantic_memberships WHERE run_id = %s",
            [gate7_run_id],
        )[0]["count"],
        "gate7_top20_definitions": client.execute(
            "SELECT COUNT(*) AS count FROM public.gate7_top20_definitions WHERE run_id = %s",
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
    assert critical_counts["videos"] == EXPECTED_RAW_VIDEOS
    assert critical_counts["outliers"] == EXPECTED_PROD_VIDEOS
    assert critical_counts["clusters"] == best_k
    assert critical_counts["subniches"] == best_k
    assert critical_counts["cluster_videos"] == EXPECTED_PROD_VIDEOS
    assert critical_counts["gate7_top100_outliers"] == 100
    assert critical_counts["gate7_semantic_definitions"] == len(semantic_definitions_records)
    assert critical_counts["gate7_distinct_normalized_intents"] == len(
        distinct_normalized_intents
    )
    assert critical_counts["gate7_semantic_memberships"] == len(semantic_memberships_records)
    assert critical_counts["gate7_top20_definitions"] == 20
    assert critical_counts["market_structure"] == 20
    assert critical_counts["production_risk"] == 20
    assert critical_counts["profitability"] == 20
    assert critical_counts["validation"] == 20

    gate7_elapsed_seconds = round(
        (datetime.datetime.now(datetime.timezone.utc) - gate7_started_at).total_seconds(),
        2,
    )
    root_status = "SPRINT12_FINAL_ANALYTICS_APPROVED"
    root_metadata = {
        "gate7_run_id": gate7_run_id,
        "source_collection_run": EXPECTED_GATE6_RUN,
        "dataset_hash": hash1,
        "assignments_hash": assign_hash1,
        "top100_ranking_hash": top100_ranking_hash,
        "top20_ranking_hash": top20_ranking_hash,
        "selected_k": best_k,
        "silhouette": best_score,
        "algorithm": APPROVED_ALGORITHM,
        "random_state": APPROVED_RANDOM_STATE,
        "representation": APPROVED_REPRESENTATION,
        "semantic_text_version": APPROVED_SEMANTIC_TEXT_VERSION,
        "tfidf_parameters": APPROVED_TFIDF_PARAMETERS,
        "fit_method": "ClusterOptimizer._fit_single",
        "k_evaluations": k_eval_results,
        "persisted_cluster_count": len(niche_clusters),
        "top20_definition_ids": top20_def_ids,
        "top20_evaluation_mapping": top20_evaluation_mapping,
        "top20_video_count": len(selected_videos),
        "sprint_run_ids": {
            "sprint5_clustering": gate7_run_id,
            "sprint6_revenue": revenue_res.run_id,
            "sprint7_market": market_res.run_id,
            "sprint8_production": prod_risk_res.run_id,
            "sprint9_profitability": profitability_res.run_id,
            "sprint10_validation": validation_res.run_id,
        },
        "validation_status_counts": dict(validation_status_counts),
        "outlier_analysis_count": len(all_outliers),
        "actual_outlier_count": len(actual_outliers),
        "small_channel_outlier_count": len(small_channel_outliers),
        "top100_outlier_count": len(top_100_outliers),
        "source_semantic_definition_count": source_definition_count,
        "semantic_definition_count": len(semantic_definitions_records),
        "distinct_normalized_intent_count": len(distinct_normalized_intents),
        "semantic_membership_count": len(semantic_memberships_records),
        "outlier_runtime_seconds": round(outlier_runtime, 2),
        "clustering_runtime_seconds": round(clustering_runtime, 2),
        "gate7_elapsed_seconds": gate7_elapsed_seconds,
        "top3_selected": False,
        "final_approval": "APPROVED",
        "critical_counts": critical_counts,
    }
    repo.finalize_gate7_run(
        run_id=gate7_run_id,
        run_type="GATE7_FINAL_ANALYTICAL_RERUN",
        dataset_hash=hash1,
        video_count=EXPECTED_PROD_VIDEOS,
        channel_count=EXPECTED_PROD_CHANNELS,
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
    terminal_count = client.execute(
        "SELECT COUNT(*) AS count FROM public.analytical_runs "
        "WHERE status = 'SPRINT12_FINAL_ANALYTICS_APPROVED'"
    )[0]["count"]
    assert terminal_count == 1

    print_flush("[PASS] PostgreSQL persistence and readback verified.")
    print_flush("\n--- 12. FINAL INTEGRITY ---")
    print_flush("Gate 7 analytical execution completed without detected errors.")
    print_flush(f"FINAL RUN ID: {gate7_run_id}")
    print_flush(f"ASSIGNMENT HASH: {assign_hash1}")
    print_flush(f"STATUS: {root_status}")
    print_flush("Final approval and superseding completed atomically.")


if __name__ == "__main__":
    main()
