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
    copyright_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    reused_content_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    regulatory_sensitive_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    overall_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    risk_level: RiskLevel = RiskLevel.UNKNOWN
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


class Sprint8AnalysisResult(BaseModel):
    run_id: str
    source_market_structure_run_id: Optional[str] = None
    source_cluster_run_id: Optional[str] = None
    analyzed_at: str
    config: Dict[str, Any] = Field(default_factory=dict)
    clusters: List[ClusterProductionRisk] = Field(default_factory=list)
    quality: Sprint8QualityMetrics
