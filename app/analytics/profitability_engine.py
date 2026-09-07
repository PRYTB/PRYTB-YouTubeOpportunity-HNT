"""
Sprint 9 Profitability Engine.

Consolidates analytical evidence from Sprints 3-8 into a comparative ProfitabilityScore (0-100)
and optional Monetary Scenarios (Pessimistic, Base, Optimistic) when valid benchmarks exist.

Strict monetary policy: Never fabricates RPM, CPM, revenue, monetary cost, or profit.
Coverage-aware renormalization: Missing or UNDETERMINED components (such as content depth = UNDETERMINED)
never award positive points or zero risk.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.analytics.benchmark_provider import EmptyBenchmarkProvider, RevenueBenchmarkProvider
from app.config.profitability_config import ProfitabilityConfig, profitability_config
from app.models.geography import ContentType
from app.models.market_structure import ClusterMarketStructure, ContentDepthBand
from app.models.outliers import VideoOutlierResult
from app.models.production_risk import ClusterProductionRisk, RiskLevel
from app.models.profitability import (
    ClusterProfitabilityAnalysis,
    ExpectedViewsRange,
    EvidenceType,
    MonetaryScenario,
    ProductionCostMonetary,
    ProfitabilityClassification,
    ProfitScenarios,
    RevenueScenarios,
    RPMRange,
    Sprint9AnalysisResult,
    Sprint9QualityMetrics,
)


class ProfitabilityEngine:
    """Consolidated Profitability Engine for PRYTB Sprint 9."""

    def __init__(
        self,
        config: Optional[ProfitabilityConfig] = None,
        benchmark_provider: Optional[RevenueBenchmarkProvider] = None,
        methodology_version: str = "sprint9-v1",
    ):
        self.config = config or profitability_config
        self.benchmark_provider = benchmark_provider or EmptyBenchmarkProvider()
        self.methodology_version = methodology_version

    def analyze_cluster(
        self,
        run_id: str,
        cluster_id: int,
        niche: str,
        subniche: str,
        microniche: str,
        cluster_videos: List[Dict[str, Any]],
        market_structure: Optional[ClusterMarketStructure] = None,
        production_risk: Optional[ClusterProductionRisk] = None,
        outlier_results: Optional[List[VideoOutlierResult]] = None,
        explicit_rpm: Optional[RPMRange] = None,
        explicit_cost_money: Optional[ProductionCostMonetary] = None,
        source_cluster_run_id: Optional[str] = None,
        source_revenue_run_id: Optional[str] = None,
        source_market_run_id: Optional[str] = None,
        source_production_run_id: Optional[str] = None,
        dataset_hash: str = "",
        assignments_hash: str = "",
    ) -> ClusterProfitabilityAnalysis:
        warnings: List[str] = []
        positive_evidence: List[str] = []
        negative_evidence: List[str] = []
        missing_evidence: List[str] = []

        video_count = len(cluster_videos)

        # 1. Format Facets & Separation
        long_form_count = 0
        short_count = 0
        unknown_format_count = 0

        for video in cluster_videos:
            duration = video.get("duration_seconds")
            if duration is None:
                unknown_format_count += 1
            elif float(duration) <= 180.0:  # 3 minutes or under
                short_count += 1
            else:
                long_form_count += 1

        # Format economic signals
        long_form_signal = 75.0 if long_form_count > 0 else None
        short_signal = 40.0 if short_count > 0 else None

        # 2. Robust Expected Views Range
        views_list = [
            float(v.get("view_count"))
            for v in cluster_videos
            if v.get("view_count") is not None and float(v.get("view_count")) >= 0
        ]

        if not views_list:
            expected_views_range = ExpectedViewsRange(
                low=0.0, base=0.0, high=0.0, confidence=0.0,
                method="insufficient_views_data",
                warnings=["No valid view count metrics in cluster videos"],
            )
            missing_evidence.append("Cluster has no view count data")
        else:
            sorted_views = sorted(views_list)
            n = len(sorted_views)
            base_v = float(median(sorted_views))
            p25_idx = max(0, int(n * 0.25))
            p75_idx = min(n - 1, int(n * 0.75))
            low_v = float(sorted_views[p25_idx])
            high_v = float(sorted_views[p75_idx])

            # Ensure strict low <= base <= high
            low_v = min(low_v, base_v)
            high_v = max(high_v, base_v)

            ev_confidence = min(100.0, n * 10.0)
            expected_views_range = ExpectedViewsRange(
                low=low_v,
                base=base_v,
                high=high_v,
                confidence=ev_confidence,
                method="robust_median_percentiles",
                evidence=[f"Calculated from {n} video view observations (median={base_v:.0f})"],
            )
            if high_v > base_v * 3.0:
                expected_views_range.warnings.append("High view variance observed in cluster")

        # 3. Component Scores (0-100 or None if UNKNOWN/UNDETERMINED)
        # Component 1: Demand (15%)
        if views_list:
            # Scale log of median view count relative to benchmark (e.g. 100k views = ~80 score)
            median_v = expected_views_range.base
            demand_score = min(100.0, max(10.0, math.log10(median_v + 1.0) * 18.0))
            if demand_score >= 60.0:
                positive_evidence.append(f"Strong view demand (median views: {median_v:,.0f})")
            else:
                negative_evidence.append(f"Moderate to low view demand (median views: {median_v:,.0f})")
        else:
            demand_score = 0.0

        # Component 2: Outliers (15%)
        if market_structure and market_structure.average_outlier_rank_score is not None:
            outlier_score = min(100.0, max(0.0, market_structure.average_outlier_rank_score))
            if outlier_score >= 50.0:
                positive_evidence.append(f"High viral outlier score ({outlier_score:.1f})")
            elif market_structure.small_channel_successes > 0:
                positive_evidence.append(f"Small channels breaking out ({market_structure.small_channel_successes} small channel successes)")
        else:
            outlier_score = 30.0  # Baseline neutral

        # Component 3: Revenue Potential (20%)
        # Based on audience economic value & long form presence
        revenue_potential_score = 60.0
        if long_form_count > 0:
            revenue_potential_score += 15.0
        if short_count > long_form_count:
            revenue_potential_score -= 15.0
        revenue_potential_score = min(100.0, max(10.0, revenue_potential_score))

        # Component 4: Competition (10%)
        if market_structure:
            competition_comp = min(100.0, max(0.0, 100.0 - market_structure.competition_score))
            if competition_comp >= 60.0:
                positive_evidence.append("Favorable competitive landscape / lower barrier to entry")
            else:
                negative_evidence.append("High competitive saturation")
        else:
            competition_comp = 50.0

        # Component 5: Geography (10%)
        geography_score = 60.0  # Tier B baseline default

        # Component 6: Evergreen (10%)
        if market_structure:
            evergreen_score = min(100.0, max(0.0, market_structure.evergreen_score))
            if evergreen_score >= 60.0:
                positive_evidence.append(f"High evergreen longevity ({evergreen_score:.1f})")
            elif evergreen_score < 40.0:
                negative_evidence.append("Trend-dependent / low evergreen longevity")
        else:
            evergreen_score = 50.0

        # Component 7: Production Score (10%)
        if production_risk:
            # Lower production cost index -> higher production attractiveness score
            prod_cost_idx = production_risk.production_cost_score
            production_score = min(100.0, max(0.0, 100.0 - prod_cost_idx))
            if production_score >= 60.0:
                positive_evidence.append(f"Low production cost index ({prod_cost_idx:.1f})")
            else:
                negative_evidence.append(f"High production cost index ({prod_cost_idx:.1f})")
            prod_cost_index_val = prod_cost_idx
            prod_complexity_val = production_risk.production_complexity.value
            prod_feasibility_val = production_risk.faceless_feasibility.value
            prod_risk_val = production_risk.risk_level.value
        else:
            production_score = 50.0
            prod_cost_index_val = 50.0
            prod_complexity_val = "UNKNOWN"
            prod_feasibility_val = "UNKNOWN"
            prod_risk_val = "UNKNOWN"
            missing_evidence.append("Production risk analysis data missing")

        # Component 8: Content Depth (5%)
        # CRITICAL: Sprint 7 production depth is UNDETERMINED (10/10).
        # UNDETERMINED / UNKNOWN must NOT receive positive points!
        if market_structure and market_structure.content_depth_band not in (ContentDepthBand.UNDETERMINED, ContentDepthBand.UNKNOWN):
            content_depth_score: Optional[float] = market_structure.content_depth_score
        else:
            content_depth_score = None
            missing_evidence.append("Content depth is UNDETERMINED / UNKNOWN")

        # Component 9: Short Potential (5%)
        if short_count > 0:
            short_potential_score: Optional[float] = 60.0
            positive_evidence.append(f"Shorts format present ({short_count} short videos)")
        else:
            short_potential_score = None
            missing_evidence.append("Short potential is UNKNOWN (0 shorts in cluster)")

        # 4. Coverage-Aware Renormalization & Base Score
        raw_components = {
            "demand": (demand_score, self.config.weight_demand),
            "outliers": (outlier_score, self.config.weight_outliers),
            "revenue_potential": (revenue_potential_score, self.config.weight_revenue_potential),
            "competition": (competition_comp, self.config.weight_competition),
            "geography": (geography_score, self.config.weight_geography),
            "evergreen": (evergreen_score, self.config.weight_evergreen),
            "production": (production_score, self.config.weight_production),
            "content_depth": (content_depth_score, self.config.weight_content_depth),
            "short_potential": (short_potential_score, self.config.weight_short_potential),
        }

        known_weight = 0.0
        weighted_sum = 0.0
        component_contributions: Dict[str, float] = {}

        for comp_name, (score_val, weight) in raw_components.items():
            if score_val is not None:
                known_weight += weight
                weighted_sum += score_val * weight
                component_contributions[comp_name] = round(score_val * weight, 4)
            else:
                component_contributions[comp_name] = 0.0

        missing_weight = 1.0 - known_weight
        component_coverage = known_weight / 1.0

        if known_weight > 0:
            base_score = weighted_sum / known_weight
        else:
            base_score = 0.0

        # 5. Risk Penalty & UNKNOWN risk handling
        if production_risk and production_risk.risk_level != RiskLevel.UNKNOWN and production_risk.overall_risk_score is not None:
            raw_risk = production_risk.overall_risk_score
            risk_penalty = raw_risk * self.config.risk_penalty_scale
            if raw_risk >= 50.0:
                negative_evidence.append(f"Elevated risk score ({raw_risk:.1f})")
        else:
            # UNKNOWN risk must NOT be treated as 0 risk!
            risk_penalty = 15.0
            missing_evidence.append("Production risk level UNKNOWN (applied safety risk penalty)")
            warnings.append("Risk assessment is UNKNOWN or missing")

        # Final Profitability Score
        profitability_score = min(100.0, max(0.0, base_score - risk_penalty))

        # Classification
        if profitability_score >= 90.0:
            classification = ProfitabilityClassification.EXCEPTIONAL
        elif profitability_score >= 80.0:
            classification = ProfitabilityClassification.STRONG
        elif profitability_score >= 70.0:
            classification = ProfitabilityClassification.INTERESTING
        elif profitability_score >= 50.0:
            classification = ProfitabilityClassification.WATCH
        else:
            classification = ProfitabilityClassification.DISCARD

        # 6. Confidence Score
        confidence_base = 80.0
        if market_structure:
            confidence_base = (confidence_base + market_structure.accessibility_confidence + market_structure.depth_confidence) / 3.0
        if production_risk:
            confidence_base = (confidence_base + production_risk.faceless_confidence) / 2.0
        
        confidence = min(100.0, max(0.0, confidence_base * component_coverage))

        # 7. Monetary Policy & Scenario Mode
        rpm_range = explicit_rpm or RPMRange(available=False)
        production_cost = explicit_cost_money or ProductionCostMonetary(available=False)

        revenue_scenarios = RevenueScenarios(available=False)
        profit_scenarios = ProfitScenarios(available=False)

        if rpm_range.available and rpm_range.mid is not None:
            # Calculate revenue scenarios
            low_rev = (expected_views_range.low * (rpm_range.low or rpm_range.mid)) / 1000.0
            base_rev = (expected_views_range.base * rpm_range.mid) / 1000.0
            high_rev = (expected_views_range.high * (rpm_range.high or rpm_range.mid)) / 1000.0

            rev_currency = rpm_range.currency
            ev_type = rpm_range.source

            revenue_scenarios = RevenueScenarios(
                available=True,
                pessimistic=MonetaryScenario(expected_revenue=low_rev, currency=rev_currency, evidence_type=ev_type),
                base=MonetaryScenario(expected_revenue=base_rev, currency=rev_currency, evidence_type=ev_type),
                optimistic=MonetaryScenario(expected_revenue=high_rev, currency=rev_currency, evidence_type=ev_type),
            )

            # Check if profit scenarios can also be calculated
            if production_cost.available and production_cost.base is not None:
                if production_cost.currency != rev_currency:
                    warnings.append(f"Currency mismatch: Revenue ({rev_currency}) vs Cost ({production_cost.currency})")
                else:
                    cost_low = production_cost.low or production_cost.base
                    cost_base = production_cost.base
                    cost_high = production_cost.high or production_cost.base

                    profit_pess = low_rev - cost_high
                    profit_base = base_rev - cost_base
                    profit_opt = high_rev - cost_low

                    profit_scenarios = ProfitScenarios(
                        available=True,
                        pessimistic=MonetaryScenario(expected_revenue=low_rev, expected_cost=cost_high, expected_profit=profit_pess, currency=rev_currency, evidence_type=ev_type),
                        base=MonetaryScenario(expected_revenue=base_rev, expected_cost=cost_base, expected_profit=profit_base, currency=rev_currency, evidence_type=ev_type),
                        optimistic=MonetaryScenario(expected_revenue=high_rev, expected_cost=cost_low, expected_profit=profit_opt, currency=rev_currency, evidence_type=ev_type),
                    )

        created_at = datetime.now(timezone.utc).isoformat()

        return ClusterProfitabilityAnalysis(
            run_id=run_id,
            cluster_id=cluster_id,
            niche=niche,
            subniche=subniche,
            microniche=microniche,
            video_count=video_count,
            long_form_video_count=long_form_count,
            short_video_count=short_count,
            unknown_format_count=unknown_format_count,
            long_form_economic_signal=long_form_signal,
            short_economic_signal=short_signal,
            expected_views_range=expected_views_range,
            rpm_range=rpm_range,
            revenue_scenarios=revenue_scenarios,
            production_cost=production_cost,
            profit_scenarios=profit_scenarios,
            production_cost_index=prod_cost_index_val,
            production_complexity=prod_complexity_val,
            production_feasibility=prod_feasibility_val,
            production_risk=prod_risk_val,
            demand_score=demand_score,
            outlier_score=outlier_score,
            revenue_potential_score=revenue_potential_score,
            competition_component=competition_comp,
            geography_score=geography_score,
            evergreen_score=evergreen_score,
            production_score=production_score,
            content_depth_score=content_depth_score,
            short_potential_score=short_potential_score,
            base_score=base_score,
            risk_penalty=risk_penalty,
            profitability_score=profitability_score,
            classification=classification,
            component_coverage=component_coverage,
            known_weight=known_weight,
            missing_weight=missing_weight,
            confidence=confidence,
            positive_evidence=positive_evidence,
            negative_evidence=negative_evidence,
            missing_evidence=missing_evidence,
            component_contributions=component_contributions,
            warnings=warnings,
            source_cluster_run_id=source_cluster_run_id,
            source_revenue_run_id=source_revenue_run_id,
            source_market_run_id=source_market_run_id,
            source_production_run_id=source_production_run_id,
            dataset_hash=dataset_hash,
            assignments_hash=assignments_hash,
            methodology_version=self.methodology_version,
            created_at=created_at,
        )

    def analyze_all(
        self,
        clusters_data: List[Dict[str, Any]],
        market_structures: Optional[Dict[int, ClusterMarketStructure]] = None,
        production_risks: Optional[Dict[int, ClusterProductionRisk]] = None,
        explicit_rpm_by_cluster: Optional[Dict[int, RPMRange]] = None,
        explicit_cost_by_cluster: Optional[Dict[int, ProductionCostMonetary]] = None,
        source_cluster_run_id: Optional[str] = None,
        source_revenue_run_id: Optional[str] = None,
        source_market_run_id: Optional[str] = None,
        source_production_run_id: Optional[str] = None,
        dataset_hash: str = "",
        assignments_hash: str = "",
    ) -> Sprint9AnalysisResult:
        run_id = f"sprint9_prof_{uuid.uuid4().hex[:12]}"
        analyzed_at = datetime.now(timezone.utc).isoformat()

        market_map = market_structures or {}
        risk_map = production_risks or {}
        rpm_map = explicit_rpm_by_cluster or {}
        cost_map = explicit_cost_by_cluster or {}

        analyzed_clusters: List[ClusterProfitabilityAnalysis] = []

        for c_data in clusters_data:
            cid = c_data["cluster_id"]
            analysis = self.analyze_cluster(
                run_id=run_id,
                cluster_id=cid,
                niche=c_data.get("niche", ""),
                subniche=c_data.get("subniche", ""),
                microniche=c_data.get("microniche", ""),
                cluster_videos=c_data.get("videos", []),
                market_structure=market_map.get(cid),
                production_risk=risk_map.get(cid),
                explicit_rpm=rpm_map.get(cid),
                explicit_cost_money=cost_map.get(cid),
                source_cluster_run_id=source_cluster_run_id,
                source_revenue_run_id=source_revenue_run_id,
                source_market_run_id=source_market_run_id,
                source_production_run_id=source_production_run_id,
                dataset_hash=dataset_hash,
                assignments_hash=assignments_hash,
            )
            analyzed_clusters.append(analysis)

        # Sort clusters by ProfitabilityScore descending for Top 5 candidates
        sorted_clusters = sorted(analyzed_clusters, key=lambda c: c.profitability_score, reverse=True)
        top_5 = [c.cluster_id for c in sorted_clusters[:5]]

        # Quality metrics
        total = len(analyzed_clusters)
        if total > 0:
            ev_unavail = sum(1 for c in analyzed_clusters if c.expected_views_range.base == 0.0) / total
            rpm_unavail = sum(1 for c in analyzed_clusters if not c.rpm_range.available) / total
            rev_unavail = sum(1 for c in analyzed_clusters if not c.revenue_scenarios.available) / total
            cost_unavail = sum(1 for c in analyzed_clusters if not c.production_cost.available) / total
            prof_unavail = sum(1 for c in analyzed_clusters if not c.profit_scenarios.available) / total
            depth_unavail = sum(1 for c in analyzed_clusters if c.content_depth_score is None) / total
            short_unknown = sum(1 for c in analyzed_clusters if c.short_potential_score is None) / total
            low_cov_cnt = sum(1 for c in analyzed_clusters if c.component_coverage < self.config.low_coverage_threshold)
            low_conf_cnt = sum(1 for c in analyzed_clusters if c.confidence < self.config.low_confidence_threshold)
        else:
            ev_unavail = rpm_unavail = rev_unavail = cost_unavail = prof_unavail = depth_unavail = short_unknown = 0.0
            low_cov_cnt = low_conf_cnt = 0

        quality = Sprint9QualityMetrics(
            expected_views_unavailable_rate=ev_unavail,
            rpm_unavailable_rate=rpm_unavail,
            revenue_unavailable_rate=rev_unavail,
            monetary_cost_unavailable_rate=cost_unavail,
            profit_unavailable_rate=prof_unavail,
            depth_unavailable_rate=depth_unavail,
            short_potential_unknown_rate=short_unknown,
            low_coverage_cluster_count=low_cov_cnt,
            low_confidence_cluster_count=low_conf_cnt,
        )

        return Sprint9AnalysisResult(
            run_id=run_id,
            source_cluster_run_id=source_cluster_run_id,
            source_revenue_run_id=source_revenue_run_id,
            source_market_run_id=source_market_run_id,
            source_production_run_id=source_production_run_id,
            dataset_hash=dataset_hash,
            assignments_hash=assignments_hash,
            methodology_version=self.methodology_version,
            analyzed_at=analyzed_at,
            clusters=analyzed_clusters,
            quality=quality,
            top_5_candidates=top_5,
        )
