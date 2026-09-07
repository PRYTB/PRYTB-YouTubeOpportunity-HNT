"""
Sprint 10 Data Models: Adversarial Opportunity Validator.

Defines models for cluster validation analyses, validation status/scoring,
fragility, false positive risks, counterfactual perturbations, and quality metrics.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    WATCH = "WATCH"
    FAIL = "FAIL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ClusterValidationAnalysis(BaseModel):
    run_id: str
    cluster_id: int = Field(ge=0)
    niche: str = ""
    subniche: str = ""
    microniche: str = ""
    video_count: int = Field(default=0, ge=0)

    # Sprint 9 Profitability Baseline
    profitability_score: float = Field(default=0.0, ge=0.0, le=100.0)
    profitability_classification: str = "DISCARD"
    profitability_confidence: float = Field(default=0.0, ge=0.0, le=100.0)

    # Sprint 10 Validation Core
    validation_score: float = Field(default=0.0, ge=0.0, le=100.0)
    validation_status: ValidationStatus = ValidationStatus.INSUFFICIENT_EVIDENCE
    validation_confidence: float = Field(default=0.0, ge=0.0, le=100.0)

    # Risk & Stability Metrics (0-100)
    false_positive_risk: float = Field(default=0.0, ge=0.0, le=100.0)
    evidence_stability: float = Field(default=0.0, ge=0.0, le=100.0)
    cross_signal_consistency: float = Field(default=0.0, ge=0.0, le=100.0)
    sample_adequacy: float = Field(default=0.0, ge=0.0, le=100.0)
    channel_diversity_validation: float = Field(default=0.0, ge=0.0, le=100.0)
    outlier_diversity_validation: float = Field(default=0.0, ge=0.0, le=100.0)
    temporal_validation: float = Field(default=0.0, ge=0.0, le=100.0)
    economic_validation: float = Field(default=0.0, ge=0.0, le=100.0)
    production_validation: float = Field(default=0.0, ge=0.0, le=100.0)
    depth_validation: float = Field(default=0.0, ge=0.0, le=100.0)
    semantic_coherence_validation: float = Field(default=0.0, ge=0.0, le=100.0)
    expected_views_stability: float = Field(default=0.0, ge=0.0, le=100.0)
    fragility_score: float = Field(default=0.0, ge=0.0, le=100.0)

    # Sensitivity / Counterfactual Perturbations
    top_video_view_share: float = Field(default=0.0, ge=0.0, le=1.0)
    top_video_outlier_share: float = Field(default=0.0, ge=0.0, le=1.0)
    score_without_top_video: float = Field(default=0.0, ge=0.0, le=100.0)
    demand_without_top_video: float = Field(default=0.0, ge=0.0, le=100.0)
    dominant_channel_share: float = Field(default=0.0, ge=0.0, le=1.0)
    top_3_channel_share: float = Field(default=0.0, ge=0.0, le=1.0)
    channel_hhi: float = Field(default=0.0, ge=0.0, le=10000.0)
    score_without_dominant_channel: float = Field(default=0.0, ge=0.0, le=100.0)
    stress_adjusted_score: float = Field(default=0.0, ge=0.0, le=100.0)
    stress_score_delta: float = Field(default=0.0)

    # Evidence Lists
    critical_failures: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    positive_evidence: List[str] = Field(default_factory=list)
    contradictory_evidence: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)

    # Provenance
    source_profitability_run_id: str
    source_cluster_run_id: str
    source_revenue_run_id: str
    source_market_run_id: str
    source_production_run_id: str
    dataset_hash: str
    assignments_hash: str
    methodology_version: str = "sprint10-v1"
    created_at: str = ""


class Sprint10QualityMetrics(BaseModel):
    low_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    high_concentration_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    one_video_dependency_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    temporal_evidence_missing_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    economic_evidence_weak_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    depth_unvalidated_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    high_fragility_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    high_false_positive_risk_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    low_validation_confidence_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class Sprint10AnalysisResult(BaseModel):
    run_id: str
    source_profitability_run_id: str
    source_cluster_run_id: str
    source_revenue_run_id: str
    source_market_run_id: str
    source_production_run_id: str
    dataset_hash: str
    assignments_hash: str
    methodology_version: str = "sprint10-v1"
    analyzed_at: str
    clusters: List[ClusterValidationAnalysis] = Field(default_factory=list)
    quality: Sprint10QualityMetrics = Field(default_factory=Sprint10QualityMetrics)
    validated_candidates: List[int] = Field(default_factory=list)
