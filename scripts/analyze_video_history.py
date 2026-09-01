import argparse
import sys
from app.analytics.historical_metrics import HistoricalMetricsAnalyzer


def analyze_video_history(video_id: str):
    analyzer = HistoricalMetricsAnalyzer()
    metrics = analyzer.analyze_video(video_id)

    print(f"Video ID: {metrics.video_id}")
    print(f"Snapshots: {metrics.snapshot_count}")
    print(f"Latest views: {metrics.latest_views}")
    print(f"Age days: {round(metrics.video_age_days, 2) if metrics.video_age_days is not None else 'N/A'}")
    print(f"Lifetime views/day: {round(metrics.lifetime_views_per_day, 2) if metrics.lifetime_views_per_day is not None else 'N/A'}")

    if metrics.intervals:
        latest_interval = metrics.intervals[-1]
        print(f"Latest interval delta: {latest_interval.view_delta}")
    else:
        print("Latest interval delta: N/A")

    print(f"Latest velocity: {round(metrics.latest_velocity, 4) if metrics.latest_velocity is not None else 'N/A'} views/hour")
    print(f"Latest acceleration: {round(metrics.latest_acceleration, 6) if metrics.latest_acceleration is not None else 'N/A'} views/hour²")

    if metrics.warnings:
        print(f"Warnings: {len(metrics.warnings)}")
        for w in metrics.warnings:
            print(f"  - {w}")
    else:
        print("Warnings: 0")


def main():
    parser = argparse.ArgumentParser(description="Analyze video historical metrics and velocity.")
    parser.add_argument("--video-id", type=str, required=True, help="Video ID to analyze.")

    args = parser.parse_args()
    analyze_video_history(args.video_id)


if __name__ == "__main__":
    main()
