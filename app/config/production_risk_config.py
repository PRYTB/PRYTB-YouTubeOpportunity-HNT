"""Editable configuration for Sprint 8 production feasibility and risk analysis."""
from pydantic import BaseModel, Field, model_validator


class ProductionRiskConfig(BaseModel):
    minimum_cluster_sample: int = Field(default=5, ge=1)
    default_output_minutes: float = Field(default=8.0, gt=0.0)
    minimum_hours_low: float = Field(default=4.0, ge=0.0)
    minimum_hours_high: float = Field(default=8.0, ge=0.0)
    hours_per_output_minute_low: float = Field(default=0.45, ge=0.0)
    hours_per_output_minute_high: float = Field(default=0.9, ge=0.0)

    cost_weight_research: float = Field(default=0.35, ge=0.0)
    cost_weight_footage: float = Field(default=0.30, ge=0.0)
    cost_weight_editing: float = Field(default=0.35, ge=0.0)
    risk_weight_copyright: float = Field(default=0.45, ge=0.0)
    risk_weight_reused_content: float = Field(default=0.30, ge=0.0)
    risk_weight_regulatory_sensitive: float = Field(default=0.25, ge=0.0)

    medium_complexity_min: float = Field(default=40.0, ge=0.0, le=100.0)
    high_complexity_min: float = Field(default=70.0, ge=0.0, le=100.0)
    medium_risk_min: float = Field(default=35.0, ge=0.0, le=100.0)
    high_risk_min: float = Field(default=65.0, ge=0.0, le=100.0)

    # New Sprint 8 component configurations
    faceless_confidence_min: float = Field(default=0.5, ge=0.0, le=1.0)
    ai_assistance_confidence_min: float = Field(default=0.5, ge=0.0, le=1.0)
    expertise_confidence_min: float = Field(default=0.5, ge=0.0, le=1.0)

    platform_risk_weight_reused: float = Field(default=0.30, ge=0.0)
    platform_risk_weight_misleading: float = Field(default=0.25, ge=0.0)
    platform_risk_weight_sensitive: float = Field(default=0.25, ge=0.0)
    platform_risk_weight_spam: float = Field(default=0.20, ge=0.0)

    accuracy_risk_weight_technical: float = Field(default=0.30, ge=0.0)
    accuracy_risk_weight_statistics: float = Field(default=0.25, ge=0.0)
    accuracy_risk_weight_predictions: float = Field(default=0.25, ge=0.0)
    accuracy_risk_weight_rapid_change: float = Field(default=0.20, ge=0.0)

    update_burden_weight_date: float = Field(default=0.25, ge=0.0)
    update_burden_weight_news: float = Field(default=0.20, ge=0.0)
    update_burden_weight_product: float = Field(default=0.25, ge=0.0)
    update_burden_weight_software: float = Field(default=0.15, ge=0.0)
    update_burden_weight_predictions: float = Field(default=0.15, ge=0.0)

    source_dependency_weight_third_party: float = Field(default=0.25, ge=0.0)
    source_dependency_weight_news: float = Field(default=0.20, ge=0.0)
    source_dependency_weight_interviews: float = Field(default=0.20, ge=0.0)
    source_dependency_weight_vendor: float = Field(default=0.15, ge=0.0)
    source_dependency_weight_external: float = Field(default=0.20, ge=0.0)

    repeatability_weight_structure: float = Field(default=0.25, ge=0.0)
    repeatability_weight_screen: float = Field(default=0.20, ge=0.0)
    repeatability_weight_narration: float = Field(default=0.20, ge=0.0)
    repeatability_weight_template: float = Field(default=0.20, ge=0.0)
    repeatability_weight_research: float = Field(default=0.15, ge=0.0)

    attractiveness_min_coverage: float = Field(default=60.0, ge=0.0, le=100.0)
    attractiveness_weight_feasibility: float = Field(default=0.25, ge=0.0)
    attractiveness_weight_cost: float = Field(default=0.20, ge=0.0)
    attractiveness_weight_faceless: float = Field(default=0.15, ge=0.0)
    attractiveness_weight_ai: float = Field(default=0.10, ge=0.0)
    attractiveness_weight_repeatability: float = Field(default=0.15, ge=0.0)
    attractiveness_weight_risk: float = Field(default=0.15, ge=0.0)

    overall_risk_weight_copyright: float = Field(default=0.20, ge=0.0)
    overall_risk_weight_platform: float = Field(default=0.20, ge=0.0)
    overall_risk_weight_accuracy: float = Field(default=0.20, ge=0.0)
    overall_risk_weight_update: float = Field(default=0.15, ge=0.0)
    overall_risk_weight_source: float = Field(default=0.15, ge=0.0)
    overall_risk_weight_expertise: float = Field(default=0.10, ge=0.0)

    overall_risk_min_coverage: float = Field(default=50.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.minimum_hours_low > self.minimum_hours_high:
            raise ValueError("Minimum production-hour bounds must be ordered.")
        if self.medium_complexity_min > self.high_complexity_min:
            raise ValueError("Production-complexity thresholds must be ordered.")
        if self.medium_risk_min > self.high_risk_min:
            raise ValueError("Risk thresholds must be ordered.")
        cost_sum = self.cost_weight_research + self.cost_weight_footage + self.cost_weight_editing
        risk_sum = (
            self.risk_weight_copyright
            + self.risk_weight_reused_content
            + self.risk_weight_regulatory_sensitive
        )
        if abs(cost_sum - 1.0) > 1e-9 or abs(risk_sum - 1.0) > 1e-9:
            raise ValueError("Sprint 8 score weights must sum to 1.0.")

        # Validate new component weights
        platform_sum = (
            self.platform_risk_weight_reused
            + self.platform_risk_weight_misleading
            + self.platform_risk_weight_sensitive
            + self.platform_risk_weight_spam
        )
        accuracy_sum = (
            self.accuracy_risk_weight_technical
            + self.accuracy_risk_weight_statistics
            + self.accuracy_risk_weight_predictions
            + self.accuracy_risk_weight_rapid_change
        )
        update_sum = (
            self.update_burden_weight_date
            + self.update_burden_weight_news
            + self.update_burden_weight_product
            + self.update_burden_weight_software
            + self.update_burden_weight_predictions
        )
        source_sum = (
            self.source_dependency_weight_third_party
            + self.source_dependency_weight_news
            + self.source_dependency_weight_interviews
            + self.source_dependency_weight_vendor
            + self.source_dependency_weight_external
        )
        repeatability_sum = (
            self.repeatability_weight_structure
            + self.repeatability_weight_screen
            + self.repeatability_weight_narration
            + self.repeatability_weight_template
            + self.repeatability_weight_research
        )
        attractiveness_sum = (
            self.attractiveness_weight_feasibility
            + self.attractiveness_weight_cost
            + self.attractiveness_weight_faceless
            + self.attractiveness_weight_ai
            + self.attractiveness_weight_repeatability
            + self.attractiveness_weight_risk
        )
        overall_sum = (
            self.overall_risk_weight_copyright
            + self.overall_risk_weight_platform
            + self.overall_risk_weight_accuracy
            + self.overall_risk_weight_update
            + self.overall_risk_weight_source
            + self.overall_risk_weight_expertise
        )

        if abs(platform_sum - 1.0) > 1e-9:
            raise ValueError("Platform risk weights must sum to 1.0.")
        if abs(accuracy_sum - 1.0) > 1e-9:
            raise ValueError("Accuracy risk weights must sum to 1.0.")
        if abs(update_sum - 1.0) > 1e-9:
            raise ValueError("Update burden weights must sum to 1.0.")
        if abs(source_sum - 1.0) > 1e-9:
            raise ValueError("Source dependency weights must sum to 1.0.")
        if abs(repeatability_sum - 1.0) > 1e-9:
            raise ValueError("Repeatability weights must sum to 1.0.")
        if abs(attractiveness_sum - 1.0) > 1e-9:
            raise ValueError("Attractiveness weights must sum to 1.0.")
        if abs(overall_sum - 1.0) > 1e-9:
            raise ValueError("Overall risk weights must sum to 1.0.")

        return self


production_risk_config = ProductionRiskConfig()