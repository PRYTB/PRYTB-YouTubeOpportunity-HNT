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
        return self


production_risk_config = ProductionRiskConfig()
