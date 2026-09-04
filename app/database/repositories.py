import json
import time
from collections import Counter
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import httpx

from app.database.insforge_client import InsForgeClient, InsForgeClientError
from app.models.market_structure import Sprint7AnalysisResult
from app.models.production_risk import Sprint8AnalysisResult
from app.models.niche import NicheMiningResult
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


class ClusterPersistenceResult(BaseModel):
    run_id: str
    clusters_written: int
    subniches_written: int
    cluster_videos_written: int


class ClusterReadbackResult(BaseModel):
    run_id: str
    expected_clusters: int
    actual_clusters: int
    expected_subniches: int
    actual_subniches: int
    expected_cluster_videos: int
    actual_cluster_videos: int
    unique_videos: int
    unique_cluster_ids: int
    duplicate_clusters: int
    duplicate_videos: int
    orphan_cluster_videos: int
    orphan_subniches: int
    missing_videos: int
    cluster_payload_mismatches: int = 0
    subniche_payload_mismatches: int = 0
    cluster_video_payload_mismatches: int = 0
    verified: bool


class MarketStructurePersistenceResult(BaseModel):
    run_id: str
    records_written: int


class MarketStructureReadbackResult(BaseModel):
    run_id: str
    expected_records: int
    actual_records: int
    unique_clusters: int
    duplicate_records: int
    payload_mismatches: int
    verified: bool


class ProductionRiskPersistenceResult(BaseModel):
    run_id: str
    records_written: int


class ProductionRiskReadbackResult(BaseModel):
    run_id: str
    expected_records: int
    actual_records: int
    unique_clusters: int
    duplicate_records: int
    payload_mismatches: int
    verified: bool


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

    def verify_niche_schema(self) -> None:
        for table in ("clusters", "subniches", "cluster_videos"):
            self._get_records(table, params={"limit": 1})

    def verify_market_structure_schema(self) -> None:
        self._get_records("market_structure_analyses", params={"limit": 1})

    def verify_production_risk_schema(self) -> None:
        self._get_records("production_risk_analyses", params={"limit": 1})

    @staticmethod
    def _build_production_risk_records(
        result: Sprint8AnalysisResult
    ) -> List[Dict[str, Any]]:
        records = []
        for cluster in result.clusters:
            payload = cluster.model_dump(mode="json")
            records.append({
                "run_id": result.run_id,
                "source_market_structure_run_id": result.source_market_structure_run_id,
                "source_cluster_run_id": result.source_cluster_run_id,
                "cluster_id": cluster.cluster_id,
                "analyzed_at": result.analyzed_at,
                "config": result.config,
                "quality": result.quality.model_dump(mode="json"),
                "metrics": payload,
                "microniche": cluster.microniche,
                "production_cost_score": cluster.production_cost_score,
                "estimated_hours_low": cluster.estimated_hours_low,
                "estimated_hours_high": cluster.estimated_hours_high,
                "production_complexity": cluster.production_complexity.value,
                "overall_risk_score": cluster.overall_risk_score,
                "risk_level": cluster.risk_level.value,
                "confidence": cluster.confidence,
            })
        return records

    def insert_production_risk_analysis(
        self, result: Sprint8AnalysisResult
    ) -> ProductionRiskPersistenceResult:
        if not result.clusters:
            raise ValueError("Sprint 8 analysis has no clusters to persist.")
        cluster_ids = [cluster.cluster_id for cluster in result.clusters]
        if len(cluster_ids) != len(set(cluster_ids)):
            raise ValueError("Duplicate cluster IDs in Sprint 8 analysis.")
        records = self._build_production_risk_records(result)
        self.verify_production_risk_schema()
        self._post_records("production_risk_analyses", records, upsert=False)
        return ProductionRiskPersistenceResult(
            run_id=result.run_id, records_written=len(records)
        )

    def verify_production_risk_readback(
        self, expected: Sprint8AnalysisResult
    ) -> ProductionRiskReadbackResult:
        records = self._get_records(
            "production_risk_analyses",
            params={"run_id": f"eq.{expected.run_id}"},
        )
        expected_records = self._build_production_risk_records(expected)
        keys = [(record.get("run_id"), record.get("cluster_id")) for record in records]
        duplicate_records = sum(
            count - 1 for count in Counter(keys).values() if count > 1
        )
        payload_mismatches = self._payload_mismatches(
            expected_records, records, ("run_id", "cluster_id")
        )
        expected_keys = {
            (expected.run_id, cluster.cluster_id) for cluster in expected.clusters
        }
        verified = (
            len(records) == len(expected_records)
            and set(keys) == expected_keys
            and duplicate_records == 0
            and payload_mismatches == 0
        )
        return ProductionRiskReadbackResult(
            run_id=expected.run_id,
            expected_records=len(expected_records),
            actual_records=len(records),
            unique_clusters=len({record.get("cluster_id") for record in records}),
            duplicate_records=duplicate_records,
            payload_mismatches=payload_mismatches,
            verified=verified,
        )

    @staticmethod
    def _build_market_structure_records(
        result: Sprint7AnalysisResult
    ) -> List[Dict[str, Any]]:
        records = []
        for cluster in result.clusters:
            payload = cluster.model_dump(mode="json")
            records.append({
                "run_id": result.run_id,
                "source_cluster_run_id": result.source_cluster_run_id,
                "cluster_id": cluster.cluster_id,
                "analyzed_at": result.analyzed_at,
                "config": result.config,
                "quality": result.quality.model_dump(mode="json"),
                "metrics": payload,
                "microniche": cluster.microniche,
                "top_5_rank": cluster.top_5_rank,
                "market_structure_score": cluster.market_structure_score,
                "competition_score": cluster.competition_score,
                "accessibility_score": cluster.accessibility_score,
                "content_depth_score": cluster.content_depth_score,
                "trend_score": cluster.trend_score,
                "evergreen_score": cluster.evergreen_score,
                "evergreen_class": cluster.evergreen_class.value,
                "market_structure_class": cluster.market_structure_class.value,
                "confidence": cluster.confidence,
            })
        return records

    def insert_market_structure_analysis(
        self, result: Sprint7AnalysisResult
    ) -> MarketStructurePersistenceResult:
        if not result.clusters:
            raise ValueError("Sprint 7 analysis has no clusters to persist.")
        cluster_ids = [cluster.cluster_id for cluster in result.clusters]
        if len(cluster_ids) != len(set(cluster_ids)):
            raise ValueError("Duplicate cluster IDs in Sprint 7 analysis.")
        records = self._build_market_structure_records(result)
        self.verify_market_structure_schema()
        self._post_records("market_structure_analyses", records, upsert=False)
        return MarketStructurePersistenceResult(
            run_id=result.run_id, records_written=len(records)
        )

    def verify_market_structure_readback(
        self, expected: Sprint7AnalysisResult
    ) -> MarketStructureReadbackResult:
        records = self._get_records(
            "market_structure_analyses",
            params={"run_id": f"eq.{expected.run_id}"},
        )
        expected_records = self._build_market_structure_records(expected)
        keys = [(record.get("run_id"), record.get("cluster_id")) for record in records]
        duplicate_records = sum(
            count - 1 for count in Counter(keys).values() if count > 1
        )
        payload_mismatches = self._payload_mismatches(
            expected_records, records, ("run_id", "cluster_id")
        )
        expected_keys = {
            (expected.run_id, cluster.cluster_id) for cluster in expected.clusters
        }
        verified = (
            len(records) == len(expected_records)
            and set(keys) == expected_keys
            and duplicate_records == 0
            and payload_mismatches == 0
        )
        return MarketStructureReadbackResult(
            run_id=expected.run_id,
            expected_records=len(expected_records),
            actual_records=len(records),
            unique_clusters=len({record.get("cluster_id") for record in records}),
            duplicate_records=duplicate_records,
            payload_mismatches=payload_mismatches,
            verified=verified,
        )

    @staticmethod
    def _build_cluster_records(
        result: NicheMiningResult
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        cluster_records = []
        subniche_records = []
        cluster_video_records = []
        for cluster in result.clusters:
            cluster_records.append({
                "cluster_id": cluster.cluster_id,
                "run_id": result.run_id,
                "algorithm": result.algorithm,
                "semantic_provider": result.semantic_provider,
                "parameters": result.parameters,
                "video_count": cluster.video_count,
                "unique_channels": cluster.unique_channels,
                "dominant_channel_share": cluster.dominant_channel_share,
                "semantic_quality": cluster.semantic_quality,
                "confidence": cluster.confidence,
                "signal_score": cluster.cluster_signal_score,
                "created_at": result.created_at
            })
            subniche_records.append({
                "cluster_id": cluster.cluster_id,
                "run_id": result.run_id,
                "niche": cluster.niche,
                "subniche": cluster.subniche,
                "microniche": cluster.microniche,
                "summary": cluster.summary,
                "label_confidence": cluster.label_confidence,
                "created_at": result.created_at
            })
            cluster_video_records.extend({
                "cluster_id": cluster.cluster_id,
                "run_id": result.run_id,
                "video_id": video_id,
                "distance_to_centroid": None
            } for video_id in cluster.video_ids)
        return cluster_records, subniche_records, cluster_video_records

    def insert_clusters(self, result: NicheMiningResult) -> ClusterPersistenceResult:
        if not result.clusters:
            raise ValueError("Niche mining result has no clusters to persist.")

        cluster_ids = [c.cluster_id for c in result.clusters]
        video_ids = [video_id for c in result.clusters for video_id in c.video_ids]
        if len(cluster_ids) != len(set(cluster_ids)):
            raise ValueError("Duplicate cluster IDs in niche mining result.")
        if len(video_ids) != len(set(video_ids)):
            raise ValueError("A video belongs to more than one cluster in this run.")
        if any(c.video_count != len(c.video_ids) for c in result.clusters):
            raise ValueError("Cluster video_count does not match its video_ids.")

        cluster_records, subniche_records, cluster_video_records = (
            self._build_cluster_records(result)
        )
        self.verify_niche_schema()
        self._post_records("clusters", cluster_records, upsert=False)
        self._post_records("subniches", subniche_records, upsert=False)
        self._post_records("cluster_videos", cluster_video_records, upsert=False)
        return ClusterPersistenceResult(
            run_id=result.run_id,
            clusters_written=len(cluster_records),
            subniches_written=len(subniche_records),
            cluster_videos_written=len(cluster_video_records)
        )

    @staticmethod
    def _payload_mismatches(
        expected_records: List[Dict[str, Any]],
        actual_records: List[Dict[str, Any]],
        key_fields: tuple[str, ...]
    ) -> int:
        def normalize(record: Dict[str, Any]) -> Dict[str, Any]:
            normalized = dict(record)
            for field in ("parameters", "config", "quality", "metrics"):
                value = normalized.get(field)
                if isinstance(value, str):
                    try:
                        normalized[field] = json.loads(value)
                    except json.JSONDecodeError:
                        pass
            return normalized

        expected_by_key = {
            tuple(record[field] for field in key_fields): normalize(record)
            for record in expected_records
        }
        actual_by_key = {
            tuple(record.get(field) for field in key_fields): record
            for record in actual_records
        }
        mismatches = 0
        for key in expected_by_key.keys() | actual_by_key.keys():
            expected_record = expected_by_key.get(key)
            actual_record = actual_by_key.get(key)
            if expected_record is None or actual_record is None:
                mismatches += 1
                continue
            persisted_payload = normalize({
                field: actual_record.get(field)
                for field in expected_record
            })
            if persisted_payload != expected_record:
                mismatches += 1
        return mismatches

    def verify_clusters_readback(self, expected: NicheMiningResult) -> ClusterReadbackResult:
        run_id = expected.run_id
        c_records = self._get_records("clusters", params={"run_id": f"eq.{run_id}"})
        sn_records = self._get_records("subniches", params={"run_id": f"eq.{run_id}"})
        cv_records = self._get_records("cluster_videos", params={"run_id": f"eq.{run_id}"})
        expected_c, expected_sn, expected_cv = self._build_cluster_records(expected)

        expected_clusters = len(expected.clusters)
        expected_video_assignments = {
            (run_id, cluster.cluster_id, video_id)
            for cluster in expected.clusters
            for video_id in cluster.video_ids
        }
        cluster_keys = [
            (r.get("run_id"), r.get("cluster_id"))
            for r in c_records
        ]
        subniche_keys = [
            (r.get("run_id"), r.get("cluster_id"))
            for r in sn_records
        ]
        cluster_video_keys = [
            (r.get("run_id"), r.get("video_id"))
            for r in cv_records
        ]
        cluster_video_assignments = {
            (r.get("run_id"), r.get("cluster_id"), r.get("video_id"))
            for r in cv_records
        }
        persisted_video_ids = {
            r.get("video_id") for r in cv_records
        }
        persisted_cluster_ids = {
            r.get("cluster_id") for r in cv_records
        }
        duplicate_clusters = sum(
            count - 1
            for count in Counter(cluster_keys).values()
            if count > 1
        )
        duplicate_videos = sum(
            count - 1
            for count in Counter(cluster_video_keys).values()
            if count > 1
        )
        stored_cluster_keys = set(cluster_keys)
        orphan_subniches = sum(
            key not in stored_cluster_keys
            for key in subniche_keys
        )
        orphan_cluster_videos = sum(
            (r.get("run_id"), r.get("cluster_id"))
            not in stored_cluster_keys
            for r in cv_records
        )
        missing_videos = sum(
            not self._get_records(
                "videos",
                params={"video_id": f"eq.{video_id}"}
            )
            for video_id in persisted_video_ids
        )
        expected_cluster_keys = {
            (run_id, cluster.cluster_id)
            for cluster in expected.clusters
        }
        cluster_payload_mismatches = self._payload_mismatches(
            expected_c, c_records, ("run_id", "cluster_id")
        )
        subniche_payload_mismatches = self._payload_mismatches(
            expected_sn, sn_records, ("run_id", "cluster_id")
        )
        cluster_video_payload_mismatches = self._payload_mismatches(
            expected_cv,
            cv_records,
            ("run_id", "cluster_id", "video_id")
        )
        verified = (
            len(c_records) == expected_clusters
            and len(sn_records) == expected_clusters
            and len(cv_records) == len(expected_video_assignments)
            and set(cluster_keys) == expected_cluster_keys
            and set(subniche_keys) == expected_cluster_keys
            and cluster_video_assignments == expected_video_assignments
            and duplicate_clusters == duplicate_videos == 0
            and orphan_cluster_videos == orphan_subniches == missing_videos == 0
            and cluster_payload_mismatches == 0
            and subniche_payload_mismatches == 0
            and cluster_video_payload_mismatches == 0
        )
        return ClusterReadbackResult(
            run_id=run_id,
            expected_clusters=expected_clusters,
            actual_clusters=len(c_records),
            expected_subniches=expected_clusters,
            actual_subniches=len(sn_records),
            expected_cluster_videos=len(expected_video_assignments),
            actual_cluster_videos=len(cv_records),
            unique_videos=len(persisted_video_ids),
            unique_cluster_ids=len(persisted_cluster_ids),
            duplicate_clusters=duplicate_clusters,
            duplicate_videos=duplicate_videos,
            orphan_cluster_videos=orphan_cluster_videos,
            orphan_subniches=orphan_subniches,
            missing_videos=missing_videos,
            cluster_payload_mismatches=cluster_payload_mismatches,
            subniche_payload_mismatches=subniche_payload_mismatches,
            cluster_video_payload_mismatches=cluster_video_payload_mismatches,
            verified=verified
        )


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
