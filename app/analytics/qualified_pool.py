"""Identity-safe qualification using the approved Sprint13 Gate2A formula."""

import hashlib
import json
import math
from typing import Any

from app.analytics.opportunity_validator import OpportunityValidator
from app.config.profitability_config import profitability_config

FORMULA_VERSION = "sprint13-gate2a-v1"
THRESHOLD = 50.0


class EvidenceError(ValueError):
    """Candidate-scoped evidence cannot be established."""


def semantic_partition(definitions: list[dict]) -> list[dict]:
    """Partition once, with semantic rejection taking precedence."""
    ids = [d["definition_id"] for d in definitions]
    if len(ids) != len(set(ids)):
        raise EvidenceError("Duplicate candidate definitions")
    validator = OpportunityValidator()
    decisions = []
    for definition in sorted(definitions, key=lambda d: d["definition_id"]):
        valid, reason = validator.validate_semantic_eligibility(
            definition["normalized_intent"]
        )
        counts = {k: definition[k] for k in (
            "video_count", "channel_count", "outlier_count"
        )}
        if any(type(v) is not int or v < 0 for v in counts.values()):
            raise EvidenceError("Missing or invalid structural counts")
        exclusions = []
        if counts["channel_count"] <= 1:
            exclusions.append("SINGLE_CHANNEL_ARTIFACT")
        if counts["outlier_count"] == 0:
            exclusions.append("ZERO_VIRAL_OUTLIERS")
        if counts["video_count"] < 1:
            exclusions.append("INSUFFICIENT_VIDEO_COUNT")
        structural = not exclusions
        partition = (
            "SEMANTICALLY_INVALID" if not valid else
            "SEMANTICALLY_VALID_AND_STRUCTURALLY_ELIGIBLE" if structural else
            "SEMANTICALLY_VALID_BUT_STRUCTURALLY_EXCLUDED"
        )
        decisions.append({
            "candidate_id": definition["definition_id"],
            "canonical_intent": definition["normalized_intent"],
            "canonical_label": definition["normalized_intent"],
            "semantic_valid": valid,
            "semantic_rejection_reason": None if valid else reason,
            "structural_eligible": structural,
            "structural_exclusion_reasons": exclusions,
            "structural_evidence": counts,
            "partition": partition,
        })
    return decisions


def qualification(semantic_valid: bool, structural_eligible: bool,
                  score: float | None) -> tuple[bool | None, bool | None]:
    """Keep unknown economics distinct from an observed economic failure."""
    if score is not None and (not math.isfinite(score) or not 0 <= score <= 100):
        raise EvidenceError("Invalid economic score")
    economic = None if score is None else score >= THRESHOLD
    combined = economic if semantic_valid and structural_eligible else False
    return economic, combined


def reconstruct_economics(
    definition: dict, mapping: dict[str, int], evidence: dict[str, dict],
    source_run_id: str, source_analysis_runs: dict[str, str],
) -> dict:
    """Never confuse a physical parent cluster with a Top20 evaluation ordinal."""
    candidate_id = definition["definition_id"]
    if candidate_id not in mapping:
        raise EvidenceError("MISSING_CANDIDATE_SCOPED_ECONOMIC_EVIDENCE")
    evaluation_id = mapping[candidate_id]
    if len(set(mapping.values())) != len(mapping):
        raise EvidenceError("Ambiguous evaluation mapping")
    for name in ("profitability", "market", "production"):
        row = evidence.get(name)
        if not row:
            raise EvidenceError(f"Missing {name} evidence")
        metrics = row["metrics"]
        if (
            row["source_cluster_run_id"] != source_run_id
            or row["run_id"] != source_analysis_runs[name]
            or row["cluster_id"] != evaluation_id
            or metrics["video_count"] != definition["video_count"]
        ):
            raise EvidenceError(f"Wrong candidate lineage: {name}")

    prof = evidence["profitability"]
    metrics = prof["metrics"]
    market, production = evidence["market"], evidence["production"]
    # Same optional-component handling and arithmetic as Gate2A build_chain.
    components = {
        "demand": float(metrics.get("demand_score", 0.0)),
        "outliers": float(metrics.get("outlier_score", 0.0)),
        "revenue_potential": float(metrics.get("revenue_potential_score", 0.0)),
        "competition": 100.0 - float(market["competition_score"]),
        "geography": float(metrics.get("geography_score", 60.0)),
        "evergreen": float(market["evergreen_score"]),
        "production": 100.0 - float(production["production_cost_score"]),
        "content_depth": metrics.get("content_depth_score"),
        "short_potential": metrics.get("short_potential_score"),
    }
    if any(v is not None and (not math.isfinite(float(v)) or not 0 <= v <= 100)
           for v in components.values()):
        raise EvidenceError("Invalid component")
    weights = profitability_config.get_weights_dict()
    known_weight = sum(weights[k] for k, v in components.items() if v is not None)
    base = sum(float(v) * weights[k] for k, v in components.items()
               if v is not None) / known_weight
    risk = float(production["overall_risk_score"])
    if not math.isfinite(risk) or not 0 <= risk <= 100:
        raise EvidenceError("Invalid risk")
    penalty = risk * profitability_config.risk_penalty_scale
    score = max(0.0, min(100.0, base - penalty))
    if not math.isclose(score, float(prof["profitability_score"]), abs_tol=0.001,
                        rel_tol=0.0):
        raise EvidenceError("Score does not reproduce persisted evidence")
    limiting = sorted(
        ({"component": k, "value": v,
          "weighted_shortfall_from_100": (100.0 - float(v)) * weights[k] / known_weight}
         for k, v in components.items() if v is not None),
        key=lambda x: (-x["weighted_shortfall_from_100"], x["component"]),
    )[:3]
    return {
        "economic_score": score,
        "threshold": THRESHOLD,
        "formula_version": FORMULA_VERSION,
        "components": components,
        "known_component_weight": known_weight,
        "base_score": base,
        "risk_penalty": penalty,
        "overall_risk_score": risk,
        "main_limiting_components": limiting,
        "evidence_confidence": prof["confidence"],
        "confidence_scope": "Persisted candidate profitability analysis; not monetary certainty",
        "evaluation_cluster_id": evaluation_id,
        "source_analysis_run_ids": source_analysis_runs,
        "evidence_type": "DERIVED",
    }


def canonical_payload(payload: dict[str, Any]) -> str:
    """Canonical keys and candidate order; reject duplicates and non-finite JSON."""
    result = dict(payload)
    decisions = result["decisions"]
    ids = [d["candidate_id"] for d in decisions]
    if len(ids) != len(set(ids)):
        raise EvidenceError("Duplicate persisted decisions")
    result["decisions"] = sorted(decisions, key=lambda d: d["candidate_id"])
    return json.dumps(result, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()
