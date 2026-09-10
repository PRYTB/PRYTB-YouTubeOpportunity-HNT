import argparse
import sys
import time
from datetime import datetime, timezone
from typing import List, Set, Optional

from app.collectors.youtube_client import (
    YouTubeClient,
    parse_iso8601_duration,
    parse_int_or_none,
)
from app.database.repositories import YouTubeRepository
from app.models.youtube import YouTubeVideo, YouTubeChannel, CollectionResult, CollectionStats
from app.utils.logger import logger


def update_metrics_snapshots(
    limit: Optional[int] = None,
    video_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    all_items: bool = False
) -> int:
    start_time = time.time()
    repo = YouTubeRepository()
    client = YouTubeClient()

    target_video_ids: Set[str] = set()
    target_channel_ids: Set[str] = set()

    if video_id:
        target_video_ids.add(video_id)
        # also include its channel if available
        v_info = repo.get_video_by_id(video_id)
        if v_info and v_info.get("channel_id"):
            target_channel_ids.add(v_info["channel_id"])

    if channel_id:
        target_channel_ids.add(channel_id)

    if not video_id and not channel_id:
        # Fetch existing IDs from PostgreSQL
        db_video_ids = repo.get_all_video_ids()
        db_channel_ids = repo.get_all_channel_ids()

        if limit and not all_items:
            db_video_ids = db_video_ids[:limit]

        target_video_ids.update(db_video_ids)
        target_channel_ids.update(db_channel_ids)

    if not target_video_ids and not target_channel_ids:
        logger.info("No videos or channels found to update.")
        print("No videos or channels found to update.")
        return 0

    logger.info(
        f"Updating metrics snapshots for {len(target_video_ids)} videos and {len(target_channel_ids)} channels."
    )

    # 1. Fetch updated video details batching with videos.list (1 unit per batch of up to 50)
    video_list: List[YouTubeVideo] = []
    if target_video_ids:
        raw_videos, _ = client.get_videos(list(target_video_ids))
        for raw in raw_videos:
            v_id = raw.get("id")
            if not v_id:
                continue
            snippet = raw.get("snippet", {})
            stats = raw.get("statistics", {})
            content = raw.get("contentDetails", {})

            ch_id = snippet.get("channelId", "")
            if ch_id:
                target_channel_ids.add(ch_id)

            duration_iso = content.get("duration")
            duration_sec = parse_iso8601_duration(duration_iso)

            video_model = YouTubeVideo(
                video_id=v_id,
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
                default_audio_language=snippet.get("defaultAudioLanguage"),
            )
            video_list.append(video_model)

    # 2. Fetch updated channel details batching with channels.list (1 unit per batch of up to 50)
    channel_list: List[YouTubeChannel] = []
    if target_channel_ids:
        raw_channels, _ = client.get_channels(list(target_channel_ids))
        for raw_ch in raw_channels:
            ch_id = raw_ch.get("id")
            if not ch_id:
                continue
            ch_snippet = raw_ch.get("snippet", {})
            ch_stats = raw_ch.get("statistics", {})

            hidden_subs = ch_stats.get("hiddenSubscriberCount", False)
            if isinstance(hidden_subs, str):
                hidden_subs = hidden_subs.lower() == "true"

            sub_count = None if hidden_subs else parse_int_or_none(ch_stats.get("subscriberCount"))

            channel_model = YouTubeChannel(
                channel_id=ch_id,
                channel_title=ch_snippet.get("title", ""),
                channel_description=ch_snippet.get("description"),
                published_at=ch_snippet.get("publishedAt"),
                country=ch_snippet.get("country"),
                subscriber_count=sub_count,
                hidden_subscriber_count=hidden_subs,
                video_count=parse_int_or_none(ch_stats.get("videoCount")),
                view_count=parse_int_or_none(ch_stats.get("viewCount")),
            )
            channel_list.append(channel_model)

    # 3. Persist new snapshots to PostgreSQL
    now_iso = datetime.now(timezone.utc).isoformat()
    coll_result = CollectionResult(
        query="metrics_update_snapshot",
        videos=video_list,
        channels=channel_list,
        stats=CollectionStats(
            requested_videos=len(target_video_ids),
            search_results=0,
            videos_resolved=len(video_list),
            videos_missing=len(target_video_ids) - len(video_list),
            unique_channels=len(target_channel_ids),
            channels_resolved=len(channel_list),
            search_pages=0,
            video_batches=math.ceil(len(target_video_ids) / 50.0) if target_video_ids else 0,
            channel_batches=math.ceil(len(target_channel_ids) / 50.0) if target_channel_ids else 0,
            api_requests=client.quota_tracker.summary()["total_requests"],
            estimated_quota_units=client.quota_tracker.summary()["total_estimated_units"],
            elapsed_seconds=round(time.time() - start_time, 3),
        ),
    )

    persist_res = repo.persist_collection(coll_result, checked_at=now_iso)

    elapsed = round(time.time() - start_time, 3)
    quota_summary = client.quota_tracker.summary()

    print(f"Update Metrics Snapshot Complete:")
    print(f"  Videos updated: {persist_res.video_metrics_inserted}")
    print(f"  Channels updated: {persist_res.channel_metrics_inserted}")
    print(f"  API requests: {quota_summary['total_requests']}")
    print(f"  Estimated quota: {quota_summary['total_estimated_units']}")
    print(f"  Elapsed: {elapsed}s")

    return persist_res.video_metrics_inserted


def main():
    parser = argparse.ArgumentParser(description="Update metrics snapshots for existing videos and channels.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of videos to update.")
    parser.add_argument("--video-id", type=str, default=None, help="Update specific video ID.")
    parser.add_argument("--channel-id", type=str, default=None, help="Update specific channel ID.")
    parser.add_argument("--all", action="store_true", help="Update all videos and channels in database.")

    args = parser.parse_args()

    import math  # Ensure math imported inside module scope
    globals()["math"] = math

    update_metrics_snapshots(
        limit=args.limit,
        video_id=args.video_id,
        channel_id=args.channel_id,
        all_items=args.all
    )


if __name__ == "__main__":
    main()
