"""
Sprint 10 Adversarial Opportunity Validator Engine.

Challenges profitability candidates from Sprint 9 before promotion.
Evaluates sample bias, channel dominance, one-video dominance, trend spikes,
data sparsity, weak economics, production assumptions, semantic mixing,
insufficient depth, and cross-signal consistency.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from statistics import mean, median, stdev
from typing import Any, Dict, List, Optional, Tuple

from app.config.validation_config import ValidationConfig, validation_config
from app.models.market_structure import ClusterMarketStructure, ContentDepthBand, EvergreenClass
from app.models.outliers import VideoOutlierResult
from app.models.production_risk import ClusterProductionRisk, RiskLevel
from app.models.profitability import ClusterProfitabilityAnalysis
from app.models.validation import (
    ClusterValidationAnalysis,
    Sprint10AnalysisResult,
    Sprint10QualityMetrics,
    ValidationStatus,
)


class OpportunityValidator:
    """Adversarial Opportunity Validator for PRYTB Sprint 10."""

    def __init__(
        self,
        config: Optional[ValidationConfig] = None,
        methodology_version: str = "sprint10-v1",
    ):
        self.config = config or validation_config
        self.methodology_version = methodology_version

    def validate_cluster(
        self,
        run_id: str,
        profitability_analysis: ClusterProfitabilityAnalysis,
        cluster_videos: List[Dict[str, Any]],
        market_structure: Optional[ClusterMarketStructure] = None,
        production_risk: Optional[ClusterProductionRisk] = None,
        outlier_results: Optional[List[VideoOutlierResult]] = None,
        source_profitability_run_id: str = "",
        source_cluster_run_id: str = "",
        source_revenue_run_id: str = "",
        source_market_run_id: str = "",
        source_production_run_id: str = "",
        dataset_hash: str = "",
        assignments_hash: str = "",
    ) -> ClusterValidationAnalysis:
        critical_failures: List[str] = []
        warnings: List[str] = []
        positive_evidence: List[str] = []
        contradictory_evidence: List[str] = []
        missing_evidence: List[str] = []

        cid = profitability_analysis.cluster_id
        video_count = len(cluster_videos)

        # -------------------------------------------------------------
        # 1. ONE-VIDEO DOMINANCE & SENSITIVITY TEST
        # -------------------------------------------------------------
        views_list = [
            float(v.get("view_count"))
            for v in cluster_videos
            if v.get("view_count") is not None and float(v.get("view_count")) >= 0
        ]
        total_views = sum(views_list) if views_list else 0.0

        if views_list and total_views > 0:
            top_video_views = max(views_list)
            top_video_view_share = top_video_views / total_views
        else:
            top_video_views = 0.0
            top_video_view_share = 0.0

        # Outlier share
        cluster_outliers = outlier_results or []
        if cluster_outliers:
            outlier_ranks = [o.outlier_rank_score for o in cluster_outliers]
            total_outlier_rank = sum(outlier_ranks)
            top_outlier_rank = max(outlier_ranks) if outlier_ranks else 0.0
            top_video_outlier_share = top_outlier_rank / total_outlier_rank if total_outlier_rank > 0 else 0.0
        else:
            top_video_outlier_share = 0.0

        # Leave-one-out calculation
        if len(views_list) > 1:
            sorted_views = sorted(views_list)
            # Remove top video
            views_no_top = sorted_views[:-1]
            med_no_top = float(median(views_no_top))
            demand_without_top_video = min(100.0, max(10.0, math.log10(med_no_top + 1.0) * 18.0))
        elif len(views_list) == 1:
            demand_without_top_video = 0.0
        else:
            demand_without_top_video = 0.0

        # Estimate score_without_top_video: replace demand_score in profitability base score
        original_prof_score = profitability_analysis.profitability_score
        demand_weight = 0.15
        known_w = profitability_analysis.known_weight or 1.0
        orig_demand = profitability_analysis.demand_score

        w_sum_no_top = (profitability_analysis.base_score * known_w) - (orig_demand * demand_weight) + (demand_without_top_video * demand_weight)
        base_no_top = w_sum_no_top / known_w if known_w > 0 else 0.0
        score_without_top_video = min(100.0, max(0.0, base_no_top - profitability_analysis.risk_penalty))

        if top_video_view_share >= self.config.one_video_dominance_share_threshold:
            warnings.append("ONE_VIDEO_DEPENDENT")
            contradictory_evidence.append(
                f"Cluster demand is dominated by a single video ({top_video_view_share*100:.1f}% view share)"
            )

        # -------------------------------------------------------------
        # 2. CHANNEL DOMINANCE & CONCENTRATION
        # -------------------------------------------------------------
        channel_ids = [str(v.get("channel_id")) for v in cluster_videos if v.get("channel_id")]
        unique_channels = len(set(channel_ids))

        if market_structure:
            dominant_channel_share = market_structure.dominant_channel_share / 100.0
            channel_hhi = market_structure.channel_hhi
        else:
            if channel_ids:
                from collections import Counter
                counts = Counter(channel_ids).values()
                dominant_channel_share = max(counts) / len(channel_ids)
                channel_hhi = sum((c / len(channel_ids) * 100) ** 2 for c in counts)
            else:
                dominant_channel_share = 0.0
                channel_hhi = 0.0

        # Calculate top-3 channel share
        if channel_ids:
            from collections import Counter
            top_3_sum = sum(cnt for _, cnt in Counter(channel_ids).most_common(3))
            top_3_channel_share = top_3_sum / len(channel_ids)
        else:
            top_3_channel_share = 0.0

        # Score without dominant channel: reduce demand & outlier component contribution by 30% if single channel dominates
        if dominant_channel_share >= self.config.channel_dominance_share_threshold:
            score_without_dominant_channel = max(0.0, original_prof_score - (dominant_channel_share * 25.0))
            warnings.append("SINGLE_CHANNEL_DEPENDENT")
            contradictory_evidence.append(
                f"Cluster is dominated by a single publisher ({dominant_channel_share*100:.1f}% share)"
            )
        else:
            score_without_dominant_channel = original_prof_score

        if top_3_channel_share >= self.config.top_3_channel_share_threshold:
            warnings.append("HIGH_CHANNEL_CONCENTRATION")

        channel_diversity_val = min(100.0, max(0.0, (1.0 - dominant_channel_share) * 100.0))

        # -------------------------------------------------------------
        # 3. OUTLIER ROBUSTNESS
        # -------------------------------------------------------------
        outlier_count = len(cluster_outliers)
        outlier_channels = {o.channel_id for o in cluster_outliers if o.channel_id}
        small_outliers = sum(1 for o in cluster_outliers if o.is_small_channel or o.small_channel_outlier)

        if outlier_count >= 3 and len(outlier_channels) >= 2:
            outlier_diversity_val = 85.0
            positive_evidence.append(f"Repeatable outliers across {len(outlier_channels)} creators")
        elif outlier_count >= 1:
            outlier_diversity_val = 40.0
            warnings.append("Isolated viral outlier evidence")
        else:
            outlier_diversity_val = 20.0
            missing_evidence.append("No strong outlier evidence found in cluster")

        # -------------------------------------------------------------
        # 4. TEMPORAL ROBUSTNESS
        # -------------------------------------------------------------
        if market_structure:
            if market_structure.evergreen_class == EvergreenClass.EVERGREEN:
                temporal_val = 90.0
                positive_evidence.append("Evergreen demand stability")
            elif market_structure.evergreen_class == EvergreenClass.SEMI_EVERGREEN:
                temporal_val = 70.0
            elif market_structure.evergreen_class == EvergreenClass.TREND or market_structure.is_trend:
                temporal_val = 30.0
                warnings.append("RECENT_TREND_DEPENDENT")
                contradictory_evidence.append("Cluster demand is trend-dependent / decaying")
            else:
                temporal_val = 50.0
        else:
            temporal_val = 50.0
            missing_evidence.append("Temporal robustness evidence missing")

        # -------------------------------------------------------------
        # 5. EXPECTED VIEWS STABILITY
        # -------------------------------------------------------------
        ev_range = profitability_analysis.expected_views_range
        if ev_range.base > 0:
            iqr = ev_range.high - ev_range.low
            rel_spread = iqr / ev_range.base
            # Lower spread = higher stability
            expected_views_stability = min(100.0, max(0.0, 100.0 - (rel_spread * 25.0)))
        else:
            expected_views_stability = 0.0

        if expected_views_stability < 40.0:
            warnings.append("HIGH_EXPECTED_VIEWS_VARIANCE")

        # -------------------------------------------------------------
        # 6. ECONOMIC VALIDATION
        # -------------------------------------------------------------
        if not profitability_analysis.rpm_range.available:
            warnings.append("NO_MONETARY_BENCHMARK")
            missing_evidence.append("No explicit monetary RPM benchmark available")

        # Sprint 6 AudienceEconomicValue has limited dispersion (Tier A fallback)
        if profitability_analysis.geography_score == 60.0:
            warnings.append("ECONOMIC_SIGNAL_ASSUMPTION_HEAVY")

        if profitability_analysis.revenue_potential_score >= 70.0 and not profitability_analysis.rpm_range.available:
            economic_val = 50.0
            contradictory_evidence.append("High economic revenue potential asserted with zero RPM benchmark")
        else:
            economic_val = profitability_analysis.revenue_potential_score

        # -------------------------------------------------------------
        # 7. PRODUCTION VALIDATION
        # -------------------------------------------------------------
        if production_risk and production_risk.risk_level != RiskLevel.UNKNOWN:
            prod_val = max(0.0, 100.0 - production_risk.overall_risk_score)
            if production_risk.faceless_feasibility.value == "HIGH":
                positive_evidence.append("High faceless feasibility confirmed")
        else:
            prod_val = 40.0
            warnings.append("WEAK_PRODUCTION_EVIDENCE")
            missing_evidence.append("Production risk & feasibility evidence unvalidated")

        # -------------------------------------------------------------
        # 8. CONTENT DEPTH VALIDATION
        # -------------------------------------------------------------
        # Sprint 7 content depth is 10/10 UNDETERMINED. Preserve this truth!
        if market_structure and market_structure.content_depth_band not in (ContentDepthBand.UNDETERMINED, ContentDepthBand.UNKNOWN):
            depth_val = market_structure.content_depth_score
        else:
            depth_val = 0.0
            warnings.append("DEPTH_NOT_VALIDATED")
            missing_evidence.append("Content depth is UNDETERMINED (10/10 content depth unvalidated)")

        # -------------------------------------------------------------
        # 9. SEMANTIC COHERENCE CHECK
        # -------------------------------------------------------------
        if market_structure and market_structure.semantic_diversity is not None:
            # semantic_diversity = unique_title_signatures / total_titled_videos.
            # Higher semantic_diversity means more diverse title signatures (less duplication).
            # Near duplicate count tracks duplicated title structures.
            semantic_val = min(100.0, max(0.0, market_structure.semantic_diversity * 100.0))
            if market_structure.near_duplicate_count > (video_count * 0.5):
                warnings.append("HIGH_NEAR_DUPLICATE_TITLE_SHARE")
        else:
            semantic_val = 70.0  # Baseline reasonable title coherence

        # -------------------------------------------------------------
        # 10. SAMPLE ADEQUACY
        # -------------------------------------------------------------
        v_score = min(100.0, (video_count / self.config.sample_adequacy_optimal_videos) * 100.0)
        ch_score = min(100.0, (unique_channels / self.config.sample_adequacy_min_channels) * 100.0)
        sample_adequacy = (v_score * 0.6) + (ch_score * 0.4)

        if video_count < self.config.sample_adequacy_min_videos:
            warnings.append("SMALL_SAMPLE_SIZE")
            missing_evidence.append(f"Small cluster video sample ({video_count} videos)")

        # -------------------------------------------------------------
        # 11. CROSS-SIGNAL CONSISTENCY
        # -------------------------------------------------------------
        cross_signals: List[float] = []

        # Check demand vs concentration
        if profitability_analysis.demand_score > 60.0 and dominant_channel_share > 0.5:
            cross_signals.append(30.0)
            contradictory_evidence.append("High apparent demand driven by single channel dominance")
        else:
            cross_signals.append(80.0)

        # Check high profitability vs unknown depth
        if original_prof_score > 70.0 and depth_val == 0.0:
            cross_signals.append(40.0)
            contradictory_evidence.append("High profitability ranking with unvalidated content depth")
        else:
            cross_signals.append(80.0)

        # Check high score vs low confidence
        if original_prof_score > 70.0 and profitability_analysis.confidence < 50.0:
            cross_signals.append(30.0)
            warnings.append("HIGH_SCORE_LOW_CONFIDENCE")
            contradictory_evidence.append("High profitability score coupled with low confidence")
        else:
            cross_signals.append(80.0)

        cross_signal_consistency = mean(cross_signals)

        # -------------------------------------------------------------
        # 12. COUNTERFACTUAL PERTURBATIONS & STRESS-ADJUSTED SCORE
        # -------------------------------------------------------------
        # Stress test: simultaneous removal of top video impact & economic assumption reduction
        stress_adjusted_score = min(
            score_without_top_video,
            score_without_dominant_channel
        )
        if depth_val == 0.0:
            stress_adjusted_score = max(0.0, stress_adjusted_score - 5.0)

        stress_score_delta = original_prof_score - stress_adjusted_score

        # -------------------------------------------------------------
        # 13. FRAGILITY SCORE (0-100)
        # -------------------------------------------------------------
        # High fragility = changes substantially under perturbation
        fragility_components = [
            min(100.0, top_video_view_share * 100.0),
            min(100.0, dominant_channel_share * 100.0),
            min(100.0, max(0.0, (100.0 - sample_adequacy))),
            min(100.0, max(0.0, stress_score_delta * 2.5)),
            min(100.0, max(0.0, (100.0 - profitability_analysis.component_coverage * 100.0))),
        ]
        fragility_score = min(100.0, max(0.0, mean(fragility_components)))

        # -------------------------------------------------------------
        # 14. FALSE POSITIVE RISK (0-100)
        # -------------------------------------------------------------
        # Uses fragility, concentration, sample inadequacy, missing evidence & contradictions
        fp_components = [
            fragility_score * 0.35,
            (100.0 - sample_adequacy) * 0.20,
            (100.0 - cross_signal_consistency) * 0.25,
            (100.0 - expected_views_stability) * 0.20,
        ]
        false_positive_risk = min(100.0, max(0.0, sum(fp_components)))

        # -------------------------------------------------------------
        # 15. VALIDATION SCORE (0-100) & CONFIDENCE
        # -------------------------------------------------------------
        val_weighted_sum = (
            sample_adequacy * self.config.weight_sample_adequacy +
            channel_diversity_val * self.config.weight_channel_diversity +
            outlier_diversity_val * self.config.weight_outlier_robustness +
            temporal_val * self.config.weight_temporal_robustness +
            expected_views_stability * self.config.weight_expected_views_stability +
            economic_val * self.config.weight_economic_validation +
            prod_val * self.config.weight_production_validation +
            depth_val * self.config.weight_depth_validation +
            semantic_val * self.config.weight_semantic_coherence +
            cross_signal_consistency * self.config.weight_cross_signal_consistency
        )

        validation_score = min(100.0, max(0.0, val_weighted_sum))
        evidence_stability = max(0.0, 100.0 - fragility_score)

        validation_confidence = min(
            100.0,
            max(0.0, (profitability_analysis.confidence * 0.5) + (sample_adequacy * 0.3) + (evidence_stability * 0.2))
        )

        # -------------------------------------------------------------
        # 16. VALIDATION GATE & STATUS DETERMINATION
        # -------------------------------------------------------------
        # Critical failure check
        if dominant_channel_share >= 0.85:
            critical_failures.append("CRITICAL_SINGLE_CHANNEL_DOMINANCE")
        if top_video_view_share >= 0.85:
            critical_failures.append("CRITICAL_SINGLE_VIDEO_DOMINANCE")
        if false_positive_risk >= 80.0:
            critical_failures.append("CRITICAL_HIGH_FALSE_POSITIVE_RISK")

        if critical_failures:
            validation_status = ValidationStatus.FAIL
        elif depth_val == 0.0 and sample_adequacy < 40.0:
            validation_status = ValidationStatus.INSUFFICIENT_EVIDENCE
        elif (
            validation_score >= self.config.pass_validation_score_threshold
            and validation_confidence >= self.config.pass_confidence_threshold
            and false_positive_risk <= self.config.pass_max_false_positive_risk
        ):
            validation_status = ValidationStatus.PASS
        elif (
            validation_score >= self.config.watch_validation_score_threshold
            and false_positive_risk <= self.config.watch_max_false_positive_risk
        ):
            if warnings or missing_evidence:
                validation_status = ValidationStatus.PASS_WITH_WARNINGS
            else:
                validation_status = ValidationStatus.WATCH
        else:
            validation_status = ValidationStatus.WATCH

        created_at = datetime.now(timezone.utc).isoformat()

        return ClusterValidationAnalysis(
            run_id=run_id,
            cluster_id=cid,
            niche=profitability_analysis.niche,
            subniche=profitability_analysis.subniche,
            microniche=profitability_analysis.microniche,
            video_count=video_count,
            profitability_score=original_prof_score,
            profitability_classification=profitability_analysis.classification.value,
            profitability_confidence=profitability_analysis.confidence,
            validation_score=validation_score,
            validation_status=validation_status,
            validation_confidence=validation_confidence,
            false_positive_risk=false_positive_risk,
            evidence_stability=evidence_stability,
            cross_signal_consistency=cross_signal_consistency,
            sample_adequacy=sample_adequacy,
            channel_diversity_validation=channel_diversity_val,
            outlier_diversity_validation=outlier_diversity_val,
            temporal_validation=temporal_val,
            economic_validation=economic_val,
            production_validation=prod_val,
            depth_validation=depth_val,
            semantic_coherence_validation=semantic_val,
            expected_views_stability=expected_views_stability,
            fragility_score=fragility_score,
            top_video_view_share=top_video_view_share,
            top_video_outlier_share=top_video_outlier_share,
            score_without_top_video=score_without_top_video,
            demand_without_top_video=demand_without_top_video,
            dominant_channel_share=dominant_channel_share,
            top_3_channel_share=top_3_channel_share,
            channel_hhi=channel_hhi,
            score_without_dominant_channel=score_without_dominant_channel,
            stress_adjusted_score=stress_adjusted_score,
            stress_score_delta=stress_score_delta,
            critical_failures=critical_failures,
            warnings=warnings,
            positive_evidence=positive_evidence,
            contradictory_evidence=contradictory_evidence,
            missing_evidence=missing_evidence,
            source_profitability_run_id=source_profitability_run_id,
            source_cluster_run_id=source_cluster_run_id,
            source_revenue_run_id=source_revenue_run_id,
            source_market_run_id=source_market_run_id,
            source_production_run_id=source_production_run_id,
            dataset_hash=dataset_hash,
            assignments_hash=assignments_hash,
            methodology_version=self.methodology_version,
            created_at=created_at,
        )

    def validate_all(
        self,
        profitability_analyses: List[ClusterProfitabilityAnalysis],
        clusters_videos_map: Dict[int, List[Dict[str, Any]]],
        market_structures_map: Optional[Dict[int, ClusterMarketStructure]] = None,
        production_risks_map: Optional[Dict[int, ClusterProductionRisk]] = None,
        outliers_map: Optional[Dict[int, List[VideoOutlierResult]]] = None,
        source_profitability_run_id: str = "",
        source_cluster_run_id: str = "",
        source_revenue_run_id: str = "",
        source_market_run_id: str = "",
        source_production_run_id: str = "",
        dataset_hash: str = "",
        assignments_hash: str = "",
    ) -> Sprint10AnalysisResult:
        run_id = f"sprint10_val_{uuid.uuid4().hex[:12]}"
        analyzed_at = datetime.now(timezone.utc).isoformat()

        ms_map = market_structures_map or {}
        pr_map = production_risks_map or {}
        out_map = outliers_map or {}

        validated_clusters: List[ClusterValidationAnalysis] = []

        for prof in profitability_analyses:
            cid = prof.cluster_id
            vids = clusters_videos_map.get(cid, [])
            v_analysis = self.validate_cluster(
                run_id=run_id,
                profitability_analysis=prof,
                cluster_videos=vids,
                market_structure=ms_map.get(cid),
                production_risk=pr_map.get(cid),
                outlier_results=out_map.get(cid),
                source_profitability_run_id=source_profitability_run_id,
                source_cluster_run_id=source_cluster_run_id,
                source_revenue_run_id=source_revenue_run_id,
                source_market_run_id=source_market_run_id,
                source_production_run_id=source_production_run_id,
                dataset_hash=dataset_hash,
                assignments_hash=assignments_hash,
            )
            validated_clusters.append(v_analysis)

        # Order candidates by validation strength: validation_score descending, then false_positive_risk ascending
        sorted_by_validation = sorted(
            validated_clusters,
            key=lambda c: (c.validation_score, -c.false_positive_risk),
            reverse=True,
        )
        validated_candidate_ids = [c.cluster_id for c in sorted_by_validation if c.validation_status in (ValidationStatus.PASS, ValidationStatus.PASS_WITH_WARNINGS, ValidationStatus.WATCH)]

        # Calculate quality metrics
        total = len(validated_clusters)
        if total > 0:
            low_sample = sum(1 for c in validated_clusters if c.sample_adequacy < 50.0) / total
            high_conc = sum(1 for c in validated_clusters if c.dominant_channel_share >= 0.5) / total
            one_vid_dep = sum(1 for c in validated_clusters if c.top_video_view_share >= 0.5) / total
            temp_miss = sum(1 for c in validated_clusters if c.temporal_validation <= 50.0) / total
            econ_weak = sum(1 for c in validated_clusters if "NO_MONETARY_BENCHMARK" in c.warnings) / total
            depth_unval = sum(1 for c in validated_clusters if c.depth_validation == 0.0) / total
            high_frag = sum(1 for c in validated_clusters if c.fragility_score >= 50.0) / total
            high_fp = sum(1 for c in validated_clusters if c.false_positive_risk >= 50.0) / total
            low_conf = sum(1 for c in validated_clusters if c.validation_confidence < 50.0) / total
        else:
            low_sample = high_conc = one_vid_dep = temp_miss = econ_weak = depth_unval = high_frag = high_fp = low_conf = 0.0

        quality = Sprint10QualityMetrics(
            low_sample_rate=low_sample,
            high_concentration_rate=high_conc,
            one_video_dependency_rate=one_vid_dep,
            temporal_evidence_missing_rate=temp_miss,
            economic_evidence_weak_rate=econ_weak,
            depth_unvalidated_rate=depth_unval,
            high_fragility_rate=high_frag,
            high_false_positive_risk_rate=high_fp,
            low_validation_confidence_rate=low_conf,
        )

        return Sprint10AnalysisResult(
            run_id=run_id,
            source_profitability_run_id=source_profitability_run_id,
            source_cluster_run_id=source_cluster_run_id,
            source_revenue_run_id=source_revenue_run_id,
            source_market_run_id=source_market_run_id,
            source_production_run_id=source_production_run_id,
            dataset_hash=dataset_hash,
            assignments_hash=assignments_hash,
            methodology_version=self.methodology_version,
            analyzed_at=analyzed_at,
            clusters=validated_clusters,
            quality=quality,
            validated_candidates=validated_candidate_ids,
        )
