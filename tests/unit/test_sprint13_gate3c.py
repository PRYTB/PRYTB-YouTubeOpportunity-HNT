"""Qualification boundaries and identity-safe evidence reconstruction."""

from copy import deepcopy

import pytest

from app.analytics.qualified_pool import (
    EvidenceError, payload_hash, qualification, reconstruct_economics, semantic_partition,
)


@pytest.mark.parametrize("semantic,structural,score,economic,combined", [
    (True, True, 50.0, True, True),
    (True, True, 49.999999999, False, False),
    (True, True, 0.0, False, False),
    (False, True, 90.0, True, False),
    (True, False, 90.0, True, False),
    (False, False, 90.0, True, False),
    (True, True, None, None, None),
    (False, True, None, None, False),
    (True, False, None, None, False),
])
def test_qualification(semantic, structural, score, economic, combined):
    assert qualification(semantic, structural, score) == (economic, combined)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -1.0, 100.1])
def test_invalid_scores_fail_closed(score):
    with pytest.raises(EvidenceError):
        qualification(True, True, score)


def definition(candidate="sample", intent="python tutorial", channels=2, outliers=1):
    return {"definition_id": candidate, "normalized_intent": intent,
            "video_count": 10, "channel_count": channels, "outlier_count": outliers}


def test_partition_is_order_independent_and_explains_exclusions():
    source = [definition("c", "es la"), definition("b", channels=1, outliers=0),
              definition("a")]
    result = semantic_partition(source)
    assert result == semantic_partition(list(reversed(source)))
    assert [r["candidate_id"] for r in result] == ["a", "b", "c"]
    assert len({r["partition"] for r in result}) == 3
    assert result[1]["structural_exclusion_reasons"] == [
        "SINGLE_CHANNEL_ARTIFACT", "ZERO_VIRAL_OUTLIERS",
    ]
    assert result[2]["semantic_rejection_reason"] == "STOPWORD_ONLY_ARTIFACT"
    assert qualification(result[2]["semantic_valid"], True, 100)[1] is False


def test_missing_structural_data_does_not_invent_exclusion():
    row = definition()
    row["channel_count"] = None
    with pytest.raises(EvidenceError):
        semantic_partition([row])


def test_duplicate_candidates_rejected():
    with pytest.raises(EvidenceError):
        semantic_partition([definition(), definition()])


def source_evidence():
    runs = {"profitability": "p", "market": "m", "production": "r"}
    evidence = {name: {"source_cluster_run_id": "source", "run_id": run,
                       "cluster_id": 7, "metrics": {"video_count": 10}}
                for name, run in runs.items()}
    evidence["profitability"].update(confidence=80.0, profitability_score=50.0)
    evidence["profitability"]["metrics"].update(
        demand_score=50.0, outlier_score=50.0, revenue_potential_score=50.0,
        geography_score=50.0, content_depth_score=None, short_potential_score=None,
    )
    evidence["market"].update(competition_score=50.0, evergreen_score=50.0)
    evidence["production"].update(production_cost_score=50.0, overall_risk_score=0.0)
    return runs, evidence


def test_exact_formula_and_optional_component_renormalization():
    runs, evidence = source_evidence()
    result = reconstruct_economics(definition(), {"sample": 7}, evidence, "source", runs)
    assert result["economic_score"] == pytest.approx(50.0)
    assert result["known_component_weight"] == pytest.approx(0.90)
    assert result["components"]["content_depth"] is None
    assert result["risk_penalty"] == 0
    assert result["formula_version"] == "sprint13-gate2a-v1"


def test_parent_cluster_cannot_borrow_another_candidates_score():
    runs, evidence = source_evidence()
    row = definition("expansion")
    row["parent_cluster_id"] = 7
    with pytest.raises(EvidenceError, match="MISSING_CANDIDATE_SCOPED"):
        reconstruct_economics(row, {"other_candidate": 7}, evidence, "source", runs)


@pytest.mark.parametrize("field,value", [
    ("cluster_id", 8), ("source_cluster_run_id", "foreign"), ("run_id", "foreign"),
])
def test_mismatched_economic_lineage_rejected(field, value):
    runs, evidence = source_evidence()
    evidence["market"][field] = value
    with pytest.raises(EvidenceError, match="Wrong candidate lineage"):
        reconstruct_economics(definition(), {"sample": 7}, evidence, "source", runs)


def test_mismatched_candidate_population_rejected():
    runs, evidence = source_evidence()
    evidence["profitability"]["metrics"]["video_count"] = 208
    with pytest.raises(EvidenceError, match="Wrong candidate lineage"):
        reconstruct_economics(definition(), {"sample": 7}, evidence, "source", runs)


def test_missing_analysis_does_not_award_default_score():
    runs, evidence = source_evidence()
    del evidence["production"]
    with pytest.raises(EvidenceError, match="Missing production"):
        reconstruct_economics(definition(), {"sample": 7}, evidence, "source", runs)


def test_hash_is_deterministic_and_sensitive_to_decisions():
    payload = {"source": "source", "decisions": [
        {"candidate_id": "b", "economic_score": 49.9999},
        {"candidate_id": "a", "economic_score": 50.0},
    ]}
    reordered = {"decisions": list(reversed(payload["decisions"])), "source": "source"}
    assert payload_hash(payload) == payload_hash(reordered)
    changed = deepcopy(payload)
    changed["decisions"][0]["economic_score"] = 50.0
    assert payload_hash(payload) != payload_hash(changed)
    with pytest.raises(EvidenceError):
        payload_hash({"decisions": [payload["decisions"][0]] * 2})
