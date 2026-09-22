"""
Sprint 10 Adversarial Opportunity Validator Engine.
"""
from typing import Tuple

class OpportunityValidator:
    """Adversarial Opportunity Validator for PRYTB."""
    def validate_semantic_eligibility(self, normalized_intent: str) -> Tuple[bool, str]:
        """
        Validates whether a normalized intent is semantically valid and non-artifact.
        Imports and uses validate_intent_semantic_quality from text_normalizer.
        """
        from app.analytics.text_normalizer import validate_intent_semantic_quality
        return validate_intent_semantic_quality(normalized_intent)
