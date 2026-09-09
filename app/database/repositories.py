import json
import time
from collections import Counter
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from app.database.postgres_client import PostgresClient, PostgresClientError
from app.models.market_structure import Sprint7AnalysisResult
from app.models.production_risk import Sprint8AnalysisResult
from app.models.profitability import Sprint9AnalysisResult
from app.models.validation import Sprint10AnalysisResult
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


class ProfitabilityPersistenceResult(BaseModel):
    run_id: str
    records_written: int


class ProfitabilityReadbackResult(BaseModel):
    run_id: str
    expected_records: int
    actual_records: int
    unique_clusters: int
    duplicate_records: int
    payload_mismatches: int
    provenance_mismatches: int
    verified: bool


class ValidationPersistenceResult(BaseModel):
    run_id: str
    records_written: int


class ValidationReadbackResult(BaseModel):
    run_id: str
    expected_records: int
    actual_records: int
    unique_clusters: int
    duplicate_records: int
    payload_mismatches: int
    provenance_mismatches: int
    verified: bool


class YouTubeRepository:
    """
    Repository responsible for persisting YouTube collection data into PostgreSQL database.
    """

    def __init__(self, client: Optional[PostgresClient] = None):
        self.client = client or PostgresClient()

    def get_video_metrics_history(
        self,
        video_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM public.video_metrics WHERE video_id = %s"
        params: List[Any] = [video_id]
        if start_time:
            query += " AND collected_at >= %s"
            params.append(start_time)
        if end_time:
            query += " AND collected_at <= %s"
            params.append(end_time)
        query += " ORDER BY collected_at ASC"
        return self.client.execute(query, params)

    def get_channel_metrics_history(
        self,
        channel_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM public.channel_metrics WHERE channel_id = %s"
        params: List[Any] = [channel_id]
        if start_time:
            query += " AND collected_at >= %s"
            params.append(start_time)
        if end_time:
            query += " AND collected_at <= %s"
            params.append(end_time)
        query += " ORDER BY collected_at ASC"
        return self.client.execute(query, params)

    def get_latest_video_metrics(self, video_id: str) -> Optional[Dict[str, Any]]:
        history = self.get_video_metrics_history(video_id)
        return history[-1] if history else None

    def get_latest_channel_metrics(self, channel_id: str) -> Optional[Dict[str, Any]]:
        history = self.get_channel_metrics_history(channel_id)
        return history[-1] if history else None

    def get_video_by_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        records = self.client.execute("SELECT * FROM public.videos WHERE video_id = %s", [video_id])
        return records[0] if records else None

    def get_channel_by_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        records = self.client.execute("SELECT * FROM public.channels WHERE channel_id = %s", [channel_id])
        return records[0] if records else None

    def get_all_videos(self) -> List[Dict[str, Any]]:
        return self.client.execute("SELECT * FROM public.videos")

    def get_all_channels(self) -> List[Dict[str, Any]]:
        return self.client.execute("SELECT * FROM public.channels")

    def get_all_video_metrics(self) -> List[Dict[str, Any]]:
        return self.client.execute("SELECT * FROM public.video_metrics")

    def get_all_channel_metrics(self) -> List[Dict[str, Any]]:
        return self.client.execute("SELECT * FROM public.channel_metrics")

    def get_all_video_ids(self) -> List[str]:
        records = self.client.execute("SELECT video_id FROM public.videos")
        return [r["video_id"] for r in records if "video_id" in r]

    def get_all_channel_ids(self) -> List[str]:
        records = self.client.execute("SELECT channel_id FROM public.channels")
        return [r["channel_id"] for r in records if "channel_id" in r]

    def verify_outlier_schema(self) -> None:
        self.client.execute("SELECT 1 FROM public.video_outlier_analyses LIMIT 1")

    def insert_outlier_analysis(self, records: List[Dict[str, Any]], batch_size: int = 500) -> bool:
        if not records:
            return True
        self.verify_outlier_schema()

        query = """
        INSERT INTO public.video_outlier_analyses (
            run_id, dataset_hash, run_type, video_id, channel_id, video_title, channel_title,
            video_views, channel_median_views, outlier_ratio, age_normalized_outlier_ratio,
            velocity_ratio, subscriber_count, is_small_channel, is_strong_outlier,
            is_major_outlier, is_extreme_outlier, small_channel_outlier, confidence,
            outlier_rank_score, warnings
        ) VALUES (
            %(run_id)s, %(dataset_hash)s, %(run_type)s, %(video_id)s, %(channel_id)s, %(video_title)s, %(channel_title)s,
            %(video_views)s, %(channel_median_views)s, %(outlier_ratio)s, %(age_normalized_outlier_ratio)s,
            %(velocity_ratio)s, %(subscriber_count)s, %(is_small_channel)s, %(is_strong_outlier)s,
            %(is_major_outlier)s, %(is_extreme_outlier)s, %(small_channel_outlier)s, %(confidence)s,
            %(outlier_rank_score)s, %(warnings)s
        ) ON CONFLICT (run_id, video_id) DO UPDATE SET
            dataset_hash = EXCLUDED.dataset_hash,
            run_type = EXCLUDED.run_type,
            channel_id = EXCLUDED.channel_id,
            video_title = EXCLUDED.video_title,
            channel_title = EXCLUDED.channel_title,
            video_views = EXCLUDED.video_views,
            channel_median_views = EXCLUDED.channel_median_views,
            outlier_ratio = EXCLUDED.outlier_ratio,
            age_normalized_outlier_ratio = EXCLUDED.age_normalized_outlier_ratio,
            velocity_ratio = EXCLUDED.velocity_ratio,
            subscriber_count = EXCLUDED.subscriber_count,
            is_small_channel = EXCLUDED.is_small_channel,
            is_strong_outlier = EXCLUDED.is_strong_outlier,
            is_major_outlier = EXCLUDED.is_major_outlier,
            is_extreme_outlier = EXCLUDED.is_extreme_outlier,
            small_channel_outlier = EXCLUDED.small_channel_outlier,
            confidence = EXCLUDED.confidence,
            outlier_rank_score = EXCLUDED.outlier_rank_score,
            warnings = EXCLUDED.warnings;
        """

        with self.client.get_cursor() as cur:
            for rec in records:
                r = dict(rec)
                if isinstance(r.get("warnings"), (list, dict)):
                    r["warnings"] = json.dumps(r["warnings"])
                cur.execute(query, r)
        return True

    def get_outlier_analysis_by_run_id(self, run_id: str) -> List[Dict[str, Any]]:
        return self.client.execute("SELECT * FROM public.video_outlier_analyses WHERE run_id = %s", [run_id])

    def delete_outlier_analysis_by_run_id(self, run_id: str) -> bool:
        self.client.execute("DELETE FROM public.video_outlier_analyses WHERE run_id = %s", [run_id])
        return True

    def verify_niche_schema(self) -> None:
        for table in ("clusters", "subniches", "cluster_videos"):
            self.client.execute(f"SELECT 1 FROM public.{table} LIMIT 1")

    def verify_market_structure_schema(self) -> None:
        self.client.execute("SELECT 1 FROM public.market_structure_analyses LIMIT 1")

    def verify_production_risk_schema(self) -> None:
        self.client.execute("SELECT 1 FROM public.production_risk_analyses LIMIT 1")

    def verify_profitability_schema(self) -> None:
        self.client.execute("SELECT 1 FROM public.cluster_profitability_analyses LIMIT 1")

    def verify_validation_schema(self) -> None:
        self.client.execute("SELECT 1 FROM public.cluster_validation_analyses LIMIT 1")

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

        query = """
        INSERT INTO public.production_risk_analyses (
            run_id, source_market_structure_run_id, source_cluster_run_id, cluster_id,
            analyzed_at, config, quality, metrics, microniche, production_cost_score,
            estimated_hours_low, estimated_hours_high, production_complexity,
            overall_risk_score, risk_level, confidence
        ) VALUES (
            %(run_id)s, %(source_market_structure_run_id)s, %(source_cluster_run_id)s, %(cluster_id)s,
            %(analyzed_at)s, %(config)s, %(quality)s, %(metrics)s, %(microniche)s, %(production_cost_score)s,
            %(estimated_hours_low)s, %(estimated_hours_high)s, %(production_complexity)s,
            %(overall_risk_score)s, %(risk_level)s, %(confidence)s
        ) ON CONFLICT (run_id, cluster_id) DO UPDATE SET
            source_market_structure_run_id = EXCLUDED.source_market_structure_run_id,
            source_cluster_run_id = EXCLUDED.source_cluster_run_id,
            analyzed_at = EXCLUDED.analyzed_at,
            config = EXCLUDED.config,
            quality = EXCLUDED.quality,
            metrics = EXCLUDED.metrics,
            microniche = EXCLUDED.microniche,
            production_cost_score = EXCLUDED.production_cost_score,
            estimated_hours_low = EXCLUDED.estimated_hours_low,
            estimated_hours_high = EXCLUDED.estimated_hours_high,
            production_complexity = EXCLUDED.production_complexity,
            overall_risk_score = EXCLUDED.overall_risk_score,
            risk_level = EXCLUDED.risk_level,
            confidence = EXCLUDED.confidence;
        """
        with self.client.get_cursor() as cur:
            for rec in records:
                r = dict(rec)
                for f in ("config", "quality", "metrics"):
                    if isinstance(r.get(f), (list, dict)):
                        r[f] = json.dumps(r[f])
                cur.execute(query, r)

        return ProductionRiskPersistenceResult(
            run_id=result.run_id, records_written=len(records)
        )

    def verify_production_risk_readback(
        self, expected: Sprint8AnalysisResult
    ) -> ProductionRiskReadbackResult:
        records = self.client.execute(
            "SELECT * FROM public.production_risk_analyses WHERE run_id = %s",
            [expected.run_id]
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
    def _build_profitability_records(
        result: Sprint9AnalysisResult
    ) -> List[Dict[str, Any]]:
        records = []
        for cluster in result.clusters:
            payload = cluster.model_dump(mode="json")
            records.append({
                "run_id": result.run_id,
                "source_cluster_run_id": result.source_cluster_run_id,
                "source_revenue_run_id": result.source_revenue_run_id,
                "source_market_run_id": result.source_market_run_id,
                "source_production_run_id": result.source_production_run_id,
                "dataset_hash": result.dataset_hash,
                "assignments_hash": result.assignments_hash,
                "methodology_version": result.methodology_version,
                "cluster_id": cluster.cluster_id,
                "analyzed_at": result.analyzed_at,
                "quality": result.quality.model_dump(mode="json"),
                "metrics": payload,
                "microniche": cluster.microniche,
                "expected_views_base": cluster.expected_views_range.base,
                "rpm_available": cluster.rpm_range.available,
                "revenue_available": cluster.revenue_scenarios.available,
                "cost_money_available": cluster.production_cost.available,
                "profit_available": cluster.profit_scenarios.available,
                "base_score": cluster.base_score,
                "risk_penalty": cluster.risk_penalty,
                "profitability_score": cluster.profitability_score,
                "classification": cluster.classification.value,
                "confidence": cluster.confidence,
                "component_coverage": cluster.component_coverage,
            })
        return records

    def insert_profitability_analysis(
        self, result: Sprint9AnalysisResult
    ) -> ProfitabilityPersistenceResult:
        if not result.clusters:
            raise ValueError("Sprint 9 analysis has no clusters to persist.")
        cluster_ids = [cluster.cluster_id for cluster in result.clusters]
        if len(cluster_ids) != len(set(cluster_ids)):
            raise ValueError("Duplicate cluster IDs in Sprint 9 analysis.")
        records = self._build_profitability_records(result)
        self.verify_profitability_schema()

        query = """
        INSERT INTO public.cluster_profitability_analyses (
            run_id, source_cluster_run_id, source_revenue_run_id, source_market_run_id,
            source_production_run_id, dataset_hash, assignments_hash, methodology_version,
            cluster_id, analyzed_at, quality, metrics, microniche, expected_views_base,
            rpm_available, revenue_available, cost_money_available, profit_available,
            base_score, risk_penalty, profitability_score, classification, confidence,
            component_coverage
        ) VALUES (
            %(run_id)s, %(source_cluster_run_id)s, %(source_revenue_run_id)s, %(source_market_run_id)s,
            %(source_production_run_id)s, %(dataset_hash)s, %(assignments_hash)s, %(methodology_version)s,
            %(cluster_id)s, %(analyzed_at)s, %(quality)s, %(metrics)s, %(microniche)s, %(expected_views_base)s,
            %(rpm_available)s, %(revenue_available)s, %(cost_money_available)s, %(profit_available)s,
            %(base_score)s, %(risk_penalty)s, %(profitability_score)s, %(classification)s, %(confidence)s,
            %(component_coverage)s
        ) ON CONFLICT (run_id, cluster_id) DO UPDATE SET
            source_cluster_run_id = EXCLUDED.source_cluster_run_id,
            source_revenue_run_id = EXCLUDED.source_revenue_run_id,
            source_market_run_id = EXCLUDED.source_market_run_id,
            source_production_run_id = EXCLUDED.source_production_run_id,
            dataset_hash = EXCLUDED.dataset_hash,
            assignments_hash = EXCLUDED.assignments_hash,
            methodology_version = EXCLUDED.methodology_version,
            analyzed_at = EXCLUDED.analyzed_at,
            quality = EXCLUDED.quality,
            metrics = EXCLUDED.metrics,
            microniche = EXCLUDED.microniche,
            expected_views_base = EXCLUDED.expected_views_base,
            rpm_available = EXCLUDED.rpm_available,
            revenue_available = EXCLUDED.revenue_available,
            cost_money_available = EXCLUDED.cost_money_available,
            profit_available = EXCLUDED.profit_available,
            base_score = EXCLUDED.base_score,
            risk_penalty = EXCLUDED.risk_penalty,
            profitability_score = EXCLUDED.profitability_score,
            classification = EXCLUDED.classification,
            confidence = EXCLUDED.confidence,
            component_coverage = EXCLUDED.component_coverage;
        """
        with self.client.get_cursor() as cur:
            for rec in records:
                r = dict(rec)
                for f in ("quality", "metrics", "component_coverage"):
                    if isinstance(r.get(f), (list, dict)):
                        r[f] = json.dumps(r[f])
                cur.execute(query, r)

        return ProfitabilityPersistenceResult(
            run_id=result.run_id, records_written=len(records)
        )

    @staticmethod
    def _build_validation_records(
        result: Sprint10AnalysisResult
    ) -> List[Dict[str, Any]]:
        records = []
        for cluster in result.clusters:
            payload = cluster.model_dump(mode="json")
            records.append({
                "run_id": result.run_id,
                "source_profitability_run_id": result.source_profitability_run_id,
                "source_cluster_run_id": result.source_cluster_run_id,
                "source_revenue_run_id": result.source_revenue_run_id,
                "source_market_run_id": result.source_market_run_id,
                "source_production_run_id": result.source_production_run_id,
                "dataset_hash": result.dataset_hash,
                "assignments_hash": result.assignments_hash,
                "methodology_version": result.methodology_version,
                "cluster_id": cluster.cluster_id,
                "analyzed_at": result.analyzed_at,
                "quality": result.quality.model_dump(mode="json"),
                "metrics": payload,
                "microniche": cluster.microniche,
                "profitability_score": cluster.profitability_score,
                "validation_score": cluster.validation_score,
                "validation_status": cluster.validation_status.value,
                "validation_confidence": cluster.validation_confidence,
                "false_positive_risk": cluster.false_positive_risk,
                "fragility_score": cluster.fragility_score,
            })
        return records

    def insert_validation_analysis(
        self, result: Sprint10AnalysisResult
    ) -> ValidationPersistenceResult:
        if not result.clusters:
            raise ValueError("Sprint 10 analysis has no clusters to persist.")
        cluster_ids = [cluster.cluster_id for cluster in result.clusters]
        if len(cluster_ids) != len(set(cluster_ids)):
            raise ValueError("Duplicate cluster IDs in Sprint 10 analysis.")
        records = self._build_validation_records(result)
        self.verify_validation_schema()

        query = """
        INSERT INTO public.cluster_validation_analyses (
            run_id, source_profitability_run_id, source_cluster_run_id, source_revenue_run_id,
            source_market_run_id, source_production_run_id, dataset_hash, assignments_hash,
            methodology_version, cluster_id, analyzed_at, quality, metrics, microniche,
            profitability_score, validation_score, validation_status, validation_confidence,
            false_positive_risk, fragility_score
        ) VALUES (
            %(run_id)s, %(source_profitability_run_id)s, %(source_cluster_run_id)s, %(source_revenue_run_id)s,
            %(source_market_run_id)s, %(source_production_run_id)s, %(dataset_hash)s, %(assignments_hash)s,
            %(methodology_version)s, %(cluster_id)s, %(analyzed_at)s, %(quality)s, %(metrics)s, %(microniche)s,
            %(profitability_score)s, %(validation_score)s, %(validation_status)s, %(validation_confidence)s,
            %(false_positive_risk)s, %(fragility_score)s
        ) ON CONFLICT (run_id, cluster_id) DO UPDATE SET
            source_profitability_run_id = EXCLUDED.source_profitability_run_id,
            source_cluster_run_id = EXCLUDED.source_cluster_run_id,
            source_revenue_run_id = EXCLUDED.source_revenue_run_id,
            source_market_run_id = EXCLUDED.source_market_run_id,
            source_production_run_id = EXCLUDED.source_production_run_id,
            dataset_hash = EXCLUDED.dataset_hash,
            assignments_hash = EXCLUDED.assignments_hash,
            methodology_version = EXCLUDED.methodology_version,
            analyzed_at = EXCLUDED.analyzed_at,
            quality = EXCLUDED.quality,
            metrics = EXCLUDED.metrics,
            microniche = EXCLUDED.microniche,
            profitability_score = EXCLUDED.profitability_score,
            validation_score = EXCLUDED.validation_score,
            validation_status = EXCLUDED.validation_status,
            validation_confidence = EXCLUDED.validation_confidence,
            false_positive_risk = EXCLUDED.false_positive_risk,
            fragility_score = EXCLUDED.fragility_score;
        """
        with self.client.get_cursor() as cur:
            for rec in records:
                r = dict(rec)
                for f in ("quality", "metrics"):
                    if isinstance(r.get(f), (list, dict)):
                        r[f] = json.dumps(r[f])
                cur.execute(query, r)

        return ValidationPersistenceResult(
            run_id=result.run_id, records_written=len(records)
        )

    def verify_validation_readback(
        self, expected: Sprint10AnalysisResult
    ) -> ValidationReadbackResult:
        records = self.client.execute(
            "SELECT * FROM public.cluster_validation_analyses WHERE run_id = %s",
            [expected.run_id]
        )
        expected_records = self._build_validation_records(expected)
        keys = [(record.get("run_id"), record.get("cluster_id")) for record in records]
        duplicate_records = sum(
            count - 1 for count in Counter(keys).values() if count > 1
        )
        payload_mismatches = self._payload_mismatches(
            expected_records, records, ("run_id", "cluster_id")
        )
        provenance_mismatches = 0
        for rec in records:
            if (
                rec.get("dataset_hash") != expected.dataset_hash
                or rec.get("assignments_hash") != expected.assignments_hash
                or rec.get("methodology_version") != expected.methodology_version
                or rec.get("source_profitability_run_id") != expected.source_profitability_run_id
                or rec.get("source_cluster_run_id") != expected.source_cluster_run_id
                or rec.get("source_revenue_run_id") != expected.source_revenue_run_id
                or rec.get("source_market_run_id") != expected.source_market_run_id
                or rec.get("source_production_run_id") != expected.source_production_run_id
            ):
                provenance_mismatches += 1

        expected_keys = {
            (expected.run_id, cluster.cluster_id) for cluster in expected.clusters
        }
        verified = (
            len(records) == len(expected_records)
            and set(keys) == expected_keys
            and duplicate_records == 0
            and payload_mismatches == 0
            and provenance_mismatches == 0
        )
        return ValidationReadbackResult(
            run_id=expected.run_id,
            expected_records=len(expected_records),
            actual_records=len(records),
            unique_clusters=len({record.get("cluster_id") for record in records}),
            duplicate_records=duplicate_records,
            payload_mismatches=payload_mismatches,
            provenance_mismatches=provenance_mismatches,
            verified=verified,
        )

    def verify_profitability_readback(
        self, expected: Sprint9AnalysisResult
    ) -> ProfitabilityReadbackResult:
        records = self.client.execute(
            "SELECT * FROM public.cluster_profitability_analyses WHERE run_id = %s",
            [expected.run_id]
        )
        expected_records = self._build_profitability_records(expected)
        keys = [(record.get("run_id"), record.get("cluster_id")) for record in records]
        duplicate_records = sum(
            count - 1 for count in Counter(keys).values() if count > 1
        )
        payload_mismatches = self._payload_mismatches(
            expected_records, records, ("run_id", "cluster_id")
        )
        provenance_mismatches = 0
        for rec in records:
            if (
                rec.get("dataset_hash") != expected.dataset_hash
                or rec.get("assignments_hash") != expected.assignments_hash
                or rec.get("methodology_version") != expected.methodology_version
            ):
                provenance_mismatches += 1

        expected_keys = {
            (expected.run_id, cluster.cluster_id) for cluster in expected.clusters
        }
        verified = (
            len(records) == len(expected_records)
            and set(keys) == expected_keys
            and duplicate_records == 0
            and payload_mismatches == 0
            and provenance_mismatches == 0
        )
        return ProfitabilityReadbackResult(
            run_id=expected.run_id,
            expected_records=len(expected_records),
            actual_records=len(records),
            unique_clusters=len({record.get("cluster_id") for record in records}),
            duplicate_records=duplicate_records,
            payload_mismatches=payload_mismatches,
            provenance_mismatches=provenance_mismatches,
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

        query = """
        INSERT INTO public.market_structure_analyses (
            run_id, source_cluster_run_id, cluster_id, analyzed_at, config, quality,
            metrics, microniche, top_5_rank, market_structure_score, competition_score,
            accessibility_score, content_depth_score, trend_score, evergreen_score,
            evergreen_class, market_structure_class, confidence
        ) VALUES (
            %(run_id)s, %(source_cluster_run_id)s, %(cluster_id)s, %(analyzed_at)s, %(config)s, %(quality)s,
            %(metrics)s, %(microniche)s, %(top_5_rank)s, %(market_structure_score)s, %(competition_score)s,
            %(accessibility_score)s, %(content_depth_score)s, %(trend_score)s, %(evergreen_score)s,
            %(evergreen_class)s, %(market_structure_class)s, %(confidence)s
        ) ON CONFLICT (run_id, cluster_id) DO UPDATE SET
            source_cluster_run_id = EXCLUDED.source_cluster_run_id,
            analyzed_at = EXCLUDED.analyzed_at,
            config = EXCLUDED.config,
            quality = EXCLUDED.quality,
            metrics = EXCLUDED.metrics,
            microniche = EXCLUDED.microniche,
            top_5_rank = EXCLUDED.top_5_rank,
            market_structure_score = EXCLUDED.market_structure_score,
            competition_score = EXCLUDED.competition_score,
            accessibility_score = EXCLUDED.accessibility_score,
            content_depth_score = EXCLUDED.content_depth_score,
            trend_score = EXCLUDED.trend_score,
            evergreen_score = EXCLUDED.evergreen_score,
            evergreen_class = EXCLUDED.evergreen_class,
            market_structure_class = EXCLUDED.market_structure_class,
            confidence = EXCLUDED.confidence;
        """
        with self.client.get_cursor() as cur:
            for rec in records:
                r = dict(rec)
                for f in ("config", "quality", "metrics"):
                    if isinstance(r.get(f), (list, dict)):
                        r[f] = json.dumps(r[f])
                cur.execute(query, r)

        return MarketStructurePersistenceResult(
            run_id=result.run_id, records_written=len(records)
        )

    def verify_market_structure_readback(
        self, expected: Sprint7AnalysisResult
    ) -> MarketStructureReadbackResult:
        records = self.client.execute(
            "SELECT * FROM public.market_structure_analyses WHERE run_id = %s",
            [expected.run_id]
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

        q_clusters = """
        INSERT INTO public.clusters (
            cluster_id, run_id, algorithm, semantic_provider, parameters,
            video_count, unique_channels, dominant_channel_share, semantic_quality,
            confidence, signal_score, created_at
        ) VALUES (
            %(cluster_id)s, %(run_id)s, %(algorithm)s, %(semantic_provider)s, %(parameters)s,
            %(video_count)s, %(unique_channels)s, %(dominant_channel_share)s, %(semantic_quality)s,
            %(confidence)s, %(signal_score)s, %(created_at)s
        ) ON CONFLICT (run_id, cluster_id) DO UPDATE SET
            algorithm = EXCLUDED.algorithm,
            semantic_provider = EXCLUDED.semantic_provider,
            parameters = EXCLUDED.parameters,
            video_count = EXCLUDED.video_count,
            unique_channels = EXCLUDED.unique_channels,
            dominant_channel_share = EXCLUDED.dominant_channel_share,
            semantic_quality = EXCLUDED.semantic_quality,
            confidence = EXCLUDED.confidence,
            signal_score = EXCLUDED.signal_score;
        """

        q_subniches = """
        INSERT INTO public.subniches (
            cluster_id, run_id, niche, subniche, microniche, summary, label_confidence, created_at
        ) VALUES (
            %(cluster_id)s, %(run_id)s, %(niche)s, %(subniche)s, %(microniche)s, %(summary)s, %(label_confidence)s, %(created_at)s
        ) ON CONFLICT (run_id, cluster_id) DO UPDATE SET
            niche = EXCLUDED.niche,
            subniche = EXCLUDED.subniche,
            microniche = EXCLUDED.microniche,
            summary = EXCLUDED.summary,
            label_confidence = EXCLUDED.label_confidence;
        """

        q_cvideos = """
        INSERT INTO public.cluster_videos (
            cluster_id, run_id, video_id, distance_to_centroid
        ) VALUES (
            %(cluster_id)s, %(run_id)s, %(video_id)s, %(distance_to_centroid)s
        ) ON CONFLICT (run_id, video_id) DO UPDATE SET
            cluster_id = EXCLUDED.cluster_id,
            distance_to_centroid = EXCLUDED.distance_to_centroid;
        """

        with self.client.get_cursor() as cur:
            for rec in cluster_records:
                r = dict(rec)
                if isinstance(r.get("parameters"), (list, dict)):
                    r["parameters"] = json.dumps(r["parameters"])
                cur.execute(q_clusters, r)
            for rec in subniche_records:
                cur.execute(q_subniches, rec)
            for rec in cluster_video_records:
                cur.execute(q_cvideos, rec)

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
            if "created_at" in normalized:
                normalized.pop("created_at")
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
        c_records = self.client.execute("SELECT * FROM public.clusters WHERE run_id = %s", [run_id])
        sn_records = self.client.execute("SELECT * FROM public.subniches WHERE run_id = %s", [run_id])
        cv_records = self.client.execute("SELECT * FROM public.cluster_videos WHERE run_id = %s", [run_id])
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
            not self.client.execute("SELECT 1 FROM public.videos WHERE video_id = %s", [video_id])
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

    def upsert_channels(self, channels: List[YouTubeChannel]) -> int:
        if not channels:
            return 0
        query = """
        INSERT INTO public.channels (
            channel_id, title, description, published_at, country
        ) VALUES (
            %(channel_id)s, %(title)s, %(description)s, %(published_at)s, %(country)s
        ) ON CONFLICT (channel_id) DO UPDATE SET
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            published_at = EXCLUDED.published_at,
            country = EXCLUDED.country;
        """
        with self.client.get_cursor() as cur:
            for ch in channels:
                rec = {
                    "channel_id": ch.channel_id,
                    "title": ch.channel_title,
                    "description": ch.channel_description,
                    "published_at": ch.published_at,
                    "country": ch.country
                }
                cur.execute(query, rec)
        return len(channels)

    def upsert_videos(self, videos: List[YouTubeVideo]) -> int:
        if not videos:
            return 0
        query = """
        INSERT INTO public.videos (
            video_id, channel_id, title, description, published_at, duration,
            duration_seconds, caption, definition, licensed_content,
            default_language, default_audio_language
        ) VALUES (
            %(video_id)s, %(channel_id)s, %(title)s, %(description)s, %(published_at)s, %(duration)s,
            %(duration_seconds)s, %(caption)s, %(definition)s, %(licensed_content)s,
            %(default_language)s, %(default_audio_language)s
        ) ON CONFLICT (video_id) DO UPDATE SET
            channel_id = EXCLUDED.channel_id,
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            published_at = EXCLUDED.published_at,
            duration = EXCLUDED.duration,
            duration_seconds = EXCLUDED.duration_seconds,
            caption = EXCLUDED.caption,
            definition = EXCLUDED.definition,
            licensed_content = EXCLUDED.licensed_content,
            default_language = EXCLUDED.default_language,
            default_audio_language = EXCLUDED.default_audio_language;
        """
        with self.client.get_cursor() as cur:
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
                cur.execute(query, rec)
        return len(videos)

    def insert_channel_metrics(
        self,
        channels: List[YouTubeChannel],
        checked_at: Optional[str] = None
    ) -> int:
        if not channels:
            return 0
        ts = checked_at or datetime.now(timezone.utc).isoformat()
        query = """
        INSERT INTO public.channel_metrics (
            channel_id, subscriber_count, video_count, view_count, collected_at
        ) VALUES (
            %(channel_id)s, %(subscriber_count)s, %(video_count)s, %(view_count)s, %(collected_at)s
        );
        """
        with self.client.get_cursor() as cur:
            for ch in channels:
                rec = {
                    "channel_id": ch.channel_id,
                    "subscriber_count": ch.subscriber_count,
                    "video_count": ch.video_count,
                    "view_count": ch.view_count,
                    "collected_at": ts
                }
                cur.execute(query, rec)
        return len(channels)

    def insert_video_metrics(
        self,
        videos: List[YouTubeVideo],
        checked_at: Optional[str] = None
    ) -> int:
        if not videos:
            return 0
        ts = checked_at or datetime.now(timezone.utc).isoformat()
        query = """
        INSERT INTO public.video_metrics (
            video_id, view_count, like_count, comment_count, collected_at
        ) VALUES (
            %(video_id)s, %(view_count)s, %(like_count)s, %(comment_count)s, %(collected_at)s
        );
        """
        with self.client.get_cursor() as cur:
            for v in videos:
                rec = {
                    "video_id": v.video_id,
                    "view_count": v.view_count,
                    "like_count": v.like_count,
                    "comment_count": v.comment_count,
                    "collected_at": ts
                }
                cur.execute(query, rec)
        return len(videos)

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
            f"Starting PostgreSQL persistence for collection query='{collection_result.query}': "
            f"{channels_rec} channels, {videos_rec} videos"
        )

        ch_upserted = 0
        v_upserted = 0
        ch_metrics_inserted = 0
        v_metrics_inserted = 0

        if collection_result.channels:
            try:
                ch_upserted = self.upsert_channels(collection_result.channels)
                db_ops += 1
            except Exception as exc:
                msg = f"Failed to upsert channels: {exc}"
                warnings.append(msg)
                logger.error(msg)
                raise

        if collection_result.videos:
            try:
                v_upserted = self.upsert_videos(collection_result.videos)
                db_ops += 1
            except Exception as exc:
                msg = f"Failed to upsert videos: {exc}"
                warnings.append(msg)
                logger.error(msg)
                raise

        if collection_result.channels:
            try:
                ch_metrics_inserted = self.insert_channel_metrics(collection_result.channels, checked_at=ts)
                db_ops += 1
            except Exception as exc:
                msg = f"Failed to insert channel metrics: {exc}"
                warnings.append(msg)
                logger.error(msg)
                raise

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
            f"PostgreSQL persistence complete: channels_upserted={ch_upserted}, videos_upserted={v_upserted}, "
            f"ch_metrics={ch_metrics_inserted}, v_metrics={v_metrics_inserted}, db_ops={db_ops}, elapsed={elapsed}s"
        )

        return res
