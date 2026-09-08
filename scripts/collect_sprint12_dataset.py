import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Any, Optional

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.collectors.youtube_client import YouTubeClient, YouTubeQuotaExceededError, parse_iso8601_duration, parse_int_or_none
from app.models.youtube import YouTubeVideo, YouTubeChannel
from app.utils.logger import logger

EXCLUDED_VIDEO_IDS = {"VID_TEST_INTEGRATION_99", "TEST_VID_001", "TEST_VID_002"}

class Sprint12CheckpointedCollector:
    def __init__(
        self,
        manifest_path: Path,
        checkpoint_path: Path,
        raw_output_dir: Path,
        run_id: str = "sprint12_prod_run_01"
    ):
        self.manifest_path = manifest_path
        self.checkpoint_path = checkpoint_path
        self.raw_output_dir = raw_output_dir
        self.run_id = run_id
        self.client = YouTubeClient()

        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.raw_output_dir.mkdir(parents=True, exist_ok=True)

        self.manifest = self._load_manifest()
        self.state = self._load_or_init_checkpoint()

    def _load_manifest(self) -> List[Dict[str, Any]]:
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [s for s in data.get("seeds", []) if s.get("enabled", True)]

    def _load_or_init_checkpoint(self) -> Dict[str, Any]:
        if self.checkpoint_path.exists():
            try:
                with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                logger.info(f"Loaded existing checkpoint from {self.checkpoint_path}. Completed seeds: {len(state.get('completed_seed_ids', []))}")
                return state
            except Exception as e:
                logger.warning(f"Failed to load checkpoint ({e}), initializing fresh state.")

        return {
            "run_id": self.run_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": "in_progress",
            "completed_seed_ids": [],
            "current_seed_id": None,
            "collected_video_ids": [],
            "collected_channel_ids": [],
            "raw_video_count": 0,
            "duplicate_exclusions": 0,
            "invalid_exclusions": 0,
            "total_quota_units": 0,
            "api_requests": 0,
            "seed_progress": {}
        }

    def _save_checkpoint(self):
        self.state["updated_at"] = datetime.utcnow().isoformat()
        temp_path = self.checkpoint_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
        temp_path.replace(self.checkpoint_path)

    def run(self, target_videos: int = 12000, max_videos_per_seed: int = 300) -> Dict[str, Any]:
        logger.info(f"Starting Sprint 12 Data Collection Run: run_id={self.run_id}, target_videos={target_videos}")
        start_time = time.time()

        collected_video_map: Dict[str, YouTubeVideo] = {}
        collected_channel_map: Dict[str, YouTubeChannel] = {}
        seen_video_ids: Set[str] = set(self.state.get("collected_video_ids", []))
        seen_channel_ids: Set[str] = set(self.state.get("collected_channel_ids", []))
        completed_seeds: Set[str] = set(self.state.get("completed_seed_ids", []))

        # Load existing raw videos/channels if resuming
        videos_dump_file = self.raw_output_dir / f"{self.run_id}_videos.json"
        channels_dump_file = self.raw_output_dir / f"{self.run_id}_channels.json"

        if videos_dump_file.exists():
            with open(videos_dump_file, "r", encoding="utf-8") as f:
                v_list = json.load(f)
                for item in v_list:
                    v_obj = YouTubeVideo(**item)
                    collected_video_map[v_obj.video_id] = v_obj

        if channels_dump_file.exists():
            with open(channels_dump_file, "r", encoding="utf-8") as f:
                c_list = json.load(f)
                for item in c_list:
                    c_obj = YouTubeChannel(**item)
                    collected_channel_map[c_obj.channel_id] = c_obj

        raw_videos_seen_total = self.state.get("raw_video_count", 0)
        duplicate_exclusions = self.state.get("duplicate_exclusions", 0)
        invalid_exclusions = self.state.get("invalid_exclusions", 0)

        for seed in self.manifest:
            seed_id = seed["seed_id"]
            query = seed["query"]
            lang = seed["language"]

            if seed_id in completed_seeds:
                logger.info(f"Skipping completed seed {seed_id} ('{query}')")
                continue

            if len(collected_video_map) >= target_videos:
                logger.info(f"Target video count ({target_videos}) reached. Stopping collection.")
                break

            logger.info(f"Processing seed {seed_id} [{lang}]: '{query}'")
            self.state["current_seed_id"] = seed_id

            # 1. Search phase for this seed
            try:
                search_items, pages = self.client.search_videos(
                    query=query,
                    max_results=max_videos_per_seed,
                    relevance_language=lang
                )
            except YouTubeQuotaExceededError as e:
                logger.error(f"YouTube Quota Exceeded on seed {seed_id}: {e}")
                self.state["status"] = "STOP"
                self.state["quota_error"] = str(e)
                self._save_checkpoint()
                return {
                    "run_id": self.run_id,
                    "status": "STOP",
                    "reason": "quota_exceeded",
                    "error": str(e),
                    "production_videos": len(collected_video_map),
                    "unique_channels": len(collected_channel_map),
                    "seeds_completed": len(completed_seeds)
                }
            except Exception as e:
                logger.error(f"Search failed for seed {seed_id}: {e}")
                self.state["status"] = "failed"
                self._save_checkpoint()
                raise e

            seed_video_ids: List[str] = []
            for item in search_items:
                vid = item.get("video_id")
                raw_videos_seen_total += 1
                if not vid or vid in EXCLUDED_VIDEO_IDS or "test" in vid.lower():
                    invalid_exclusions += 1
                    continue
                if vid in seen_video_ids:
                    duplicate_exclusions += 1
                    continue
                seen_video_ids.add(vid)
                seed_video_ids.append(vid)

            # 2. Fetch video details
            if seed_video_ids:
                raw_vids, v_batches = self.client.get_videos(seed_video_ids)
                raw_vid_map = {item["id"]: item for item in raw_vids if item.get("id")}

                new_channel_ids: Set[str] = set()

                for vid in seed_video_ids:
                    if vid not in raw_vid_map:
                        invalid_exclusions += 1
                        continue

                    raw = raw_vid_map[vid]
                    snippet = raw.get("snippet", {})
                    stats = raw.get("statistics", {})
                    content = raw.get("contentDetails", {})

                    ch_id = snippet.get("channelId", "")
                    if ch_id:
                        new_channel_ids.add(ch_id)
                        seen_channel_ids.add(ch_id)

                    duration_iso = content.get("duration")
                    duration_sec = parse_iso8601_duration(duration_iso)

                    video_obj = YouTubeVideo(
                        video_id=vid,
                        channel_id=ch_id,
                        title=snippet.get("title", ""),
                        description=snippet.get("description"),
                        published_at=snippet.get("publishedAt"),
                        category_id=snippet.get("categoryId"),
                        view_count=parse_int_or_none(stats.get("viewCount")),
                        like_count=parse_int_or_none(stats.get("likeCount")),
                        comment_count=parse_int_or_none(stats.get("commentCount")),
                        duration_iso=duration_iso,
                        duration_seconds=duration_sec,
                        definition=content.get("definition"),
                        caption=content.get("caption"),
                        licensed_content=content.get("licensedContent"),
                        default_language=snippet.get("defaultLanguage"),
                        default_audio_language=snippet.get("defaultAudioLanguage")
                    )
                    collected_video_map[vid] = video_obj

                # 3. Fetch missing channel details
                ch_to_fetch = [cid for cid in new_channel_ids if cid not in collected_channel_map]
                if ch_to_fetch:
                    raw_chans, c_batches = self.client.get_channels(ch_to_fetch)
                    for raw_ch in raw_chans:
                        ch_id = raw_ch.get("id")
                        if not ch_id:
                            continue
                        ch_snippet = raw_ch.get("snippet", {})
                        ch_stats = raw_ch.get("statistics", {})
                        hidden_subs = ch_stats.get("hiddenSubscriberCount", False)
                        if isinstance(hidden_subs, str):
                            hidden_subs = hidden_subs.lower() == "true"
                        sub_count = None if hidden_subs else parse_int_or_none(ch_stats.get("subscriberCount"))

                        channel_obj = YouTubeChannel(
                            channel_id=ch_id,
                            channel_title=ch_snippet.get("title", ""),
                            channel_description=ch_snippet.get("description"),
                            published_at=ch_snippet.get("publishedAt"),
                            country=ch_snippet.get("country"),
                            subscriber_count=sub_count,
                            hidden_subscriber_count=hidden_subs,
                            video_count=parse_int_or_none(ch_stats.get("videoCount")),
                            view_count=parse_int_or_none(ch_stats.get("viewCount"))
                        )
                        collected_channel_map[ch_id] = channel_obj

            # Update checkpoint state
            completed_seeds.add(seed_id)
            quota_summary = self.client.quota_tracker.summary()

            self.state["completed_seed_ids"] = list(completed_seeds)
            self.state["collected_video_ids"] = list(collected_video_map.keys())
            self.state["collected_channel_ids"] = list(collected_channel_map.keys())
            self.state["raw_video_count"] = raw_videos_seen_total
            self.state["duplicate_exclusions"] = duplicate_exclusions
            self.state["invalid_exclusions"] = invalid_exclusions
            self.state["total_quota_units"] = quota_summary["total_estimated_units"]
            self.state["api_requests"] = quota_summary["total_requests"]
            self.state["seed_progress"][seed_id] = {
                "pages": pages,
                "videos_added": len(seed_video_ids),
                "timestamp": datetime.utcnow().isoformat()
            }
            self._save_checkpoint()

            # Intermediate periodic dumps
            with open(videos_dump_file, "w", encoding="utf-8") as f:
                json.dump([v.model_dump() for v in collected_video_map.values()], f, ensure_ascii=False)

            with open(channels_dump_file, "w", encoding="utf-8") as f:
                json.dump([c.model_dump() for c in collected_channel_map.values()], f, ensure_ascii=False)

            logger.info(f"Seed {seed_id} complete. Total unique production videos so far: {len(collected_video_map)}, unique channels: {len(collected_channel_map)}")

        if len(collected_video_map) >= target_videos or len(completed_seeds) == len(self.manifest):
            self.state["status"] = "completed"
        self._save_checkpoint()

        elapsed = time.time() - start_time
        summary = {
            "run_id": self.run_id,
            "status": self.state["status"],
            "raw_video_count": raw_videos_seen_total,
            "duplicate_exclusions": duplicate_exclusions,
            "invalid_exclusions": invalid_exclusions,
            "production_videos": len(collected_video_map),
            "unique_channels": len(collected_channel_map),
            "seeds_completed": len(completed_seeds),
            "total_seeds": len(self.manifest),
            "quota_units": self.state["total_quota_units"],
            "api_requests": self.state["api_requests"],
            "elapsed_seconds": round(elapsed, 2),
            "videos_dump_file": str(videos_dump_file),
            "channels_dump_file": str(channels_dump_file)
        }
        logger.info(f"Sprint 12 Collection completed summary: {summary}")
        return summary


def main():
    parser = argparse.ArgumentParser(description="PRYTB — Sprint 12 Checkpointed Data Collector")
    parser.add_argument("--run-id", type=str, default="sprint12_prod_run_01", help="Sprint 12 Run ID")
    parser.add_argument("--target-videos", type=int, default=12000, help="Target number of unique production videos")
    parser.add_argument("--max-per-seed", type=int, default=300, help="Max videos per search query seed")
    args = parser.parse_args()

    manifest_path = BASE_DIR / "config" / "sprint12_seed_manifest.json"
    checkpoint_path = BASE_DIR / "data" / "checkpoints" / f"{args.run_id}_checkpoint.json"
    raw_output_dir = BASE_DIR / "data" / "raw" / "sprint12"

    collector = Sprint12CheckpointedCollector(
        manifest_path=manifest_path,
        checkpoint_path=checkpoint_path,
        raw_output_dir=raw_output_dir,
        run_id=args.run_id
    )

    summary = collector.run(target_videos=args.target_videos, max_videos_per_seed=args.max_per_seed)
    print("\n==================================================")
    print("PRYTB — SPRINT 12 COLLECTION SUMMARY")
    print("==================================================")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print("==================================================\n")

if __name__ == "__main__":
    main()
