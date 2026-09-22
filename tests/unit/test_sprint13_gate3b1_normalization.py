import pytest
from app.analytics.text_normalizer import (
    normalize_intent_string,
    validate_intent_semantic_quality,
    COMMON_STOPWORDS
)

def test_stopword_only_rejection():
    # Known artifacts
    invalid_intents = ["es la", "de en", "es es la", "cómo de", "the of and"]
    for intent in invalid_intents:
        is_valid, reason = validate_intent_semantic_quality(intent)
        assert not is_valid, f"Expected '{intent}' to be invalid, but was valid"
        assert reason == "STOPWORD_ONLY_ARTIFACT"

def test_duplicate_token_normalization():
    # Redundant tokens like "de de software" should normalize to "de software"
    intent = "de de software"
    normalized = normalize_intent_string(intent)
    assert normalized == "de software"
    
    # Check that "de software" is semantically valid because "software" is a meaningful token
    is_valid, reason = validate_intent_semantic_quality(normalized)
    assert is_valid
    assert reason == "VALID"

def test_meaningful_short_intents_preserved():
    # Valid short intents with meaningful technical / domain words
    valid_intents = ["python tutorial", "notion app", "saas architecture", "ai agents", "rtx 5090"]
    for intent in valid_intents:
        is_valid, reason = validate_intent_semantic_quality(intent)
        assert is_valid, f"Expected '{intent}' to be valid"
        assert reason == "VALID"

def test_utf8_encoding_safety():
    # "cómo" with Spanish accent
    intent = "calendar cómo"
    normalized = normalize_intent_string(intent)
    assert "cómo" in normalized or "como" in normalized
    is_valid, reason = validate_intent_semantic_quality(normalized)
    assert is_valid

def test_def_052_exclusion_behavior():
    # def_052 stored intent "es la"
    is_valid, reason = validate_intent_semantic_quality("es la")
    assert not is_valid
    assert reason == "STOPWORD_ONLY_ARTIFACT"

def test_opportunity_validator_guard():
    from app.analytics.opportunity_validator import OpportunityValidator
    validator = OpportunityValidator()
    
    # def_052 invalid
    is_valid, reason = validator.validate_semantic_eligibility("es la")
    assert not is_valid
    
    # def_045 valid
    is_valid, reason = validator.validate_semantic_eligibility("de software")
    assert is_valid
