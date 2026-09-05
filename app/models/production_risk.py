"""Normalized models for Sprint 8 production feasibility and risk analysis."""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class ProductionComplexity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class FacelessFeasibility(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class AIAssistancePotential(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class ExpertiseRequirement(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    SPECIALIST = "SPECIALIST"
    UNKNOWN = "UNKNOWN"


class RepeatabilityBand(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class ClusterProductionRisk(BaseModel):
    cluster_id: int = Field(ge=0)
    niche: str = ""
    subniche: str = ""
    microniche: str = ""
    video_count: int = Field(default=0, ge=0)
    production_cost_score: float = Field(default=0.0, ge=0.0, le=100.0)
    estimated_hours_low: Optional[float] = Field(default=None, ge=0.0)
    estimated_hours_high: Optional[float] = Field(default=None, ge=0.0)
    research_complexity_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    footage_complexity_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    editing_complexity_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    production_complexity: ProductionComplexity = ProductionComplexity.UNKNOWN

    # New Sprint 8 components
    faceless_feasibility: FacelessFeasibility = FacelessFeasibility.UNKNOWN
    faceless_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    faceless_observed_evidence: List[str] = Field(default_factory=list)
    faceless_inferred_evidence: List[str] = Field(default_factory=list)
    faceless_warnings: List[str] = Field(default_factory=list)

    ai_assistance_potential: AIAssistancePotential = AIAssistancePotential.UNKNOWN
    ai_assistance_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    ai_assistance_observed_evidence: List[str] = Field(default_factory=list)
    ai_assistance_inferred_evidence: List[str] = Field(default_factory=list)
    ai_assistance_warnings: List[str] = Field(default_factory=list)

    expertise_requirement: ExpertiseRequirement = ExpertiseRequirement.UNKNOWN
    expertise_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    expertise_observed_evidence: List[str] = Field(default_factory=list)
    expertise_inferred_evidence: List[str] = Field(default_factory=list)
    expertise_warnings: List[str] = Field(default_factory=list)

    copyright_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    reused_content_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    regulatory_sensitive_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    platform_policy_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    accuracy_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    update_burden_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    source_dependency_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    copyright_risk_level: RiskLevel = RiskLevel.UNKNOWN
    platform_policy_risk_level: RiskLevel = RiskLevel.UNKNOWN
    accuracy_risk_level: RiskLevel = RiskLevel.UNKNOWN
    update_burden_level: RiskLevel = RiskLevel.UNKNOWN
    source_dependency_level: RiskLevel = RiskLevel.UNKNOWN

    overall_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    risk_level: RiskLevel = RiskLevel.UNKNOWN

    repeatability_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    repeatability_band: RepeatabilityBand = RepeatabilityBand.UNKNOWN
    repeatability_confidence: float = Field(default=0.0, ge=0.0, le=100.0)

    production_attractiveness_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    production_attractiveness_available: bool = False
    production_attractiveness_coverage: float = Field(default=0.0, ge=0.0, le=100.0)
    production_attractiveness_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    production_attractiveness_warnings: List[str] = Field(default_factory=list)

    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    observed_fields: List[str] = Field(default_factory=list)
    inferred_fields: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_hours(self):
        if (
            self.estimated_hours_low is not None
            and self.estimated_hours_high is not None
            and self.estimated_hours_low > self.estimated_hours_high
        ):
            raise ValueError("Production hour bounds must be ordered.")
        return self


class Sprint8QualityMetrics(BaseModel):
    total_videos: int = Field(default=0, ge=0)
    total_clusters: int = Field(default=0, ge=0)
    title_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    description_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    duration_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    clusters_without_risk_evidence: int = Field(default=0, ge=0)

    # New quality metrics for added components
    faceless_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    ai_assistance_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    expertise_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    platform_risk_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    accuracy_risk_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    update_burden_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    source_dependency_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    repeatability_unknown_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    attractiveness_unavailable_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    low_sample_cluster_count: int = Field(default=0, ge=0)


class Sprint8AnalysisResult(BaseModel):
    run_id: str
    source_market_structure_run_id: Optional[str] = None
    source_cluster_run_id: Optional[str] = None
    analyzed_at: str
    config: Dict[str, Any] = Field(default_factory=dict)
    clusters: List[ClusterProductionRisk] = Field(default_factory=list)
    quality: Sprint8QualityMetrics