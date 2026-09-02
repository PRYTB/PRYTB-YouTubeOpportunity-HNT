import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import numpy as np

from app.analytics.semantic_provider import SemanticProvider, TFIDFLocalSemanticProvider, OmniRouteEmbeddingProvider
from app.analytics.text_normalizer import clean_text_for_embedding
from app.analytics.clustering_engine import ClusterOptimizer, detect_near_duplicates
from app.analytics.cluster_analyzer import (
    analyze_channel_diversity,
    cross_reference_outliers,
    select_representative_titles,
    calculate_cluster_confidence,
    calculate_cluster_signal_score
)
from app.analytics.labeler import ClusterLabeler, validate_label_quality
from app.analytics.outlier_engine import OutlierEngine
from app.database.repositories import YouTubeRepository
from app.models.niche import NicheCluster, NicheMiningResult, ClusterHierarchy
from app.utils.config import settings
from app.utils.logger import logger


class NicheMiner:
    """
    Core engine for Sprint 5 - Niche Miner.
    Processes videos, titles, and outlier signals into coherent, structured thematic clusters.
    """

    def __init__(
        self,
        repository: Optional[YouTubeRepository] = None,
        semantic_provider: Optional[SemanticProvider] = None,
        labeler: Optional[ClusterLabeler] = None,
        outlier_engine: Optional[OutlierEngine] = None
    ):
        self.repository = repository or YouTubeRepository()
        self.semantic_provider = semantic_provider or TFIDFLocalSemanticProvider()
        self.labeler = labeler or ClusterLabeler()
        self.outlier_engine = outlier_engine or OutlierEngine(repository=self.repository)

    def mine(
        self,
        limit: Optional[int] = None,
        algorithm: str = "kmeans",
        min_cluster_size: int = 2
    ) -> NicheMiningResult:
        """Alias for mine_niches for API consistency."""
        return self.mine_niches(limit=limit, algorithm=algorithm, min_cluster_size=min_cluster_size)

    def mine_niches(
        self,
        limit: Optional[int] = None,
        algorithm: str = "kmeans",
        min_cluster_size: int = 2
    ) -> NicheMiningResult:
        start_time = time.time()
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        logger.info(f"Starting NicheMiner run {run_id} using {self.semantic_provider.provider_name}...")

        # 1. Fetch videos from DB
        all_videos = self.repository.get_all_videos()
        videos_considered = len(all_videos)

        if limit and limit > 0:
            videos_to_process = all_videos[:limit]
        else:
            videos_to_process = all_videos

        videos_embedded = 0
        videos_skipped = 0

        valid_videos = []
        texts_to_embed = []
        titles = []
        channel_ids = []

        for v in videos_to_process:
            v_id = v.get("video_id")
            v_title = v.get("title", "")
            v_desc = v.get("description", "")
            c_id = v.get("channel_id", "")

            if not v_id or not v_title:
                videos_skipped += 1
                continue

            cleaned_text = clean_text_for_embedding(v_title, v_desc)
            if not cleaned_text:
                videos_skipped += 1
                continue

            valid_videos.append(v)
            texts_to_embed.append(cleaned_text)
            titles.append(v_title)
            channel_ids.append(c_id)
            videos_embedded += 1

        if not texts_to_embed:
            logger.warning("No valid videos to embed.")
            return NicheMiningResult(
                run_id=run_id,
                algorithm=algorithm,
                parameters={"min_cluster_size": min_cluster_size},
                semantic_provider=self.semantic_provider.provider_name,
                videos_considered=videos_considered,
                videos_embedded=0,
                videos_skipped=videos_skipped,
                created_at=created_at,
                elapsed_seconds=round(time.time() - start_time, 2)
            )

        # 2. Semantic embeddings
        logger.info(f"Embedding {len(texts_to_embed)} video texts...")
        embeddings = self.semantic_provider.embed_texts(texts_to_embed)

        # 3. Fit optimal clusters
        optimizer = ClusterOptimizer()
        labels, selected_algo, params, quality_score = optimizer.fit_optimal_clusters(
            embeddings=embeddings,
            algorithm=algorithm
        )

        params["min_cluster_size"] = min_cluster_size

        # 4. Outlier crossover map
        logger.info("Computing outlier crossover statistics...")
        outlier_results = self.outlier_engine.analyze_all()
        outliers_map = {res.video_id: res for res in outlier_results}

        # 5. Group by cluster label & analyze quality/diversity/labels
        unique_cluster_ids = sorted(list(set(labels)))
        clusters: List[NicheCluster] = []
        unassigned_count = 0

        for cid in unique_cluster_ids:
            indices = [i for i, l in enumerate(labels) if l == cid]
            cluster_vids = [valid_videos[i]["video_id"] for i in indices]
            cluster_chans = [channel_ids[i] for i in indices]
            v_count = len(cluster_vids)

            if v_count < min_cluster_size and len(unique_cluster_ids) > 1:
                unassigned_count += v_count
                continue

            # Diversity metrics
            uniq_chans, dom_share, diversity_cat, warnings = analyze_channel_diversity(cluster_chans)

            # Representative titles (closest to centroid)
            rep_titles = select_representative_titles(
                embeddings=embeddings,
                cluster_indices=indices,
                titles=titles
            )

            # Outlier stats
            outlier_stats = cross_reference_outliers(
                cluster_video_ids=cluster_vids,
                outliers_map=outliers_map
            )

            # Structured labeling (Niche -> Subniche -> Microniche)
            hierarchy: ClusterHierarchy = self.labeler.label_cluster(rep_titles)

            # Validate label quality
            l_quality_score, l_warnings = validate_label_quality(
                niche=hierarchy.niche,
                subniche=hierarchy.subniche,
                microniche=hierarchy.microniche,
                representative_titles=rep_titles
            )
            warnings.extend(l_warnings)

            # Calculate confidence
            confidence = calculate_cluster_confidence(
                semantic_quality=quality_score,
                video_count=v_count,
                unique_channels=uniq_chans,
                dominant_channel_share=dom_share,
                outlier_count=outlier_stats["outlier_count"],
                label_quality_score=l_quality_score
            )

            # Calculate ClusterSignalScore
            signal_score = calculate_cluster_signal_score(
                semantic_quality=quality_score,
                outlier_count=outlier_stats["outlier_count"],
                video_count=v_count,
                dominant_channel_share=dom_share,
                confidence=confidence
            )

            cluster_obj = NicheCluster(
                cluster_id=int(cid),
                video_ids=cluster_vids,
                video_count=v_count,
                unique_channels=uniq_chans,
                dominant_channel_share=dom_share,
                channel_diversity=diversity_cat,
                representative_titles=rep_titles,
                niche=hierarchy.niche,
                subniche=hierarchy.subniche,
                microniche=hierarchy.microniche,
                summary=hierarchy.summary,
                label_confidence=hierarchy.confidence,
                label_quality_score=l_quality_score,
                label_warnings=l_warnings,
                outlier_count=outlier_stats["outlier_count"],
                strong_outlier_count=outlier_stats["strong_outlier_count"],
                major_outlier_count=outlier_stats["major_outlier_count"],
                median_outlier_ratio=outlier_stats["median_outlier_ratio"],
                max_outlier_ratio=outlier_stats["max_outlier_ratio"],
                semantic_quality=quality_score,
                confidence=confidence,
                cluster_signal_score=signal_score,
                warnings=warnings
            )
            clusters.append(cluster_obj)


        # Sort clusters by ClusterSignalScore
        clusters.sort(key=lambda c: c.cluster_signal_score, reverse=True)

        elapsed = round(time.time() - start_time, 2)

        res = NicheMiningResult(
            run_id=run_id,
            algorithm=selected_algo,
            parameters=params,
            semantic_provider=self.semantic_provider.provider_name,
            videos_considered=videos_considered,
            videos_embedded=videos_embedded,
            videos_skipped=videos_skipped,
            total_clusters=len(clusters),
            unassigned_count=unassigned_count,
            quality_metric_name="silhouette_score",
            quality_metric_value=quality_score,
            clusters=clusters,
            elapsed_seconds=elapsed,
            created_at=created_at
        )

        logger.info(f"NicheMiner run {run_id} completed: generated {len(clusters)} clusters in {elapsed}s.")
        return res
