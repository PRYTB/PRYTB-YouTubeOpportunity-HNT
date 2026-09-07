"""
Configurable Master Prompt weights and parameters for Sprint 9 Profitability Engine.
"""

from typing import Dict
from pydantic import BaseModel, Field, model_validator


class ProfitabilityConfig(BaseModel):
    # Component weights totaling 1.0 (100%)
    weight_demand: float = Field(default=0.15, ge=0.0, le=1.0)
    weight_outliers: float = Field(default=0.15, ge=0.0, le=1.0)
    weight_revenue_potential: float = Field(default=0.20, ge=0.0, le=1.0)
    weight_competition: float = Field(default=0.10, ge=0.0, le=1.0)
    weight_geography: float = Field(default=0.10, ge=0.0, le=1.0)
    weight_evergreen: float = Field(default=0.10, ge=0.0, le=1.0)
    weight_production: float = Field(default=0.10, ge=0.0, le=1.0)
    weight_content_depth: float = Field(default=0.05, ge=0.0, le=1.0)
    weight_short_potential: float = Field(default=0.05, ge=0.0, le=1.0)

    # Thresholds & Penalty factors
    risk_penalty_scale: float = Field(default=0.30, ge=0.0, le=1.0)  # Max risk penalty scaled down to avoid over-punishing
    low_coverage_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    low_confidence_threshold: float = Field(default=50.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_weights_total(self) -> "ProfitabilityConfig":
        total = (
            self.weight_demand
            + self.weight_outliers
            + self.weight_revenue_potential
            + self.weight_competition
            + self.weight_geography
            + self.weight_evergreen
            + self.weight_production
            + self.weight_content_depth
            + self.weight_short_potential
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Profitability component weights must sum to 1.0 (got {total:.4f}).")
        return self

    def get_weights_dict(self) -> Dict[str, float]:
        return {
            "demand": self.weight_demand,
            "outliers": self.weight_outliers,
            "revenue_potential": self.weight_revenue_potential,
            "competition": self.weight_competition,
            "geography": self.weight_geography,
            "evergreen": self.weight_evergreen,
            "production": self.weight_production,
            "content_depth": self.weight_content_depth,
            "short_potential": self.weight_short_potential,
        }


profitability_config = ProfitabilityConfig()
