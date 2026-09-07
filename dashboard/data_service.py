"""
Dashboard Data Service Layer for PRYTB Sprint 11.

Provides normalized view models, caching, hash verification, and read-only data joins
across Sprint 5-10 analytical outputs and YouTube entities.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.database.repositories import YouTubeRepository
from app.models.market_structure import (
    ClusterMarketStructure,
    EvergreenClass,
    EntryAccessibility,
    ContentDepthBand,
    MarketStructureClass,
)
from app.models.production_risk import (
    ClusterProductionRisk,
    RiskLevel,
    ProductionComplexity,
    FacelessFeasibility,
    AIAssistancePotential,
    ExpertiseRequirement,
    RepeatabilityBand,
)
from app.models.profitability import (
    ClusterProfitabilityAnalysis,
    ProfitabilityClassification,
    ExpectedViewsRange,
    RPMRange,
)
from app.models.validation import (
    ClusterValidationAnalysis,
    ValidationStatus,
)
from app.models.outliers import VideoOutlierResult
from app.utils.logger import logger
from scripts.validate_opportunities import run_validation

CANONICAL_VIDEOS = 83
CANONICAL_CLUSTERS = 10
CANONICAL_DATASET_HASH = "4d81c80e8da54b371c7eb969957ea347fc632d82abd737719141c866f4bfe9ad"
CANONICAL_ASSIGNMENTS_HASH = "6c0e7bb6aeec75985664becb05f7c61cbfec874c15a6ec7395d60c2996436288"


class ProvenanceInfo(BaseModel):
    dataset_hash: str
    assignments_hash: str
    videos_count: int
    clusters_count: int
    profitability_run_id: str
    validation_run_id: str
    market_run_id: str
    production_run_id: str
    revenue_run_id: str
    cluster_run_id: str
    is_compatible: bool = True
    error_message: Optional[str] = None


class OpportunityCandidateViewModel(BaseModel):
    cluster_id: int
    niche: str
    subniche: str
    microniche: str
    video_count: int
    
    # Validation
    validation_score: float
    validation_status: ValidationStatus
    validation_confidence: float
    fragility_score: float
    false_positive_risk: float
    
    # Profitability
    profitability_score: float
    profitability_classification: ProfitabilityClassification
    profitability_confidence: float
    coverage: float
    risk_penalty: float
    
    # Expected Views
    expected_views_low: float
    expected_views_base: float
    expected_views_high: float
    
    # RPM / Revenue / Cost / Profit status
    rpm_available: bool = False
    revenue_available: bool = False
    cost_available: bool = False
    profit_available: bool = False
    
    # Market & Competition (Sprint 7)
    competition_score: float
    accessibility: EntryAccessibility
    dominant_channel_share: float
    top_3_channel_share: float
    channel_hhi: float
    unique_channels: int
    small_channel_success_rate: float
    outlier_diversity: float
    evergreen_score: float
    evergreen_class: EvergreenClass
    trend_score: float
    content_depth_score: float
    content_depth_band: ContentDepthBand
    market_structure_class: MarketStructureClass
    
    # Production (Sprint 8)
    production_complexity: ProductionComplexity
    production_feasibility: float
    production_cost_index: float
    faceless_feasibility: FacelessFeasibility
    ai_assistance: AIAssistancePotential
    expertise_requirement: ExpertiseRequirement
    repeatability: RepeatabilityBand
    copyright_risk: RiskLevel
    platform_risk: RiskLevel
    accuracy_risk: RiskLevel
    update_burden: RiskLevel
    source_dependency: RiskLevel
    overall_production_risk: RiskLevel
    production_attractiveness: float
    production_confidence: float
    
    # Economic / Geography (Sprint 6)
    dominant_language: str
    market_tier: str
    audience_economic_value: float
    economic_confidence: float
    benchmark_coverage: float
    long_form_count: int
    short_count: int
    
    # Evidence lists
    positive_evidence: List[str] = Field(default_factory=list)
    negative_evidence: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    critical_failures: List[str] = Field(default_factory=list)
    
    # Sensitivity
    original_profitability_score: float
    score_without_top_video: float
    score_without_dominant_channel: float
    stress_adjusted_score: float
    sample_adequacy: float
    cross_signal_consistency: float
    expected_views_stability: float


class VideoViewModel(BaseModel):
    video_id: str
    title: str
    channel_id: str
    channel_title: str
    views: int
    subscribers: Optional[int] = None
    published_at: Optional[str] = None
    video_age_days: Optional[float] = None
    outlier_ratio: Optional[float] = None
    age_normalized_outlier_ratio: Optional[float] = None
    velocity: Optional[float] = None
    duration: Optional[str] = None
    content_type: str = "long_form"
    cluster_id: int
    niche: str = ""
    canonical_url: Optional[str] = None


class ChannelViewModel(BaseModel):
    channel_id: str
    channel_title: str
    subscribers: Optional[int] = None
    video_count_in_dataset: int
    outlier_count: int
    clusters_represented: List[int]
    median_views: float
    is_small_channel: bool = False


class DashboardDataset(BaseModel):
    provenance: ProvenanceInfo
    candidates: List[OpportunityCandidateViewModel]
    videos: List[VideoViewModel]
    outliers: List[VideoOutlierResult]
    channels: List[ChannelViewModel]
    
    # Summary counters
    total_videos: int = 83
    total_channels: int = 0
    total_clusters: int = 10
    total_outliers: int = 0
    status_counts: Dict[str, int] = Field(default_factory=dict)
    profitability_counts: Dict[str, int] = Field(default_factory=dict)


class DashboardDataService:
    """Service layer for fetching, joined, and validating dashboard data."""

    def __init__(self, repository: Optional[YouTubeRepository] = None):
        self.repository = repository or YouTubeRepository()

    def get_dashboard_data(self) -> DashboardDataset:
        val_output = run_validation(repository=self.repository, persist=False)
        val_result = val_output["result"]
        prof_result = val_output["sprint9_result"]
        sprint5_clusters = val_output.get("sprint5_clusters")
        sprint6_result = val_output.get("sprint6_result")
        sprint7_result = val_output.get("sprint7_result")
        sprint8_result = val_output.get("sprint8_result")
        outliers_raw = val_output.get("outlier_results", [])
        ordered_videos = val_output.get("ordered_videos", [])
        enriched_channels = val_output.get("enriched_channels", [])

        # Validate Provenance
        ds_hash = val_result.dataset_hash
        as_hash = val_result.assignments_hash
        is_compat = True
        err_msg = None

        if ds_hash != CANONICAL_DATASET_HASH or as_hash != CANONICAL_ASSIGNMENTS_HASH:
            is_compat = False
            err_msg = f"Canonical hash mismatch: dataset_hash={ds_hash}, assignments_hash={as_hash}"
        elif val_result.source_profitability_run_id != prof_result.run_id:
            is_compat = False
            err_msg = f"Run ID mismatch between validation ({val_result.source_profitability_run_id}) and profitability ({prof_result.run_id})"

        provenance = ProvenanceInfo(
            dataset_hash=ds_hash,
            assignments_hash=as_hash,
            videos_count=len(ordered_videos),
            clusters_count=len(val_result.clusters),
            profitability_run_id=prof_result.run_id,
            validation_run_id=val_result.run_id,
            market_run_id=val_result.source_market_run_id,
            production_run_id=val_result.source_production_run_id,
            revenue_run_id=val_result.source_revenue_run_id,
            cluster_run_id=val_result.source_cluster_run_id,
            is_compatible=is_compat,
            error_message=err_msg,
        )

        # Build Lookups
        prof_by_cluster = {c.cluster_id: c for c in prof_result.clusters}
        market_by_cluster = {c.cluster_id: c for c in sprint7_result.clusters} if sprint7_result else {}
        prod_by_cluster = {c.cluster_id: c for c in sprint8_result.clusters} if sprint8_result else {}
        rev_by_cluster = {c.cluster_id: c for c in sprint6_result.clusters} if sprint6_result else {}
        outlier_by_video = {o.video_id: o for o in outliers_raw}
        
        channel_info_map = {c.get("channel_id"): c for c in enriched_channels if isinstance(c, dict)}
        
        # Build Video View Models
        video_vms: List[VideoViewModel] = []
        cluster_by_video: Dict[str, int] = {}
        niche_by_video: Dict[str, str] = {}

        if sprint5_clusters:
            for c in sprint5_clusters:
                cid = getattr(c, "cluster_id", None) if not isinstance(c, dict) else c.get("cluster_id")
                v_ids = getattr(c, "video_ids", []) if not isinstance(c, dict) else c.get("video_ids", [])
                subn = getattr(c, "subniche", "") if not isinstance(c, dict) else c.get("subniche", "")
                for vid in v_ids:
                    cluster_by_video[vid] = cid
                    niche_by_video[vid] = subn

        for v in ordered_videos:
            vid = v.get("video_id", "")
            cid = cluster_by_video.get(vid, 0)
            niche = niche_by_video.get(vid, "")
            out = outlier_by_video.get(vid)
            
            ch_id = v.get("channel_id", "")
            ch_info = channel_info_map.get(ch_id, {})
            subs = v.get("subscriber_count") or ch_info.get("subscriber_count") or (out.subscriber_count if out else None)

            # URL
            canon_url = f"https://www.youtube.com/watch?v={vid}" if vid else None

            v_model = VideoViewModel(
                video_id=vid,
                title=v.get("title") or v.get("video_title") or vid,
                channel_id=ch_id,
                channel_title=v.get("channel_title") or ch_info.get("channel_title") or ch_id,
                views=int(v.get("view_count") or 0),
                subscribers=int(subs) if subs is not None else None,
                published_at=v.get("published_at"),
                video_age_days=float(v.get("video_age_days")) if v.get("video_age_days") is not None else None,
                outlier_ratio=out.outlier_ratio if out else None,
                age_normalized_outlier_ratio=out.age_normalized_outlier_ratio if out else None,
                velocity=out.latest_velocity if out else None,
                duration=v.get("duration"),
                content_type="short" if v.get("is_short") else "long_form",
                cluster_id=cid,
                niche=niche,
                canonical_url=canon_url,
            )
            video_vms.append(v_model)

        # Build Channel View Models
        channel_video_counts: Dict[str, int] = {}
        channel_outlier_counts: Dict[str, int] = {}
        channel_clusters: Dict[str, set] = {}
        channel_views_list: Dict[str, List[int]] = {}
        channel_titles: Dict[str, str] = {}
        channel_subs: Dict[str, Optional[int]] = {}

        for vm in video_vms:
            ch_id = vm.channel_id
            channel_video_counts[ch_id] = channel_video_counts.get(ch_id, 0) + 1
            if ch_id not in channel_clusters:
                channel_clusters[ch_id] = set()
            channel_clusters[ch_id].add(vm.cluster_id)
            
            if ch_id not in channel_views_list:
                channel_views_list[ch_id] = []
            channel_views_list[ch_id].append(vm.views)

            channel_titles[ch_id] = vm.channel_title
            if vm.subscribers is not None:
                channel_subs[ch_id] = vm.subscribers

            out = outlier_by_video.get(vm.video_id)
            if out and (out.is_strong_outlier or out.is_major_outlier or out.is_extreme_outlier):
                channel_outlier_counts[ch_id] = channel_outlier_counts.get(ch_id, 0) + 1

        channel_vms: List[ChannelViewModel] = []
        for ch_id, count in channel_video_counts.items():
            views_list = sorted(channel_views_list.get(ch_id, [0]))
            med_v = float(views_list[len(views_list) // 2]) if views_list else 0.0
            subs = channel_subs.get(ch_id)
            is_small = (subs is not None and subs <= 50000)

            channel_vms.append(
                ChannelViewModel(
                    channel_id=ch_id,
                    channel_title=channel_titles.get(ch_id, ch_id),
                    subscribers=subs,
                    video_count_in_dataset=count,
                    outlier_count=channel_outlier_counts.get(ch_id, 0),
                    clusters_represented=sorted(list(channel_clusters.get(ch_id, set()))),
                    median_views=med_v,
                    is_small_channel=is_small,
                )
            )

        # Build Opportunity Candidates View Models
        candidate_vms: List[OpportunityCandidateViewModel] = []
        status_counts: Dict[str, int] = {}
        prof_counts: Dict[str, int] = {}

        for val_c in val_result.clusters:
            cid = val_c.cluster_id
            prof_c = prof_by_cluster.get(cid)
            market_c = market_by_cluster.get(cid)
            prod_c = prod_by_cluster.get(cid)
            rev_c = rev_by_cluster.get(cid)

            # Status counters
            st_val = val_c.validation_status.value
            status_counts[st_val] = status_counts.get(st_val, 0) + 1

            p_cls = prof_c.classification.value if prof_c else val_c.profitability_classification
            prof_counts[p_cls] = prof_counts.get(p_cls, 0) + 1

            # Top video share & HHI from market structure or fallback
            top_3_share = 0.0
            if market_c and hasattr(market_c, "top_3_channel_share"):
                top_3_share = market_c.top_3_channel_share
            elif market_c:
                top_3_share = market_c.dominant_channel_share

            # Create ViewModel
            cand = OpportunityCandidateViewModel(
                cluster_id=cid,
                niche=val_c.niche or (prof_c.niche if prof_c else ""),
                subniche=val_c.subniche or (prof_c.subniche if prof_c else ""),
                microniche=val_c.microniche or (prof_c.microniche if prof_c else ""),
                video_count=val_c.video_count,
                
                # Validation
                validation_score=val_c.validation_score,
                validation_status=val_c.validation_status,
                validation_confidence=val_c.validation_confidence,
                fragility_score=val_c.fragility_score,
                false_positive_risk=val_c.false_positive_risk,
                
                # Profitability
                profitability_score=val_c.profitability_score if prof_c is None else prof_c.profitability_score,
                profitability_classification=prof_c.classification if prof_c else ProfitabilityClassification(val_c.profitability_classification),
                profitability_confidence=val_c.profitability_confidence if prof_c is None else prof_c.confidence,
                coverage=prof_c.component_coverage if prof_c else 0.0,
                risk_penalty=prof_c.risk_penalty if prof_c else 0.0,
                
                # Expected Views
                expected_views_low=prof_c.expected_views_range.low if prof_c else 0.0,
                expected_views_base=prof_c.expected_views_range.base if prof_c else 0.0,
                expected_views_high=prof_c.expected_views_range.high if prof_c else 0.0,
                
                # RPM / Revenue / Cost / Profit
                rpm_available=prof_c.rpm_range.available if prof_c else False,
                revenue_available=prof_c.revenue_scenarios.available if prof_c else False,
                cost_available=prof_c.production_cost.available if prof_c else False,
                profit_available=prof_c.profit_scenarios.available if prof_c else False,
                
                # Market & Competition
                competition_score=market_c.competition_score if market_c else 0.0,
                accessibility=market_c.accessibility if market_c else EntryAccessibility.UNKNOWN,
                dominant_channel_share=market_c.dominant_channel_share if market_c else val_c.dominant_channel_share * 100.0,
                top_3_channel_share=top_3_share,
                channel_hhi=market_c.channel_hhi if market_c else 0.0,
                unique_channels=market_c.channel_count if market_c else 0,
                small_channel_success_rate=market_c.small_channel_success_rate if (market_c and market_c.small_channel_success_rate is not None) else 0.0,
                outlier_diversity=market_c.average_outlier_rank_score if market_c else 0.0,
                evergreen_score=market_c.evergreen_score if market_c else 0.0,
                evergreen_class=market_c.evergreen_class if market_c else EvergreenClass.UNKNOWN,
                trend_score=market_c.trend_score if (market_c and market_c.trend_score is not None) else 0.0,
                content_depth_score=market_c.content_depth_score if market_c else 0.0,
                content_depth_band=market_c.content_depth_band if market_c else ContentDepthBand.UNDETERMINED,
                market_structure_class=market_c.market_structure_class if market_c else MarketStructureClass.UNCERTAIN,
                
                # Production
                production_complexity=prod_c.production_complexity if prod_c else ProductionComplexity.UNKNOWN,
                production_feasibility=100.0 - (prod_c.production_cost_score if prod_c else 0.0),
                production_cost_index=prod_c.production_cost_score if prod_c else 0.0,
                faceless_feasibility=prod_c.faceless_feasibility if prod_c else FacelessFeasibility.UNKNOWN,
                ai_assistance=prod_c.ai_assistance_potential if prod_c else AIAssistancePotential.UNKNOWN,
                expertise_requirement=prod_c.expertise_requirement if prod_c else ExpertiseRequirement.UNKNOWN,
                repeatability=prod_c.repeatability_band if prod_c else RepeatabilityBand.UNKNOWN,
                copyright_risk=prod_c.copyright_risk_level if prod_c else RiskLevel.UNKNOWN,
                platform_risk=prod_c.platform_policy_risk_level if prod_c else RiskLevel.UNKNOWN,
                accuracy_risk=prod_c.accuracy_risk_level if prod_c else RiskLevel.UNKNOWN,
                update_burden=prod_c.update_burden_level if prod_c else RiskLevel.UNKNOWN,
                source_dependency=prod_c.source_dependency_level if prod_c else RiskLevel.UNKNOWN,
                overall_production_risk=prod_c.risk_level if prod_c else RiskLevel.UNKNOWN,
                production_attractiveness=prod_c.production_attractiveness_score if (prod_c and prod_c.production_attractiveness_score is not None) else 0.0,
                production_confidence=prod_c.confidence if prod_c else 0.0,
                
                # Economic / Geography
                dominant_language=rev_c.dominant_language.value if (rev_c and hasattr(rev_c.dominant_language, "value")) else (str(rev_c.dominant_language) if rev_c else "Unknown"),
                market_tier=next(iter(rev_c.market_tier_distribution.keys()), "UNKNOWN") if (rev_c and rev_c.market_tier_distribution) else "UNKNOWN",
                audience_economic_value=rev_c.audience_economic_value if rev_c else 0.0,
                economic_confidence=rev_c.revenue_confidence if rev_c else 0.0,
                benchmark_coverage=rev_c.benchmark_coverage if rev_c else 0.0,
                long_form_count=rev_c.long_form_count if rev_c else 0,
                short_count=rev_c.short_count if rev_c else 0,
                
                # Evidence lists
                positive_evidence=val_c.positive_evidence,
                negative_evidence=val_c.contradictory_evidence,
                missing_evidence=val_c.missing_evidence,
                warnings=val_c.warnings,
                critical_failures=val_c.critical_failures,
                
                # Sensitivity
                original_profitability_score=val_c.profitability_score,
                score_without_top_video=val_c.score_without_top_video,
                score_without_dominant_channel=val_c.score_without_dominant_channel,
                stress_adjusted_score=val_c.stress_adjusted_score,
                sample_adequacy=val_c.sample_adequacy,
                cross_signal_consistency=val_c.cross_signal_consistency,
                expected_views_stability=val_c.expected_views_stability,
            )
            candidate_vms.append(cand)

        prod_video_ids = set(v.video_id for v in video_vms)
        prod_outliers = [o for o in outliers_raw if o.video_id in prod_video_ids]
        actual_outliers = [o for o in prod_outliers if o.is_actual_outlier()]

        return DashboardDataset(
            provenance=provenance,
            candidates=candidate_vms,
            videos=video_vms,
            outliers=prod_outliers,
            channels=channel_vms,
            total_videos=len(video_vms),
            total_channels=len(channel_vms),
            total_clusters=len(candidate_vms),
            total_outliers=len(actual_outliers),
            status_counts=status_counts,
            profitability_counts=prof_counts,
        )
