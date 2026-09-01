from typing import Dict, List, Any, Optional
from pydantic import BaseModel

# Centralized YouTube API v3 Quota Costs
DEFAULT_QUOTA_COSTS: Dict[str, int] = {
    "search.list": 100,
    "videos.list": 1,
    "channels.list": 1,
}

class QuotaOperation(BaseModel):
    operation: str
    requests: int = 1
    estimated_units: int

class QuotaTracker:
    def __init__(self, custom_costs: Optional[Dict[str, int]] = None):
        self.costs = custom_costs or DEFAULT_QUOTA_COSTS.copy()
        self.history: List[QuotaOperation] = []
        self.total_estimated_units: int = 0
        self.total_requests: int = 0

    def track(self, operation: str, requests: int = 1) -> int:
        unit_cost = self.costs.get(operation, 1)
        units = unit_cost * requests
        op = QuotaOperation(operation=operation, requests=requests, estimated_units=units)
        self.history.append(op)
        self.total_estimated_units += units
        self.total_requests += requests
        return units

    def reset(self) -> None:
        self.history.clear()
        self.total_estimated_units = 0
        self.total_requests = 0

    def summary(self) -> Dict[str, Any]:
        return {
            "total_estimated_units": self.total_estimated_units,
            "total_requests": self.total_requests,
            "operations": [op.model_dump() for op in self.history]
        }
