"""
Sprint 9 Data Models: Profitability Engine.

Defines models for comparative profitability scoring, monetary scenarios,
robust expected views ranges, RPM ranges, component contributions,
confidence, explainability, and full data provenance.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class EvidenceType(str, Enum):
    OBSERVED = "OBSERVED"
    EXTERNAL_BENCHMARK = "EXTERNAL_BENCHMARK"
    MANUAL_ASSUMPTION = "MANUAL_ASSUMPTION"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class ProfitabilityClassification(str, Enum):
    DISCARD = "DISCARD"        # 0 - 49.99
    WATCH = "WATCH"            # 50 - 69.99
    INTERESTING = "INTERESTING" # 70 - 79.99
    STRONG = "STRONG"          # 80 - 89.99
    EXCEPTIONAL = "EXCEPTIONAL" # 90 - 100


class ExpectedViewsRange(BaseModel):
    low: float = Field(ge=0.0)
    base: float = Field(ge=0.0)
    high: float = Field(ge=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    method: str = "robust_median_percentiles"
    evidence: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bounds(self) -> "ExpectedViewsRange":
        if not (self.low <= self.base <= self.high):
            raise ValueError(f"Invalid view bounds: low ({self.low}) <= base ({self.base}) <= high ({self.high}) required.")
        return self


class RPMRange(BaseModel):
    available: bool = False
    low: Optional[float] = Field(default=None, ge=0.0)
    mid: Optional[float] = Field(default=None, ge=0.0)
    high: Optional[float] = Field(default=None, ge=0.0)
    currency: str = "USD"
    market: Optional[str] = None
    content_type: Optional[str] = None
    source: EvidenceType = EvidenceType.UNKNOWN
    benchmark_type: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    warnings: List[str] = Field(default_factory=list)


class MonetaryScenario(BaseModel):
    expected_revenue: Optional[float] = Field(default=None, ge=0.0)
    expected_cost: Optional[float] = Field(default=None, ge=0.0)
    expected_profit: Optional[float] = Field(default=None)
    currency: str = "USD"
    evidence_type: EvidenceType = EvidenceType.UNKNOWN
    warnings: List[str] = Field(default_factory=list)


class RevenueScenarios(BaseModel):
    available: bool = False
    pessimistic: Optional[MonetaryScenario] = None
    base: Optional[MonetaryScenario] = None
    optimistic: Optional[MonetaryScenario] = None
    warnings: List[str] = Field(default_factory=list)


class ProductionCostMonetary(BaseModel):
    available: bool = False
    low: Optional[float] = Field(default=None, ge=0.0)
    base: Optional[float] = Field(default=None, ge=0.0)
    high: Optional[float] = Field(default=None, ge=0.0)
    currency: str = "USD"
    evidence_type: EvidenceType = EvidenceType.UNKNOWN
    warnings: List[str] = Field(default_factory=list)


class ProfitScenarios(BaseModel):
    available: bool = False
    pessimistic: Optional[MonetaryScenario] = None
    base: Optional[MonetaryScenario] = None
    optimistic: Optional[MonetaryScenario] = None
    warnings: List[str] = Field(default_factory=list)


class ClusterProfitabilityAnalysis(BaseModel):
    run_id: str
    cluster_id: int = Field(ge=0)
    niche: str = ""
    subniche: str = ""
    microniche: str = ""
    video_count: int = Field(default=0, ge=0)

    # Format facets
    long_form_video_count: int = Field(default=0, ge=0)
    short_video_count: int = Field(default=0, ge=0)
    unknown_format_count: int = Field(default=0, ge=0)
    long_form_economic_signal: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    short_economic_signal: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    # Expected views & monetary policy models
    expected_views_range: ExpectedViewsRange
    rpm_range: RPMRange = Field(default_factory=RPMRange)
    revenue_scenarios: RevenueScenarios = Field(default_factory=RevenueScenarios)
    production_cost: ProductionCostMonetary = Field(default_factory=ProductionCostMonetary)
    profit_scenarios: ProfitScenarios = Field(default_factory=ProfitScenarios)

    # Sprint 8 Production relative indicators
    production_cost_index: float = Field(default=0.0, ge=0.0, le=100.0)
    production_complexity: str = "UNKNOWN"
    production_feasibility: str = "UNKNOWN"
    production_risk: str = "UNKNOWN"

    # Component Scores (0-100 or None if missing/unknown)
    demand_score: float = Field(default=0.0, ge=0.0, le=100.0)
    outlier_score: float = Field(default=0.0, ge=0.0, le=100.0)
    revenue_potential_score: float = Field(default=0.0, ge=0.0, le=100.0)
    competition_component: float = Field(default=0.0, ge=0.0, le=100.0)
    geography_score: float = Field(default=0.0, ge=0.0, le=100.0)
    evergreen_score: float = Field(default=0.0, ge=0.0, le=100.0)
    production_score: float = Field(default=0.0, ge=0.0, le=100.0)
    content_depth_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    short_potential_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    # Composite profitability & risk
    base_score: float = Field(default=0.0, ge=0.0, le=100.0)
    risk_penalty: float = Field(default=0.0, ge=0.0, le=100.0)
    profitability_score: float = Field(default=0.0, ge=0.0, le=100.0)
    classification: ProfitabilityClassification = ProfitabilityClassification.DISCARD

    # Coverage & Confidence
    component_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    known_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)

    # Explainability
    positive_evidence: List[str] = Field(default_factory=list)
    negative_evidence: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    component_contributions: Dict[str, float] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)

    # Provenance
    source_cluster_run_id: Optional[str] = None
    source_revenue_run_id: Optional[str] = None
    source_market_run_id: Optional[str] = None
    source_production_run_id: Optional[str] = None
    dataset_hash: str
    assignments_hash: str
    methodology_version: str = "sprint9-v1"
    created_at: str = ""


class Sprint9QualityMetrics(BaseModel):
    expected_views_unavailable_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    rpm_unavailable_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    revenue_unavailable_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    monetary_cost_unavailable_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    profit_unavailable_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    depth_unavailable_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    short_potential_unknown_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    low_coverage_cluster_count: int = Field(default=0, ge=0)
    low_confidence_cluster_count: int = Field(default=0, ge=0)


class Sprint9AnalysisResult(BaseModel):
    run_id: str
    source_cluster_run_id: Optional[str] = None
    source_revenue_run_id: Optional[str] = None
    source_market_run_id: Optional[str] = None
    source_production_run_id: Optional[str] = None
    dataset_hash: str
    assignments_hash: str
    methodology_version: str = "sprint9-v1"
    analyzed_at: str
    clusters: List[ClusterProfitabilityAnalysis] = Field(default_factory=list)
    quality: Sprint9QualityMetrics = Field(default_factory=Sprint9QualityMetrics)
    top_5_candidates: List[int] = Field(default_factory=list)
