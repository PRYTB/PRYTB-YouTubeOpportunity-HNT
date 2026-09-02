"""
Main CLI entrypoint for Sprint 5 - Niche Miner.
Mines thematic clusters from persisted YouTube videos, validates dominance & channel diversity,
and persists cluster results.

Usage:
  python scripts/mine_niches.py [--limit 100] [--algorithm kmeans] [--min-cluster-size 2] [--persist]
"""
import sys
import argparse
import time
import io
from pathlib import Path

# Ensure stdout uses UTF-8 encoding for Windows terminals
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.niche_miner import NicheMiner
from app.analytics.semantic_provider import TFIDFLocalSemanticProvider, OmniRouteEmbeddingProvider
from app.analytics.text_normalizer import clean_text_for_embedding
from app.analytics.clustering_engine import ClusterOptimizer, detect_near_duplicates
from app.database.repositories import YouTubeRepository
from app.utils.config import settings
from app.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Mine thematic clusters & subniches from YouTube video dataset.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of videos to analyze.")
    parser.add_argument("--algorithm", type=str, default="kmeans", choices=["kmeans", "agglomerative"], help="Clustering algorithm.")
    parser.add_argument("--min-cluster-size", type=int, default=2, help="Minimum videos per valid cluster.")
    parser.add_argument("--persist", action="store_true", help="Persist generated clusters into InsForge DB.")
    args = parser.parse_args()

    print("=" * 80)
    print("PRYTB SPRINT 5 — NICHE MINER (Semantic Clustering & Niche Hierarchy)")
    print("=" * 80)

    repo = YouTubeRepository()

    # Determine Provider
    provider = TFIDFLocalSemanticProvider()
    miner = NicheMiner(repository=repo, semantic_provider=provider)

    # Perform evaluation of representations, K range 3..12 and algorithms
    print("\n[STEP 1] Running Semantic Representations & Algorithm Comparisons (K=3..12)...")
    all_videos = repo.get_all_videos()
    if args.limit:
        all_videos = all_videos[:args.limit]
    
    titles_list = [v.get("title", "") for v in all_videos if v.get("title")]
    desc_list = [v.get("description", "") for v in all_videos if v.get("title")]
    
    # Near duplicates detection
    near_dup_groups = detect_near_duplicates(titles_list)
    print(f"Near duplicate title groups detected: {len(near_dup_groups)}")
    for g_idx, group in enumerate(near_dup_groups[:3], start=1):
        sample_t = [titles_list[i] for i in group[:2]]
        print(f"  Group #{g_idx}: {sample_t}")

    # Build semantic texts
    semantic_texts = [clean_text_for_embedding(t, d) for t, d in zip(titles_list, desc_list)]
    
    # Embeddings evaluation
    emb_unigram = TFIDFLocalSemanticProvider(ngram_range=(1, 1)).embed_texts(semantic_texts)
    emb_bigram = TFIDFLocalSemanticProvider(ngram_range=(1, 2)).embed_texts(semantic_texts)
    
    optimizer = ClusterOptimizer()
    eval_unigram = optimizer.compare_and_evaluate(emb_unigram, k_min=3, k_max=12)
    eval_bigram = optimizer.compare_and_evaluate(emb_bigram, k_min=3, k_max=12)
    
    best_uni = max(eval_unigram.get("evaluations", [{"silhouette": 0}]), key=lambda x: x["silhouette"])
    best_bi = max(eval_bigram.get("evaluations", [{"silhouette": 0}]), key=lambda x: x["silhouette"])

    print(f"  Representation A (Unigrams):        Best Silhouette = {best_uni['silhouette']} (K={best_uni['k']}, Algo={best_uni['algorithm']})")
    print(f"  Representation B (Unigrams+Bigrams): Best Silhouette = {best_bi['silhouette']} (K={best_bi['k']}, Algo={best_bi['algorithm']})")

    # Run mine_niches
    print("\n[STEP 2] Executing Optimal Mining Run...")
    result = miner.mine_niches(
        limit=args.limit,
        algorithm=args.algorithm,
        min_cluster_size=args.min_cluster_size
    )

    print("\n--------------------------------------------------")
    print("MINING EXECUTION SUMMARY")
    print("--------------------------------------------------")
    print(f"Run ID:            {result.run_id}")
    print(f"Videos Considered: {result.videos_considered}")
    print(f"Videos Embedded:   {result.videos_embedded}")
    print(f"Videos Skipped:    {result.videos_skipped}")
    print(f"Clusters Formed:   {result.total_clusters}")
    print(f"Noise/Unassigned:  {result.unassigned_count}")
    print(f"Semantic Provider: {result.semantic_provider}")
    print(f"Algorithm:         {result.algorithm} (params: {result.parameters})")
    print(f"Quality Metric:    {result.quality_metric_name} = {result.quality_metric_value:.4f}")
    print(f"Near Duplicate Groups: {len(near_dup_groups)}")
    print(f"Elapsed Time:      {result.elapsed_seconds}s")
    print("--------------------------------------------------\n")

    print("TOP GENERATED CLUSTERS:")
    print("-" * 80)
    
    # Sprint 4 Top Outlier IDs for Dominance Test
    top4_outlier_ids = ["i2x_e-oN4Vw", "a5n-uYq0X50", "w0P11jYmEGA", "K1nZ2k3l79w"]
    outliers_found_map = {}

    top5_manual_results = []

    for idx, c in enumerate(result.clusters, start=1):
        print(f"Rank {idx} | Cluster ID #{c.cluster_id} (Signal Score: {c.cluster_signal_score:.2f})")
        print(f"  Niche:      {c.niche}")
        print(f"  Subniche:   {c.subniche}")
        print(f"  Microniche: {c.microniche}")
        print(f"  Summary:    {c.summary}")
        print(f"  Videos:     {c.video_count} | Unique Channels: {c.unique_channels} | Dom Share: {c.dominant_channel_share * 100:.1f}% ({c.channel_diversity})")
        
        o_ratio_str = f"{c.median_outlier_ratio:.2f}X" if c.median_outlier_ratio is not None else "N/A"
        print(f"  Outliers:   {c.outlier_count} (Strong: {c.strong_outlier_count}, Major: {c.major_outlier_count}) | Median Outlier Ratio: {o_ratio_str}")
        print(f"  Label Quality Score: {c.label_quality_score:.1f}/100 | Confidence: {c.confidence:.1f}%")
        print("  Representative Titles:")
        for t in c.representative_titles[:3]:
            print(f"    - {t}")
        if c.warnings:
            print(f"  Warnings:   {', '.join(c.warnings)}")

        # Perform manual check validation rule for top 5
        if idx <= 5:
            pass_validation = (
                len(c.representative_titles) > 0 and
                c.label_quality_score >= 50.0 and
                c.subniche != c.niche and
                not any("Domain" in w for w in [c.niche, c.subniche])
            )
            top5_manual_results.append((idx, c.cluster_id, "PASS" if pass_validation else "FAIL"))
            print(f"  Manual Validation: {'PASS' if pass_validation else 'FAIL'}")

        print("-" * 80)

        # Track top4 outliers cluster assignment
        for target_id in top4_outlier_ids:
            if target_id in c.video_ids:
                outliers_found_map[target_id] = c

    # Sprint 4 Top 4 Dominance Test Evaluation
    print("\n==================================================")
    print("DOMINANCE TEST (Sprint 4 Top Outliers Analysis)")
    print("==================================================")
    
    if len(outliers_found_map) == 4:
        first_cluster_id = list(outliers_found_map.values())[0].cluster_id
        all_same = all(c.cluster_id == first_cluster_id for c in outliers_found_map.values())
        dom_cluster = list(outliers_found_map.values())[0]
        print(f"Sprint 4 Top-4 in Same Cluster: {'YES' if all_same else 'NO'}")
        print(f"Assigned Cluster ID:           {dom_cluster.cluster_id}")
        print(f"Dominant Channel Share:        {dom_cluster.dominant_channel_share * 100:.1f}%")
        print(f"Unique Channels in Cluster:    {dom_cluster.unique_channels}")
        print(f"Channel Concentration Warning: {'YES' if dom_cluster.dominant_channel_share > 0.6 else 'NO'}")
    else:
        print(f"Top 4 Outliers present in dataset: {len(outliers_found_map)}/4")
        for tid in top4_outlier_ids:
            if tid in outliers_found_map:
                c = outliers_found_map[tid]
                print(f"  - {tid} -> Cluster #{c.cluster_id} (Dom Share: {c.dominant_channel_share*100:.1f}%)")
            else:
                print(f"  - {tid} -> Not in embedded dataset")
    print("==================================================\n")

    # Persist if flag provided
    if args.persist:
        print("Persisting clusters, subniches, and cluster_videos to InsForge backend DB...")
        inserted = repo.insert_clusters(result)
        print(f"[OK] Persisted {inserted} cluster records into InsForge.")

        print("Executing InsForge Read-Back verification...")
        readback = repo.verify_clusters_readback(result.run_id)
        print(f"  clusters exist:       {readback['clusters_exist']} ({readback['clusters_count']} records)")
        print(f"  subniches exist:      {readback['subniches_exist']} ({readback['subniches_count']} records)")
        print(f"  cluster_videos exist: {readback['cluster_videos_exist']} ({readback['cluster_videos_count']} records)")
        print(f"  run_id matches:       {readback['run_id_matches']}")
        if readback['clusters_exist'] and readback['subniches_exist'] and readback['cluster_videos_exist'] and readback['run_id_matches']:
            print("[OK] READ-BACK VERIFICATION PASSED PERFECTLY.")
        else:
            print("[FAIL] READ-BACK VERIFICATION FAILED.")

    print(f"\nNiche Mining run {result.run_id} finished successfully.")



if __name__ == "__main__":
    main()
