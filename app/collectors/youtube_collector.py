import time
from typing import List, Optional, Set
from app.utils.logger import logger
from app.collectors.youtube_client import (
    YouTubeClient,
    parse_iso8601_duration,
    parse_int_or_none
)
from app.collectors.quota_tracker import QuotaTracker
from app.models.youtube import (
    YouTubeVideo,
    YouTubeChannel,
    CollectionResult,
    CollectionStats
)


class YouTubeCollector:
    def __init__(self, client: Optional[YouTubeClient] = None):
        self.client = client or YouTubeClient()

    def collect_keyword(
        self,
        query: str,
        max_videos: int = 50,
        published_after: Optional[str] = None,
        published_before: Optional[str] = None,
        region_code: Optional[str] = None,
        relevance_language: Optional[str] = None,
        order: Optional[str] = None
    ) -> CollectionResult:
        start_time = time.time()
        warnings: List[str] = []

        logger.info(f"Starting YouTube collection for query='{query}', max_videos={max_videos}")

        # 1. Search phase
        search_items, search_pages = self.client.search_videos(
            query=query,
            max_results=max_videos,
            published_after=published_after,
            published_before=published_before,
            region_code=region_code,
            relevance_language=relevance_language,
            order=order
        )

        search_results_count = len(search_items)
        logger.info(f"Search returned {search_results_count} items across {search_pages} pages")

        # Deduplicate video IDs preserving order
        unique_video_ids: List[str] = []
        seen_vids: Set[str] = set()
        for item in search_items:
            vid = item["video_id"]
            if vid and vid not in seen_vids:
                seen_vids.add(vid)
                unique_video_ids.append(vid)

        # 2. Video details phase
        raw_videos, video_batches = self.client.get_videos(unique_video_ids)
        logger.info(f"Fetched details for {len(raw_videos)} videos in {video_batches} batches")

        # Map raw video details by video ID
        raw_video_map = {item.get("id"): item for item in raw_videos if item.get("id")}

        videos: List[YouTubeVideo] = []
        missing_videos_count = 0
        channel_ids_to_fetch: List[str] = []
        seen_chans: Set[str] = set()

        for vid in unique_video_ids:
            if vid not in raw_video_map:
                missing_videos_count += 1
                msg = f"Video ID {vid} found in search but not returned by videos.list (private/deleted)."
                warnings.append(msg)
                logger.warning(msg)
                continue

            raw = raw_video_map[vid]
            snippet = raw.get("snippet", {})
            stats = raw.get("statistics", {})
            content = raw.get("contentDetails", {})
            status = raw.get("status", {})

            ch_id = snippet.get("channelId", "")
            if ch_id and ch_id not in seen_chans:
                seen_chans.add(ch_id)
                channel_ids_to_fetch.append(ch_id)

            duration_iso = content.get("duration")
            duration_sec = parse_iso8601_duration(duration_iso)

            video_model = YouTubeVideo(
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
            videos.append(video_model)

        # 3. Channel details phase
        raw_channels, channel_batches = self.client.get_channels(channel_ids_to_fetch)
        logger.info(f"Fetched details for {len(raw_channels)} channels in {channel_batches} batches")

        channels: List[YouTubeChannel] = []
        raw_channel_map = {item.get("id"): item for item in raw_channels if item.get("id")}

        for ch_id in channel_ids_to_fetch:
            if ch_id not in raw_channel_map:
                msg = f"Channel ID {ch_id} not returned by channels.list."
                warnings.append(msg)
                logger.warning(msg)
                continue

            raw_ch = raw_channel_map[ch_id]
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
                view_count=parse_int_or_none(ch_stats.get("viewCount"))
            )
            channels.append(channel_model)

        elapsed = round(time.time() - start_time, 3)

        quota_summary = self.client.quota_tracker.summary()

        stats_model = CollectionStats(
            requested_videos=max_videos,
            search_results=search_results_count,
            videos_resolved=len(videos),
            videos_missing=missing_videos_count,
            unique_channels=len(channel_ids_to_fetch),
            channels_resolved=len(channels),
            search_pages=search_pages,
            video_batches=video_batches,
            channel_batches=channel_batches,
            api_requests=quota_summary["total_requests"],
            estimated_quota_units=quota_summary["total_estimated_units"],
            elapsed_seconds=elapsed
        )

        logger.info(
            f"Collection finished for query='{query}': {len(videos)} videos, {len(channels)} channels resolved, "
            f"estimated_quota={stats_model.estimated_quota_units}, elapsed={elapsed}s"
        )

        return CollectionResult(
            query=query,
            videos=videos,
            channels=channels,
            stats=stats_model,
            warnings=warnings
        )
