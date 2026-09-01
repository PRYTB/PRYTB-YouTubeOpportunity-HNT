import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.collectors.youtube_collector import YouTubeCollector
from app.database.repositories import YouTubeRepository
from app.utils.logger import logger

def main():
    parser = argparse.ArgumentParser(description="PRYTB — Collect and Persist YouTube Data to InsForge")
    parser.add_argument("--query", type=str, required=True, help="Search query keyword")
    parser.add_argument("--max-videos", type=int, default=50, help="Maximum number of videos to collect")
    parser.add_argument("--export", action="store_true", help="Export collected data to data/exports/")
    args = parser.parse_args()

    collector = YouTubeCollector()
    repository = YouTubeRepository()

    logger.info(f"Starting pipeline: collect & persist for query='{args.query}', max_videos={args.max_videos}")

    # 1. Collection Phase
    try:
        collection_result = collector.collect_keyword(query=args.query, max_videos=args.max_videos)
    except Exception as exc:
        print(f"Collection failed: {exc}")
        sys.exit(1)

    # 2. Persistence Phase
    try:
        persistence_result = repository.persist_collection(collection_result)
    except Exception as exc:
        print(f"Persistence failed: {exc}")
        sys.exit(1)

    # Console Summary Output
    print("\n==================================================")
    print("PRYTB — YOUTUBE COLLECTION & PERSISTENCE")
    print("==================================================")
    print(f"Query: {collection_result.query}")
    print(f"Requested: {collection_result.stats.requested_videos}")
    print(f"Videos collected: {len(collection_result.videos)}")
    print(f"Channels collected: {len(collection_result.channels)}")
    print(f"API requests: {collection_result.stats.api_requests}")
    print(f"Estimated quota: {collection_result.stats.estimated_quota_units}")
    print(f"Collection elapsed: {collection_result.stats.elapsed_seconds}s")
    print("--------------------------------------------------")
    print(f"Channels upserted: {persistence_result.channels_upserted}")
    print(f"Videos upserted: {persistence_result.videos_upserted}")
    print(f"Channel metrics inserted: {persistence_result.channel_metrics_inserted}")
    print(f"Video metrics inserted: {persistence_result.video_metrics_inserted}")
    print(f"DB operations: {persistence_result.db_operations}")
    print(f"Persistence elapsed: {persistence_result.elapsed_seconds}s")
    print("==================================================\n")

    if args.export:
        exports_dir = BASE_DIR / "data" / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        videos_file = exports_dir / f"videos_{timestamp}.json"
        channels_file = exports_dir / f"channels_{timestamp}.json"

        with open(videos_file, "w", encoding="utf-8") as f:
            json.dump([v.model_dump() for v in collection_result.videos], f, indent=2, ensure_ascii=False)

        with open(channels_file, "w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in collection_result.channels], f, indent=2, ensure_ascii=False)

        print(f"[EXPORT] Saved {len(collection_result.videos)} videos to {videos_file}")
        print(f"[EXPORT] Saved {len(collection_result.channels)} channels to {channels_file}\n")

if __name__ == "__main__":
    main()
