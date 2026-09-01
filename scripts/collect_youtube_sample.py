import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.collectors.youtube_collector import YouTubeCollector
from app.utils.logger import logger

def main():
    parser = argparse.ArgumentParser(description="PRYTB — YouTube Data Collector Sample Script")
    parser.add_argument("--query", type=str, required=True, help="Search query keyword")
    parser.add_argument("--max-videos", type=int, default=50, help="Maximum number of videos to collect")
    parser.add_argument("--export", action="store_true", help="Export collected data to data/exports/")
    args = parser.parse_args()

    collector = YouTubeCollector()

    try:
        result = collector.collect_keyword(query=args.query, max_videos=args.max_videos)
    except Exception as exc:
        print(f"Collection failed: {exc}")
        sys.exit(1)

    # Console Summary Output
    print("\n==================================================")
    print("PRYTB — YOUTUBE COLLECTION")
    print("==================================================")
    print(f"Query: {result.query}")
    print(f"Requested: {result.stats.requested_videos}")
    print(f"Videos collected: {len(result.videos)}")
    print(f"Channels collected: {len(result.channels)}")
    print(f"API requests: {result.stats.api_requests}")
    print(f"Estimated quota: {result.stats.estimated_quota_units}")
    print(f"Elapsed: {result.stats.elapsed_seconds}s")
    print("\nStatus: OK")
    print("==================================================\n")

    print("--- SAMPLE VIDEOS (Max 5) ---")
    for i, v in enumerate(result.videos[:5], 1):
        subs = v.duration_seconds
        print(f"[{i}] Video ID: {v.video_id} | Title: {v.title[:45]} | Views: {v.view_count} | Duration: {v.duration_seconds}s | Channel: {v.channel_id} | Published: {v.published_at}")
    print("-----------------------------\n")

    if args.export:
        exports_dir = BASE_DIR / "data" / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        videos_file = exports_dir / f"videos_{timestamp}.json"
        channels_file = exports_dir / f"channels_{timestamp}.json"

        with open(videos_file, "w", encoding="utf-8") as f:
            json.dump([v.model_dump() for v in result.videos], f, indent=2, ensure_ascii=False)

        with open(channels_file, "w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in result.channels], f, indent=2, ensure_ascii=False)

        print(f"[EXPORT] Saved {len(result.videos)} videos to {videos_file}")
        print(f"[EXPORT] Saved {len(result.channels)} channels to {channels_file}\n")

if __name__ == "__main__":
    main()
