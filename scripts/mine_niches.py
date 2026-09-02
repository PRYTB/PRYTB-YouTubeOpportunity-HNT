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
    print(f"Elapsed Time:      {result.elapsed_seconds}s")
    print("--------------------------------------------------\n")

    print("TOP GENERATED CLUSTERS:")
    print("-" * 80)
    
    # Sprint 4 Top Outlier IDs for Dominance Test
    top4_outlier_ids = ["JMUxmLyrhSk", "rbCQKODKv1o", "_DVVNOGYtmU", "sLyZIVy3GeU"]
    outliers_found_map = {}

    for idx, c in enumerate(result.clusters, start=1):
        print(f"Rank {idx} | Cluster ID #{c.cluster_id} (Signal Score: {c.cluster_signal_score:.2f})")
        print(f"  Niche:      {c.niche}")
        print(f"  Subniche:   {c.subniche}")
        print(f"  Microniche: {c.microniche}")
        print(f"  Summary:    {c.summary}")
        print(f"  Videos:     {c.video_count} | Unique Channels: {c.unique_channels} | Dom Share: {c.dominant_channel_share * 100:.1f}% ({c.channel_diversity})")
        
        o_ratio_str = f"{c.median_outlier_ratio:.2f}X" if c.median_outlier_ratio is not None else "N/A"
        print(f"  Outliers:   {c.outlier_count} (Strong: {c.strong_outlier_count}, Major: {c.major_outlier_count}) | Median Outlier Ratio: {o_ratio_str}")
        print(f"  Confidence: {c.confidence:.1f}%")
        print("  Representative Titles:")
        for t in c.representative_titles[:3]:
            print(f"    - {t}")
        if c.warnings:
            print(f"  Warnings:   {', '.join(c.warnings)}")
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
        print("Persisting clusters to InsForge backend DB...")
        inserted = repo.insert_clusters(result)
        print(f"[OK] Persisted {inserted} cluster records into InsForge.")

    print(f"Niche Mining run {result.run_id} finished successfully.")


if __name__ == "__main__":
    main()
