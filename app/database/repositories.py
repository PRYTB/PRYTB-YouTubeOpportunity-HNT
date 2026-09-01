import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import httpx

from app.database.insforge_client import InsForgeClient, InsForgeClientError
from app.models.youtube import CollectionResult, YouTubeChannel, YouTubeVideo
from app.utils.logger import logger


class PersistenceResult(BaseModel):
    channels_received: int = 0
    channels_upserted: int = 0
    videos_received: int = 0
    videos_upserted: int = 0
    channel_metrics_inserted: int = 0
    video_metrics_inserted: int = 0
    db_operations: int = 0
    warnings: List[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0


class YouTubeRepository:
    """
    Repository responsible for persisting YouTube collection data into InsForge PostgreSQL.
    """

    def __init__(self, client: Optional[InsForgeClient] = None):
        self.client = client or InsForgeClient()

    def _get_records(
        self,
        endpoint_table: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if not self.client.url:
            raise InsForgeClientError("INSFORGE_URL is not configured.")

        url = f"{self.client.url}/api/database/records/{endpoint_table}"
        headers = self.client._get_headers()

        try:
            with httpx.Client(timeout=self.client.timeout) as http_client:
                response = http_client.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                        return data["data"]
                    return []
                elif response.status_code in [401, 403]:
                    raise InsForgeClientError(f"InsForge authentication failure (HTTP {response.status_code}).")
                else:
                    err_msg = f"InsForge GET request to {endpoint_table} failed (HTTP {response.status_code}): {response.text}"
                    logger.error(err_msg)
                    raise InsForgeClientError(err_msg)
        except httpx.RequestError as exc:
            err_msg = f"Network error reading from InsForge {endpoint_table}: {exc}"
            logger.error(err_msg)
            raise InsForgeClientError(err_msg)

    def get_video_metrics_history(
        self,
        video_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {"video_id": f"eq.{video_id}", "order": "collected_at.asc"}
        if start_time:
            params["collected_at"] = f"gte.{start_time}"
        if end_time:
            if "collected_at" in params:
                params["collected_at"] = f"and(gte.{start_time},lte.{end_time})"
            else:
                params["collected_at"] = f"lte.{end_time}"
        records = self._get_records("video_metrics", params=params)
        # Fallback python sort in case backend doesn't respect order param
        records.sort(key=lambda x: str(x.get("collected_at", "")))
        return records

    def get_channel_metrics_history(
        self,
        channel_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {"channel_id": f"eq.{channel_id}", "order": "collected_at.asc"}
        if start_time:
            params["collected_at"] = f"gte.{start_time}"
        if end_time:
            if "collected_at" in params:
                params["collected_at"] = f"and(gte.{start_time},lte.{end_time})"
            else:
                params["collected_at"] = f"lte.{end_time}"
        records = self._get_records("channel_metrics", params=params)
        records.sort(key=lambda x: str(x.get("collected_at", "")))
        return records

    def get_latest_video_metrics(self, video_id: str) -> Optional[Dict[str, Any]]:
        history = self.get_video_metrics_history(video_id)
        return history[-1] if history else None

    def get_latest_channel_metrics(self, channel_id: str) -> Optional[Dict[str, Any]]:
        history = self.get_channel_metrics_history(channel_id)
        return history[-1] if history else None

    def get_video_by_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        params = {"video_id": f"eq.{video_id}"}
        records = self._get_records("videos", params=params)
        return records[0] if records else None

    def get_channel_by_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        params = {"channel_id": f"eq.{channel_id}"}
        records = self._get_records("channels", params=params)
        return records[0] if records else None

    def get_all_videos(self) -> List[Dict[str, Any]]:
        return self._get_records("videos")

    def get_all_channels(self) -> List[Dict[str, Any]]:
        return self._get_records("channels")

    def get_all_video_metrics(self) -> List[Dict[str, Any]]:
        return self._get_records("video_metrics")

    def get_all_channel_metrics(self) -> List[Dict[str, Any]]:
        return self._get_records("channel_metrics")

    def get_all_video_ids(self) -> List[str]:
        records = self._get_records("videos")
        return [r["video_id"] for r in records if "video_id" in r]

    def get_all_channel_ids(self) -> List[str]:
        records = self._get_records("channels")
        return [r["channel_id"] for r in records if "channel_id" in r]

    def _post_records(
        self,
        endpoint_table: str,
        records: List[Dict[str, Any]],
        upsert: bool = False
    ) -> bool:
        if not records:
            return True

        if not self.client.url:
            raise InsForgeClientError("INSFORGE_URL is not configured.")

        url = f"{self.client.url}/api/database/records/{endpoint_table}"
        headers = self.client._get_headers()
        if upsert:
            headers["Prefer"] = "resolution=merge-duplicates"

        try:
            with httpx.Client(timeout=self.client.timeout) as http_client:
                response = http_client.post(url, headers=headers, json=records)
                if response.status_code in [200, 201]:
                    return True
                elif response.status_code in [401, 403]:
                    raise InsForgeClientError(f"InsForge authentication failure (HTTP {response.status_code}).")
                else:
                    err_msg = f"InsForge request to {endpoint_table} failed (HTTP {response.status_code}): {response.text}"
                    logger.error(err_msg)
                    raise InsForgeClientError(err_msg)
        except httpx.RequestError as exc:
            err_msg = f"Network error sending batch to InsForge {endpoint_table}: {exc}"
            logger.error(err_msg)
            raise InsForgeClientError(err_msg)

    def upsert_channels(self, channels: List[YouTubeChannel]) -> int:
        if not channels:
            return 0

        records = []
        for ch in channels:
            rec = {
                "channel_id": ch.channel_id,
                "title": ch.channel_title,
                "description": ch.channel_description,
                "published_at": ch.published_at,
                "country": ch.country
            }
            records.append(rec)

        self._post_records("channels", records, upsert=True)
        return len(records)

    def upsert_videos(self, videos: List[YouTubeVideo]) -> int:
        if not videos:
            return 0

        records = []
        for v in videos:
            rec = {
                "video_id": v.video_id,
                "channel_id": v.channel_id,
                "title": v.title,
                "description": v.description,
                "published_at": v.published_at,
                "duration": v.duration_iso,
                "duration_seconds": v.duration_seconds,
                "caption": v.caption,
                "definition": v.definition,
                "licensed_content": v.licensed_content,
                "default_language": v.default_language,
                "default_audio_language": v.default_audio_language
            }
            records.append(rec)

        self._post_records("videos", records, upsert=True)
        return len(records)

    def insert_channel_metrics(
        self,
        channels: List[YouTubeChannel],
        checked_at: Optional[str] = None
    ) -> int:
        if not channels:
            return 0

        ts = checked_at or datetime.now(timezone.utc).isoformat()
        records = []
        for ch in channels:
            rec = {
                "channel_id": ch.channel_id,
                "subscriber_count": ch.subscriber_count,
                "video_count": ch.video_count,
                "view_count": ch.view_count,
                "collected_at": ts
            }
            records.append(rec)

        self._post_records("channel_metrics", records, upsert=False)
        return len(records)

    def insert_video_metrics(
        self,
        videos: List[YouTubeVideo],
        checked_at: Optional[str] = None
    ) -> int:
        if not videos:
            return 0

        ts = checked_at or datetime.now(timezone.utc).isoformat()
        records = []
        for v in videos:
            rec = {
                "video_id": v.video_id,
                "view_count": v.view_count,
                "like_count": v.like_count,
                "comment_count": v.comment_count,
                "collected_at": ts
            }
            records.append(rec)

        self._post_records("video_metrics", records, upsert=False)
        return len(records)

    def persist_collection(
        self,
        collection_result: CollectionResult,
        checked_at: Optional[str] = None
    ) -> PersistenceResult:
        start_time = time.time()
        warnings: List[str] = []
        db_ops = 0

        ts = checked_at or datetime.now(timezone.utc).isoformat()

        channels_rec = len(collection_result.channels)
        videos_rec = len(collection_result.videos)

        logger.info(
            f"Starting InsForge persistence for collection query='{collection_result.query}': "
            f"{channels_rec} channels, {videos_rec} videos"
        )

        ch_upserted = 0
        v_upserted = 0
        ch_metrics_inserted = 0
        v_metrics_inserted = 0

        # Step 1: Upsert channels
        if collection_result.channels:
            try:
                ch_upserted = self.upsert_channels(collection_result.channels)
                db_ops += 1
            except Exception as exc:
                msg = f"Failed to upsert channels: {exc}"
                warnings.append(msg)
                logger.error(msg)
                raise

        # Step 2: Upsert videos
        if collection_result.videos:
            try:
                v_upserted = self.upsert_videos(collection_result.videos)
                db_ops += 1
            except Exception as exc:
                msg = f"Failed to upsert videos: {exc}"
                warnings.append(msg)
                logger.error(msg)
                raise

        # Step 3: Insert channel metrics snapshot
        if collection_result.channels:
            try:
                ch_metrics_inserted = self.insert_channel_metrics(collection_result.channels, checked_at=ts)
                db_ops += 1
            except Exception as exc:
                msg = f"Failed to insert channel metrics: {exc}"
                warnings.append(msg)
                logger.error(msg)
                raise

        # Step 4: Insert video metrics snapshot
        if collection_result.videos:
            try:
                v_metrics_inserted = self.insert_video_metrics(collection_result.videos, checked_at=ts)
                db_ops += 1
            except Exception as exc:
                msg = f"Failed to insert video metrics: {exc}"
                warnings.append(msg)
                logger.error(msg)
                raise

        elapsed = round(time.time() - start_time, 3)

        res = PersistenceResult(
            channels_received=channels_rec,
            channels_upserted=ch_upserted,
            videos_received=videos_rec,
            videos_upserted=v_upserted,
            channel_metrics_inserted=ch_metrics_inserted,
            video_metrics_inserted=v_metrics_inserted,
            db_operations=db_ops,
            warnings=warnings,
            elapsed_seconds=elapsed
        )

        logger.info(
            f"InsForge persistence complete: channels_upserted={ch_upserted}, videos_upserted={v_upserted}, "
            f"ch_metrics={ch_metrics_inserted}, v_metrics={v_metrics_inserted}, db_ops={db_ops}, elapsed={elapsed}s"
        )

        return res
