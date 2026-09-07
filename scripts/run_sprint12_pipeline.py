"""Sprint 12 Production Pipeline Execution Script.

Orchestrates:
1. Dataset Contract verification (Sprint 12 dataset contract)
2. Outlier Engine (Sprint 4)
3. Clustering & K Optimization / Niche Miner (Sprint 5)
4. Revenue & Geography Engine (Sprint 6)
5. Market Structure & Depth & Evergreen (Sprint 7)
6. Production Risk Engine (Sprint 8)
7. Profitability Engine (Sprint 9)
8. Opportunity Validator Engine (Sprint 10)
9. Non-Obviousness Gate check & Top Outputs generation
10. Persistence to InsForge database + exact readback verification
"""

import json
import hashlib
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Sequence, Mapping
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.outlier_engine import OutlierEngine
from app.analytics.clustering_engine import ClusterOptimizer, detect_near_duplicates
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
from app.analytics.semantic_provider import TFIDFLocalSemanticProvider
from app.analytics.text_normalizer import clean_text_for_embedding
from app.database.repositories import YouTubeRepository
from app.models.outliers import VideoOutlierResult
from app.models.niche import NicheMiningResult, NicheCluster, ClusterHierarchy
from app.models.market_structure import Sprint7AnalysisResult, ClusterMarketStructure
from app.models.production_risk import Sprint8AnalysisResult, ClusterProductionRisk
from app.models.profitability import Sprint9AnalysisResult, ClusterProfitabilityAnalysis
from app.models.validation import Sprint10AnalysisResult, ClusterValidationAnalysis
from app.utils.logger import logger

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
RAW_DIR = ROOT_DIR / "data" / "raw" / "sprint12"
OUTPUT_DIR = PROCESSED_DIR / "sprint12"


class InMemoryYouTubeRepository(YouTubeRepository):
    """In-memory wrapper around YouTubeRepository for Sprint 12 dataset execution."""
    def __init__(self, videos: List[Dict[str, Any]], channels: List[Dict[str, Any]]):
        self.client = None
        self._videos = videos
        self._channels = channels
        self._videos_map = {v["video_id"]: v for v in videos if "video_id" in v}
        self._channels_map = {c["channel_id"]: c for c in channels if "channel_id" in c}

    def get_all_videos(self) -> List[Dict[str, Any]]:
        return self._videos

    def get_all_channels(self) -> List[Dict[str, Any]]:
        return self._channels

    def get_all_video_ids(self) -> List[str]:
        return list(self._videos_map.keys())

    def get_video_by_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        return self._videos_map.get(video_id)

    def get_channel_by_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        return self._channels_map.get(channel_id)

    def get_all_video_metrics(self) -> List[Dict[str, Any]]:
        metrics = []
        for v in self._videos:
            metrics.append({
                "video_id": v["video_id"],
                "view_count": v.get("view_count", 0),
                "like_count": v.get("like_count", 0),
                "comment_count": v.get("comment_count", 0),
                "collected_at": v.get("published_at", "2026-01-01T00:00:00Z"),
            })
        return metrics

    def get_all_channel_metrics(self) -> List[Dict[str, Any]]:
        metrics = []
        for c in self._channels:
            metrics.append({
                "channel_id": c["channel_id"],
                "subscriber_count": c.get("subscriber_count", 0),
                "video_count": c.get("video_count", 0),
                "view_count": c.get("view_count", 0),
                "collected_at": c.get("published_at", "2026-01-01T00:00:00Z"),
            })
        return metrics

    def get_video_metrics_history(self, video_id: str, start_time: Optional[str] = None, end_time: Optional[str] = None) -> List[Dict[str, Any]]:
        v = self._videos_map.get(video_id)
        if not v:
            return []
        return [{
            "video_id": video_id,
            "view_count": v.get("view_count", 0),
            "like_count": v.get("like_count", 0),
            "comment_count": v.get("comment_count", 0),
            "collected_at": v.get("published_at", "2026-01-01T00:00:00Z"),
        }]

    def get_channel_metrics_history(self, channel_id: str, start_time: Optional[str] = None, end_time: Optional[str] = None) -> List[Dict[str, Any]]:
        c = self._channels_map.get(channel_id)
        if not c:
            return []
        return [{
            "channel_id": channel_id,
            "subscriber_count": c.get("subscriber_count", 0),
            "video_count": c.get("video_count", 0),
            "view_count": c.get("view_count", 0),
            "collected_at": c.get("published_at", "2026-01-01T00:00:00Z"),
        }]

    def get_latest_video_metrics(self, video_id: str) -> Optional[Dict[str, Any]]:
        history = self.get_video_metrics_history(video_id)
        return history[-1] if history else None

    def get_latest_channel_metrics(self, channel_id: str) -> Optional[Dict[str, Any]]:
        history = self.get_channel_metrics_history(channel_id)
        return history[-1] if history else None


def compute_assignments_hash(video_ids: List[str], labels: List[int]) -> str:
    pairs = sorted(zip(video_ids, labels), key=lambda pair: pair[0])
    payload = "\n".join(f"{video_id}::{int(label)}" for video_id, label in pairs).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pipeline_start_time = time.time()

    print("==================================================")
    print("STARTING SPRINT 12 PRODUCTION PIPELINE EXECUTION")
    print("==================================================")

    # 1. Load Dataset Contract and Production Videos
    contract_file = PROCESSED_DIR / "sprint12_dataset_contract.json"
    videos_file = PROCESSED_DIR / "sprint12_production_videos.json"
    channels_file = RAW_DIR / "sprint12_prod_run_01_channels.json"

    if not contract_file.exists() or not videos_file.exists():
        raise FileNotFoundError("Sprint 12 dataset contract or production videos file missing!")

    with open(contract_file, "r", encoding="utf-8") as f:
        contract = json.load(f)

    with open(videos_file, "r", encoding="utf-8") as f:
        videos = json.load(f)

    with open(channels_file, "r", encoding="utf-8") as f:
        channels = json.load(f)

    print(f"Loaded Contract: run_id={contract['run_id']}, videos={contract['video_count']}, channels={contract['channel_count']}")
    print(f"Dataset Hash: {contract['dataset_hash']}")
    print(f"Seed Manifest Hash: {contract['seed_manifest_hash']}")

    repo = InMemoryYouTubeRepository(videos=videos, channels=channels)

    # 2. Outlier Engine (Sprint 4)
    print("\n--- STAGE 1: OUTLIER ENGINE (Sprint 4) ---")
    t0 = time.time()
    outlier_engine = OutlierEngine(repository=repo)
    all_outliers = outlier_engine.analyze_all()
    
    actual_outliers = [res for res in all_outliers if res.is_actual_outlier()]
    small_channel_outliers = [res for res in all_outliers if res.small_channel_outlier]
    valid_baselines = [res for res in all_outliers if res.baseline_confidence in ("MEDIUM", "HIGH")]

    # Rank top 100 outliers by outlier_rank_score
    top_100_outliers = sorted(all_outliers, key=lambda x: x.outlier_rank_score, reverse=True)[:100]
    top_100_unique_channels = len(set(res.channel_id for res in top_100_outliers))
    
    outliers_map_by_id = {res.video_id: res for res in all_outliers}

    outlier_runtime = time.time() - t0
    print(f"Total Analyzed Videos: {len(all_outliers)}")
    print(f"Actual Outliers: {len(actual_outliers)}")
    print(f"Small-Channel Outliers: {len(small_channel_outliers)}")
    print(f"Valid Baselines (Med/High): {len(valid_baselines)}")
    print(f"Top 100 Outliers Unique Channels: {top_100_unique_channels}")
    print(f"Outlier Stage Runtime: {outlier_runtime:.2f}s")

    # 3. Clustering & K Optimization / Niche Miner (Sprint 5)
    print("\n--- STAGE 2: CLUSTERING & K SELECTION (Sprint 5) ---")
    t0 = time.time()
    
    # Extract semantic texts
    texts = [clean_text_for_embedding(v.get("title", ""), v.get("description", "")) for v in videos]
    titles = [v.get("title", "") for v in videos]
    video_ids = [v["video_id"] for v in videos]
    channel_ids = [v.get("channel_id", "") for v in videos]

    provider = TFIDFLocalSemanticProvider(max_features=1000, ngram_range=(1, 2))
    embeddings = provider.embed_texts(texts)

    # Scale adaptation: K selection range (K=15..35)
    optimizer = ClusterOptimizer(min_k=15, max_k=35, random_state=42)
    labels, selected_algo, selected_params, silhouette = optimizer.fit_optimal_clusters(
        embeddings=embeddings,
        algorithm="kmeans"
    )
    selected_k = len(set(labels))
    print(f"Optimal K Selected: {selected_k} (Silhouette={silhouette:.4f}, Algo={selected_algo})")

    assignments_hash = compute_assignments_hash(video_ids, labels.tolist())
    run_id_s5 = f"s5_run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    labeler = ClusterLabeler()
    min_cluster_size = 2
    unique_cids = sorted(list(set(labels)))

    niche_clusters: List[NicheCluster] = []
    clusters_payload = []
    clusters_dict_map = {}

    for cid in unique_cids:
        indices = [i for i, l in enumerate(labels) if l == cid]
        cluster_vids = [video_ids[i] for i in indices]
        cluster_chans = [channel_ids[i] for i in indices]
        v_count = len(cluster_vids)

        if v_count < min_cluster_size:
            continue

        uniq_chans, dom_share, diversity_cat, warnings = analyze_channel_diversity(cluster_chans)
        rep_titles = select_representative_titles(embeddings=embeddings, cluster_indices=indices, titles=titles)
        hierarchy = labeler.label_cluster(rep_titles)
        quality_score, label_warns = validate_label_quality(hierarchy.niche, hierarchy.subniche, hierarchy.microniche, rep_titles)
        
        c_outliers = [outliers_map_by_id.get(vid) for vid in cluster_vids if vid in outliers_map_by_id]
        actual_c_outliers = [o for o in c_outliers if o and o.is_actual_outlier()]
        small_c_outliers = [o for o in c_outliers if o and o.small_channel_outlier]

        confidence = calculate_cluster_confidence(
            semantic_quality=silhouette,
            video_count=v_count,
            unique_channels=uniq_chans,
            dominant_channel_share=dom_share,
            outlier_count=len(actual_c_outliers),
            label_quality_score=quality_score
        )
        signal_score = calculate_cluster_signal_score(
            semantic_quality=silhouette,
            outlier_count=len(actual_c_outliers),
            video_count=v_count,
            dominant_channel_share=dom_share,
            confidence=confidence
        )

        cluster_obj = NicheCluster(
            cluster_id=cid,
            hierarchy=hierarchy,
            summary=hierarchy.summary,
            video_count=v_count,
            channel_count=uniq_chans,
            video_ids=cluster_vids,
            representative_titles=rep_titles,
            outlier_count=len(actual_c_outliers),
            small_channel_outlier_count=len(small_c_outliers),
            dominant_channel_share=dom_share,
            channel_diversity_category=diversity_cat,
            confidence_score=confidence,
            signal_score=signal_score,
            label_quality_score=quality_score,
            warnings=warnings + label_warns
        )
        niche_clusters.append(cluster_obj)

        cp = {
            "cluster_id": cid,
            "niche": hierarchy.niche,
            "subniche": hierarchy.subniche,
            "microniche": hierarchy.microniche,
            "summary": hierarchy.summary,
            "video_ids": cluster_vids,
            "representative_titles": rep_titles,
            "channel_count": uniq_chans,
            "outlier_count": len(actual_c_outliers),
            "videos": [repo.get_video_by_id(vid) for vid in cluster_vids if repo.get_video_by_id(vid)]
        }
        clusters_payload.append(cp)
        clusters_dict_map[cid] = cp

    mining_result = NicheMiningResult(
        run_id=run_id_s5,
        algorithm=selected_algo,
        parameters={"k": selected_k, "min_cluster_size": min_cluster_size},
        semantic_provider=provider.provider_name,
        videos_considered=len(videos),
        videos_embedded=len(videos),
        videos_skipped=0,
        clusters=niche_clusters,
        created_at=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=round(time.time() - t0, 2)
    )

    clustering_runtime = time.time() - t0
    print(f"Clustering Runtime: {clustering_runtime:.2f}s")
    print(f"Assignments Hash: {assignments_hash}")
    print(f"Clusters Mined: {len(niche_clusters)}")

    # 4. Revenue & Geography Engine (Sprint 6)
    print("\n--- STAGE 3: REVENUE & GEOGRAPHY ENGINE (Sprint 6) ---")
    t0 = time.time()
    rev_engine = RevenueGeographyEngine()
    revenue_result = rev_engine.analyze(
        videos=videos,
        channels=channels,
        clusters=clusters_payload,
        source_cluster_run_id=mining_result.run_id
    )
    revenue_runtime = time.time() - t0
    print(f"Revenue Stage Runtime: {revenue_runtime:.2f}s")

    # 5. Market Structure Engine & Content Depth (Sprint 7)
    print("\n--- STAGE 4: MARKET STRUCTURE & CONTENT DEPTH (Sprint 7) ---")
    t0 = time.time()
    market_engine = MarketStructureEngine()
    market_result = market_engine.analyze(
        videos=videos,
        channels=channels,
        clusters=clusters_payload,
        source_cluster_run_id=mining_result.run_id,
        outlier_results=all_outliers
    )
    market_runtime = time.time() - t0

    market_structures_map = {c.cluster_id: c for c in market_result.clusters}
    depth_dist = {"SHALLOW": 0, "20_PLUS": 0, "50_PLUS": 0, "100_PLUS": 0, "UNDETERMINED": 0}
    for cms in market_result.clusters:
        depth_val = cms.content_depth_band.value if hasattr(cms.content_depth_band, "value") else str(cms.content_depth_band)
        if depth_val in depth_dist:
            depth_dist[depth_val] += 1
        elif depth_val == "BELOW_20":
            depth_dist["SHALLOW"] += 1
        else:
            depth_dist["UNDETERMINED"] += 1

    print(f"Market Structure Runtime: {market_runtime:.2f}s")
    print(f"Content Depth Distribution: {depth_dist}")

    # 6. Production Risk Engine (Sprint 8)
    print("\n--- STAGE 5: PRODUCTION RISK ENGINE (Sprint 8) ---")
    t0 = time.time()
    prod_engine = ProductionRiskEngine()
    production_result = prod_engine.analyze(
        videos=videos,
        clusters=clusters_payload,
        source_market_structure_run_id=market_result.run_id,
        source_cluster_run_id=mining_result.run_id
    )
    production_runtime = time.time() - t0
    production_risks_map = {c.cluster_id: c for c in production_result.clusters}
    print(f"Production Risk Runtime: {production_runtime:.2f}s")

    # 7. Profitability Engine (Sprint 9)
    print("\n--- STAGE 6: PROFITABILITY ENGINE (Sprint 9) ---")
    t0 = time.time()
    profit_engine = ProfitabilityEngine()
    profitability_result = profit_engine.analyze_all(
        clusters_data=clusters_payload,
        market_structures=market_structures_map,
        production_risks=production_risks_map,
        source_cluster_run_id=mining_result.run_id,
        source_revenue_run_id=revenue_result.run_id,
        source_market_run_id=market_result.run_id,
        source_production_run_id=production_result.run_id,
        dataset_hash=contract["dataset_hash"],
        assignments_hash=assignments_hash
    )
    profitability_runtime = time.time() - t0
    print(f"Profitability Engine Runtime: {profitability_runtime:.2f}s")

    # 8. Opportunity Validator Engine (Sprint 10)
    print("\n--- STAGE 7: OPPORTUNITY VALIDATOR ENGINE (Sprint 10) ---")
    t0 = time.time()
    validator_engine = OpportunityValidator()
    
    # Map outliers per cluster
    outliers_map = {}
    for cp in clusters_payload:
        cid = cp["cluster_id"]
        v_ids = set(cp["video_ids"])
        outliers_map[cid] = [res for res in all_outliers if res.video_id in v_ids]

    clusters_videos_map = {cp["cluster_id"]: cp["videos"] for cp in clusters_payload}

    validation_result = validator_engine.validate_all(
        profitability_analyses=profitability_result.clusters,
        clusters_videos_map=clusters_videos_map,
        market_structures_map=market_structures_map,
        production_risks_map=production_risks_map,
        outliers_map=outliers_map,
        source_profitability_run_id=profitability_result.run_id,
        source_cluster_run_id=mining_result.run_id,
        source_revenue_run_id=revenue_result.run_id,
        source_market_run_id=market_result.run_id,
        source_production_run_id=production_result.run_id,
        dataset_hash=contract["dataset_hash"],
        assignments_hash=assignments_hash
    )
    validation_runtime = time.time() - t0

    # Validator status summary
    status_counts = {"PASS": 0, "PASS_WITH_WARNINGS": 0, "WATCH": 0, "FAIL": 0, "INSUFFICIENT_EVIDENCE": 0}
    for cva in validation_result.clusters:
        st = cva.validation_status.value if hasattr(cva.validation_status, "value") else str(cva.validation_status)
        status_counts[st] = status_counts.get(st, 0) + 1

    print(f"Validation Runtime: {validation_runtime:.2f}s")
    print(f"Validation Status Breakdown: {status_counts}")

    # 9. Non-Obviousness Gate & Top Opportunity Candidates Selection
    print("\n--- STAGE 8: NON-OBVIOUSNESS GATE & CANDIDATE EVALUATION ---")
    
    # Broad generic terms that signal non-actionable high-level topics
    GENERIC_TERMS = {"ai", "artificial intelligence", "cybersecurity", "finance", "technology", "tech", "programming", "software"}

    candidates = []
    specific_count = 0
    generic_count = 0
    examples = []

    prof_map_by_cid = {p.cluster_id: p for p in profitability_result.clusters}

    for cva in validation_result.clusters:
        val_st = cva.validation_status.value if hasattr(cva.validation_status, "value") else str(cva.validation_status)
        cid = cva.cluster_id
        if val_st in ("PASS", "PASS_WITH_WARNINGS", "WATCH"):
            prof = prof_map_by_cid.get(cid)
            cp = clusters_dict_map.get(cid, {})
            subniche = str(cp.get("subniche", "") or "").lower().strip()
            microniche = str(cp.get("microniche", "") or "").lower().strip()
            
            is_generic = subniche in GENERIC_TERMS or microniche in GENERIC_TERMS
            if is_generic:
                generic_count += 1
            else:
                specific_count += 1

            candidate_item = {
                "cluster_id": cid,
                "label": f"{cp.get('subniche')} - {cp.get('microniche')}",
                "niche": cp.get("niche"),
                "subniche": cp.get("subniche"),
                "microniche": cp.get("microniche"),
                "videos": len(cp.get("video_ids", [])),
                "channels": cp.get("channel_count", 0),
                "outliers": cp.get("outlier_count", 0),
                "validation_status": val_st,
                "viability_score": cva.validation_score,
                "fragility_score": cva.fragility_score,
                "false_positive_risk": cva.false_positive_risk,
                "profitability_score": prof.profitability_score if prof else 0.0,
                "classification": prof.classification.value if prof and hasattr(prof.classification, 'value') else (str(prof.classification) if prof else "UNKNOWN"),
                "warnings": cva.warnings,
                "is_generic": is_generic
            }
            candidates.append(candidate_item)
            examples.append(candidate_item["label"])

    # Rank top candidates by overall viability score
    top_candidates = sorted([c for c in candidates if c["validation_status"] in ("PASS", "PASS_WITH_WARNINGS")], key=lambda x: x["viability_score"], reverse=True)[:10]

    non_obviousness_pass = specific_count >= generic_count
    gate_status = "PASS" if non_obviousness_pass else "FIX"

    print(f"Specific/Actionable Subniches: {specific_count}")
    print(f"Generic Subniches: {generic_count}")
    print(f"Non-Obviousness Gate: {gate_status}")
    print(f"Top Opportunity Candidates (Count: {len(top_candidates)}):")
    for cand in top_candidates:
        print(f"  - [{cand['validation_status']}] {cand['label']} (Viability: {cand['viability_score']:.2f}, Videos: {cand['videos']}, Channels: {cand['channels']})")

    # 10. Persistence Attempt to InsForge Database
    print("\n--- STAGE 9: PERSISTENCE & READBACK VERIFICATION ---")
    real_repo = YouTubeRepository()
    db_persisted = False
    try:
        if real_repo.client and real_repo.client.url:
            print("InsForge DB connection available. Persisting analytical runs...")
            c_res = real_repo.insert_clusters(mining_result)
            ms_res = real_repo.insert_market_structure_analysis(market_result)
            pr_res = real_repo.insert_production_risk_analysis(production_result)
            pf_res = real_repo.insert_profitability_analysis(profitability_result)
            val_res = real_repo.insert_validation_analysis(validation_result)

            # Verify readback
            c_rb = real_repo.verify_clusters_readback(mining_result)
            ms_rb = real_repo.verify_market_structure_readback(market_result)
            pr_rb = real_repo.verify_production_risk_readback(production_result)
            pf_rb = real_repo.verify_profitability_readback(profitability_result)
            val_rb = real_repo.verify_validation_readback(validation_result)

            db_persisted = c_rb.verified and ms_rb.verified and pr_rb.verified and pf_rb.verified and val_rb.verified
            print(f"InsForge Persistence & Readback Verified: {db_persisted}")
        else:
            print("InsForge URL not configured; saving full analytical lineage to local JSON artifacts.")
    except Exception as exc:
        print(f"InsForge persistence warning (continuing with JSON persistence): {exc}")

    # 11. Save Pipeline Results Artifacts
    pipeline_total_runtime = time.time() - pipeline_start_time
    
    summary_artifact = {
        "dataset_contract": contract,
        "assignments_hash": assignments_hash,
        "runtimes": {
            "outlier_engine": outlier_runtime,
            "clustering": clustering_runtime,
            "revenue_geography": revenue_runtime,
            "market_structure": market_runtime,
            "production_risk": production_runtime,
            "profitability": profitability_runtime,
            "validator": validation_runtime,
            "total_pipeline": pipeline_total_runtime
        },
        "top_100_outliers_summary": {
            "count": len(top_100_outliers),
            "unique_channels": top_100_unique_channels,
            "actual_outliers_count": len(actual_outliers),
            "small_channel_outliers_count": len(small_channel_outliers)
        },
        "clustering_summary": {
            "k_selected": selected_k,
            "silhouette": silhouette,
            "total_clusters": len(niche_clusters)
        },
        "content_depth_summary": depth_dist,
        "validator_summary": status_counts,
        "non_obviousness_gate": {
            "specific_count": specific_count,
            "generic_count": generic_count,
            "gate": gate_status,
            "examples": examples[:5]
        },
        "top_opportunity_candidates": top_candidates,
        "provenance_lineage": {
            "dataset_run_id": contract["run_id"],
            "cluster_run_id": mining_result.run_id,
            "revenue_run_id": revenue_result.run_id,
            "market_run_id": market_result.run_id,
            "production_run_id": production_result.run_id,
            "profitability_run_id": profitability_result.run_id,
            "validation_run_id": validation_result.run_id,
            "dataset_hash": contract["dataset_hash"],
            "assignments_hash": assignments_hash
        }
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_file = OUTPUT_DIR / "sprint12_pipeline_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary_artifact, f, indent=2)

    # Save detailed outputs for dashboard
    outliers_file = OUTPUT_DIR / "sprint12_top100_outliers.json"
    with open(outliers_file, "w", encoding="utf-8") as f:
        json.dump([o.model_dump(mode="json") for o in top_100_outliers], f, indent=2)

    clusters_file = OUTPUT_DIR / "sprint12_clusters.json"
    with open(clusters_file, "w", encoding="utf-8") as f:
        json.dump([c.model_dump(mode="json") for c in niche_clusters], f, indent=2)

    validations_file = OUTPUT_DIR / "sprint12_validations.json"
    with open(validations_file, "w", encoding="utf-8") as f:
        json.dump(validation_result.model_dump(mode="json"), f, indent=2)

    print(f"\nSaved Pipeline Execution Summary to {summary_file}")
    print(f"Total Pipeline Runtime: {pipeline_total_runtime:.2f}s ({len(videos)/(pipeline_total_runtime/60):.1f} videos/min)")
    print("==================================================")
    print("SPRINT 12 PIPELINE COMPLETED SUCCESSFULLY")
    print("==================================================")


if __name__ == "__main__":
    main()
