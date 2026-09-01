"""
Script to rank video outliers in PRYTB Sprint 4.
Usage: python scripts/rank_outliers.py [--limit 20]
"""
import sys
import argparse
import time
from pathlib import Path

# Ensure root dir in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics.outlier_engine import OutlierEngine
from app.database.repositories import YouTubeRepository
from app.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Rank YouTube video outliers.")
    parser.add_argument("--limit", type=int, default=20, help="Number of outliers to display.")
    args = parser.parse_args()

    start_time = time.time()
    print("=" * 80)
    print(f"PRYTB SPRINT 4 — OUTLIER ENGINE RANKING (Top {args.limit})")
    print("=" * 80)

    repo = YouTubeRepository()
    engine = OutlierEngine(repository=repo)

    top_outliers = engine.rank_outliers(limit=args.limit)
    elapsed = round(time.time() - start_time, 2)

    print(f"\nExecution complete in {elapsed}s. Top {len(top_outliers)} Outliers:\n")
    header = f"{'Rank':<5} | {'Video ID':<12} | {'Views':<10} | {'MedViews':<10} | {'OutlierRatio':<12} | {'AgeNormRatio':<12} | {'Subs':<8} | {'SmallCh':<7} | {'Vel(v/h)':<8} | {'Conf':<5}"
    print(header)
    print("-" * len(header))

    for idx, item in enumerate(top_outliers, start=1):
        v_views = f"{item.video_views:,}" if item.video_views is not None else "N/A"
        m_views = f"{int(item.channel_median_views):,}" if item.channel_median_views is not None else "N/A"
        o_ratio = f"{item.outlier_ratio:.2f}X" if item.outlier_ratio is not None else "N/A"
        a_ratio = f"{item.age_normalized_outlier_ratio:.2f}X" if item.age_normalized_outlier_ratio is not None else "N/A"
        subs = f"{item.subscriber_count:,}" if item.subscriber_count is not None else "Hidden"
        small = "YES" if item.is_small_channel else ("NO" if item.is_small_channel is False else "Unknown")
        vel = f"{item.latest_velocity:.1f}" if item.latest_velocity is not None else "N/A"
        conf = f"{item.confidence:.0f}%"

        print(f"{idx:<5} | {item.video_id:<12} | {v_views:<10} | {m_views:<10} | {o_ratio:<12} | {a_ratio:<12} | {subs:<8} | {small:<7} | {vel:<8} | {conf:<5}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
