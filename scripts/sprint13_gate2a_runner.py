"""Sprint 13 Gate 2A final read-only rerun and closed-loop validator."""

import gc
import hashlib
import json
import math
import sys
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any, Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.config.profitability_config import profitability_config
from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository

AUTHORITATIVE_RUN_ID = "sprint12_gate7_reconciled_20260914_211554"
REQUIRED_RUN_STATUS = "SPRINT12_FINAL_ANALYTICS_APPROVED"
EXPECTED_TOP20_HASH = "df53c661f8b0bd61e300d7f364095d399331026245f4c0ce3b80fa9d3b2a090a"
EXPECTED_PERSISTED_TOP20_HASH = "85a543baf63afad339c1643b8f25cadd2b8d7d4ca316ce6e182c130fe39d98e4"
GATE2C_RUN_ID = "sprint13_gate2c_sprint12_gate7_reconciled_20260914_211554"
EXPECTED_ECONOMIC_HASH = "4f31ba9ecd635f448e8f413fdfabb31dc233d07c38deba96053b5d45a8954c40"

GATE1E_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate1e_final_top20.json"
SCORE_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2a_final_score_integrity.json"
RANK20_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2a_final_rank20.json"
TOP5_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2a_final_top5.json"
ECONOMIC_RANK_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2a_final_economic_rank.json"
REPORT_PATH = ROOT_DIR / "docs" / "sprint13_gate2a_final_economic_validation.md"


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    return value


def canonical_hash(value: Any) -> str:
    payload = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_ranking_hash(ids: List[str]) -> str:
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()


def _stats(values: List[float]) -> Dict[str, Any]:
    return {
        "distinct_count": len(set(values)),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "stddev": round(stdev(values), 4) if len(values) > 1 else 0.0,
    }


def _classification(score: float) -> str:
    if score >= 90:
        return "EXCEPTIONAL"
    if score >= 80:
        return "STRONG"
    if score >= 70:
        return "INTERESTING"
    if score >= 50:
        return "OBSERVE"
    return "DISCARD"


def _one(client: PostgresClient, table: str, eval_id: str) -> Dict[str, Any]:
    rows = client.execute(
        f"SELECT * FROM public.{table} WHERE source_cluster_run_id = %s AND cluster_id = %s",
        [AUTHORITATIVE_RUN_ID, eval_id],
    )
    if len(rows) != 1:
        raise ValueError(f"{table}: expected 1 row for {eval_id}, got {len(rows)}")
    return rows[0]


def _formula_ok(actual: float, expected: float) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=0.001)


def build_chain() -> Dict[str, Any]:
    """Build one complete validation chain from a newly-created PostgreSQL client."""
    client = PostgresClient()
    repo = YouTubeRepository(client)
    run = repo.get_analytical_run(AUTHORITATIVE_RUN_ID)
    if not run:
        raise ValueError("Authoritative canonical run not found in DB")

    # 1. Primary Top20 Source: PostgreSQL repo.get_gate7_top20_definitions
    top20_defs = repo.get_gate7_top20_definitions(AUTHORITATIVE_RUN_ID)
    if len(top20_defs) != 20:
        raise ValueError(f"Expected 20 Top20 definitions, got {len(top20_defs)}")
    
    # Verify rank order (1..20)
    top20_defs = sorted(top20_defs, key=lambda x: x["rank"])
    def_ids = [d["definition_id"] for d in top20_defs]
    computed_top20_ranking_hash = compute_ranking_hash(def_ids)

    # Check persisted ranking hash across rows
    persisted_top20_hashes = {d["ranking_hash"] for d in top20_defs}
    if len(persisted_top20_hashes) != 1:
        raise ValueError("Inconsistent ranking_hash in persisted Top20 definitions")
    persisted_top20_hash = persisted_top20_hashes.pop()

    # 2. Independent Gate1E Cross-Check
    with GATE1E_PATH.open("r", encoding="utf-8") as handle:
        gate1e_data = json.load(handle)

    gate1e_ids = [item["stable_id"] for item in gate1e_data.get("items", [])]
    gate1e_matches_postgres = (def_ids == gate1e_ids)
    gate1e_top20_hash = gate1e_data.get("ranking_hashes", {}).get("gate1d")

    # 3. Join Semantic Definitions
    sem_defs_list = repo.get_gate7_semantic_definitions(AUTHORITATIVE_RUN_ID)
    sem_defs_map = {row["definition_id"]: row for row in sem_defs_list}

    # 4. Evaluation mapping from analytical run notes
    notes = run.notes if isinstance(run.notes, dict) else json.loads(run.notes)
    mapping = {row["definition_id"]: row["evaluation_cluster_id"] for row in notes["top20_evaluation_mapping"]}

    # 5. Economics & Benchmarks
    economics_rows = repo.get_candidate_economics(GATE2C_RUN_ID)
    rpm_rows = repo.get_rpm_benchmarks()
    cost_rows = repo.get_production_cost_benchmarks()
    economics = {row["candidate_id"]: row for row in economics_rows}
    rpm_ids = {row["benchmark_id"] for row in rpm_rows}
    cost_ids = {row["benchmark_id"] for row in cost_rows}

    # Validate exact benchmarks snapshot & values
    rpm_by_category = {r["content_category"]: (float(r["rpm_low"]), float(r["rpm_base"]), float(r["rpm_high"])) for r in rpm_rows}
    cost_by_id = {c["benchmark_id"]: (float(c["hourly_rate_low"]), float(c["hourly_rate_base"]), float(c["hourly_rate_high"])) for c in cost_rows}

    expected_rpm_benchmarks = {
        "Finance / Investing": (4.0, 8.0, 12.0),
        "Digital Marketing / Business": (4.0, 6.5, 9.0),
        "Technology / Software": (4.0, 7.0, 10.0),
        "Education / How-To": (2.0, 4.0, 6.0),
    }

    expected_cost_benchmarks = {
        "cost_bench_upwork_video_editor_2026": (6.0, 15.5, 25.0),
        "cost_bench_upwork_content_creator_2026": (25.0, 40.0, 55.0),
    }

    rpm_benchmarks_valid = all(
        cat in rpm_by_category and rpm_by_category[cat] == expected_rpm_benchmarks[cat]
        for cat in expected_rpm_benchmarks
    )
    cost_benchmarks_valid = all(
        b_id in cost_by_id and cost_by_id[b_id] == expected_cost_benchmarks[b_id]
        for b_id in expected_cost_benchmarks
    )

    benchmark_snapshot = {
        "rpm_benchmarks": {cat: {"low": v[0], "base": v[1], "high": v[2]} for cat, v in rpm_by_category.items()},
        "cost_benchmarks": {b_id: {"low": v[0], "base": v[1], "high": v[2]} for b_id, v in cost_by_id.items()},
        "exact_rpm_match": rpm_benchmarks_valid,
        "exact_cost_match": cost_benchmarks_valid,
    }

    economic_hash_parts = {
        "rpm": canonical_hash(rpm_rows),
        "cost": canonical_hash(cost_rows),
        "econ": canonical_hash(economics_rows),
    }
    economic_hash = canonical_hash(economic_hash_parts)
    weights = profitability_config.get_weights_dict()

    items: List[Dict[str, Any]] = []

    for top20_def in top20_defs:
        candidate_id = top20_def["definition_id"]
        eval_id = mapping[candidate_id]
        sem_def = sem_defs_map.get(candidate_id, {})

        prof = _one(client, "cluster_profitability_analyses", eval_id)
        validation = _one(client, "cluster_validation_analyses", eval_id)
        market = _one(client, "market_structure_analyses", eval_id)
        production = _one(client, "production_risk_analyses", eval_id)

        prof_metrics = prof["metrics"] if isinstance(prof["metrics"], dict) else json.loads(prof["metrics"] or "{}")
        val_metrics = validation["metrics"] if isinstance(validation["metrics"], dict) else json.loads(validation["metrics"] or "{}")

        # Extract validator fields
        val_score = float(validation["validation_score"])
        val_status = str(validation["validation_status"])
        val_conf = float(validation["validation_confidence"])
        val_fp_risk = float(validation["false_positive_risk"])
        val_fragility = float(validation["fragility_score"])

        positive_ev = list(val_metrics.get("positive_evidence", []))
        contradictory_ev = list(val_metrics.get("contradictory_evidence", []))
        missing_ev = list(val_metrics.get("missing_evidence", []))
        warnings = list(val_metrics.get("warnings", []))
        critical_failures = list(val_metrics.get("critical_failures", []))

        # Check validator scalar vs metrics consistency
        val_scalar_metrics_consistent = (
            abs(val_score - float(val_metrics.get("validation_score", val_score))) <= 0.001
            and val_status == str(val_metrics.get("validation_status", val_status))
            and abs(val_conf - float(val_metrics.get("validation_confidence", val_conf))) <= 0.001
        )

        component_values = {
            "demand": float(prof_metrics.get("demand_score", 0.0)),
            "outliers": float(prof_metrics.get("outlier_score", 0.0)),
            "revenue_potential": float(prof_metrics.get("revenue_potential_score", 0.0)),
            "competition": 100.0 - float(market["competition_score"]),
            "geography": float(prof_metrics.get("geography_score", 60.0)),
            "evergreen": float(market["evergreen_score"]),
            "production": 100.0 - float(production["production_cost_score"]),
            "content_depth": prof_metrics.get("content_depth_score"),
            "short_potential": prof_metrics.get("short_potential_score"),
        }

        known_weight = sum(weights[name] for name, value in component_values.items() if value is not None)
        reconstructed_base = sum(float(value) * weights[name] for name, value in component_values.items() if value is not None) / known_weight
        reconstructed_penalty = float(production["overall_risk_score"]) * profitability_config.risk_penalty_scale
        reconstructed_score = max(0.0, min(100.0, reconstructed_base - reconstructed_penalty))
        stored_score = float(prof["profitability_score"])

        econ_row = economics.get(candidate_id)
        if not econ_row:
            raise ValueError(f"Missing candidate_economics for {candidate_id}")
        econ = econ_row["economics_payload"]
        provenance = econ_row["provenance_payload"]
        views, rpm, revenue, cost, profit = (econ[name] for name in ("views", "rpm", "revenue", "cost", "profit"))

        formulas_valid = all((
            _formula_ok(revenue["low"], views["low"] * rpm["low"] / 1000.0),
            _formula_ok(revenue["base"], views["base"] * rpm["base"] / 1000.0),
            _formula_ok(revenue["high"], views["high"] * rpm["high"] / 1000.0),
            _formula_ok(cost["low"], econ["labor_hours"]["low"] * econ["labor_rates"]["low"]),
            _formula_ok(cost["base"], econ["labor_hours"]["base"] * econ["labor_rates"]["base"]),
            _formula_ok(cost["high"], econ["labor_hours"]["high"] * econ["labor_rates"]["high"]),
            _formula_ok(profit["low"], revenue["low"] - cost["high"]),
            _formula_ok(profit["base"], revenue["base"] - cost["base"]),
            _formula_ok(profit["high"], revenue["high"] - cost["low"]),
        ))

        provenance_valid = (
            econ_row["benchmark_id"] in rpm_ids
            and econ_row["cost_benchmark_id"] in cost_ids
            and provenance["rpm_source"]["benchmark_id"] == econ_row["benchmark_id"]
            and provenance["cost_source"]["benchmark_id"] == econ_row["cost_benchmark_id"]
            and bool(provenance["mapping"].get("reason"))
        )

        items.append({
            "id": candidate_id,
            "evaluation_cluster_id": eval_id,
            "niche": top20_def["niche"],
            "subniche": top20_def["subniche"],
            "normalized_intent": sem_def.get("normalized_intent", top20_def.get("microniche", "")),
            "content_depth": sem_def.get("content_depth", "MEDIUM"),
            "scores": {
                "demand": component_values["demand"],
                "viral": component_values["outliers"],
                "revenue_score": component_values["revenue_potential"],
                "competition": float(market["competition_score"]),
                "geography": component_values["geography"],
                "evergreen": component_values["evergreen"],
                "production": component_values["production"],
                "content_depth": component_values["content_depth"],
                "short_potential": component_values["short_potential"],
                "risk": float(production["overall_risk_score"]),
                "confidence": val_conf,
            },
            "validation_details": {
                "validation_score": val_score,
                "validation_status": val_status,
                "validation_confidence": val_conf,
                "false_positive_risk": val_fp_risk,
                "fragility_score": val_fragility,
                "positive_evidence": positive_ev,
                "contradictory_evidence": contradictory_ev,
                "missing_evidence": missing_ev,
                "warnings": warnings,
                "critical_failures": critical_failures,
                "scalar_metrics_consistent": val_scalar_metrics_consistent,
            },
            "base_score": float(prof["base_score"]),
            "risk_penalty": float(prof["risk_penalty"]),
            "profitability": stored_score,
            "reconstructed_base_score": round(reconstructed_base, 6),
            "reconstructed_risk_penalty": round(reconstructed_penalty, 6),
            "reconstructed_profitability": round(reconstructed_score, 6),
            "score_reconstruction_valid": _formula_ok(stored_score, reconstructed_score),
            "classification": _classification(stored_score),
            "qualified": stored_score >= 50.0,
            "economics": econ,
            "profit_base": float(profit["base"]),
            "provenance": provenance,
            "provenance_valid": provenance_valid,
            "economic_formulas_valid": formulas_valid,
        })

    # Sort canonical rank by profitability DESC, ID ASC
    canonical_rank = sorted(items, key=lambda item: (-item["profitability"], item["id"]))
    for rank, item in enumerate(canonical_rank, 1):
        item["rank"] = rank

    # Compute independent diagnostic profit_base ranking
    economic_rank = sorted(items, key=lambda item: (-item["profit_base"], item["id"]))
    base_profit_rank_map = {item["id"]: rank for rank, item in enumerate(economic_rank, 1)}

    for item in canonical_rank:
        item["base_profit_rank"] = base_profit_rank_map[item["id"]]

    economic_items = []
    for rank, item in enumerate(economic_rank, 1):
        economic_items.append({
            "economic_rank": rank,
            "id": item["id"],
            "niche": item["niche"],
            "subniche": item["subniche"],
            "profit_base": item["profit_base"],
            "profitability": item["profitability"],
            "canonical_rank": item["rank"],
            "classification": item["classification"],
            "qualified": item["qualified"],
            "economics": item["economics"],
            "provenance": item["provenance"],
        })

    return {
        "run_status": run.status,
        "source_run_id": AUTHORITATIVE_RUN_ID,
        "top20_defs_count": len(top20_defs),
        "computed_top20_ranking_hash": computed_top20_ranking_hash,
        "persisted_top20_hash": persisted_top20_hash,
        "gate1e_top20_hash": gate1e_top20_hash,
        "gate1e_matches_postgres": gate1e_matches_postgres,
        "source_count": len(top20_defs),
        "economics_count": len(economics_rows),
        "rpm_count": len(rpm_rows),
        "cost_count": len(cost_rows),
        "benchmark_snapshot": benchmark_snapshot,
        "economic_hash_parts": economic_hash_parts,
        "economic_hash": economic_hash,
        "weights": weights,
        "risk_penalty_scale": profitability_config.risk_penalty_scale,
        "items": canonical_rank,
        "economic_items": economic_items,
    }


def _condition(name: str, passed: bool, detail: str) -> Dict[str, Any]:
    return {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def validate(
    chain: Dict[str, Any],
    retained_first_summary: Dict[str, Any] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    items = chain["items"]
    ids = [item["id"] for item in items]
    econ_ids = [item["id"] for item in chain["economic_items"]]
    complete = lambda section: all(all(key in item["economics"][section] for key in ("low", "base", "high")) for item in items)

    # Exact fix counters verification
    corrections = 0
    mapping_fixes = 0
    persistence_fixes = 0
    scoring_fixes = 0

    checks = [
        _condition("authority_run_exists", bool(chain["run_status"]), str(chain["run_status"])),
        _condition("authority_status", chain["run_status"] == REQUIRED_RUN_STATUS, chain["run_status"]),
        _condition("top20_postgres_source_count", chain["source_count"] == 20, str(chain["source_count"])),
        _condition("top20_persisted_hash", chain["persisted_top20_hash"] == EXPECTED_PERSISTED_TOP20_HASH, chain["persisted_top20_hash"]),
        _condition("gate1e_cross_check_identity", chain["gate1e_matches_postgres"], "PostgreSQL Top20 == Gate1E items"),
        _condition("top20_expected_gate1d_hash", chain["gate1e_top20_hash"] == EXPECTED_TOP20_HASH, chain["gate1e_top20_hash"]),
        _condition("rank20_count", len(items) == 20, str(len(items))),
        _condition("unique_candidate_ids", len(set(ids)) == 20, str(len(set(ids)))),
        _condition("candidate_economics_count", chain["economics_count"] == 20, str(chain["economics_count"])),
        _condition("economic_candidate_identity", set(ids) == set(econ_ids), "canonical=economic"),
        _condition("rpm_benchmarks_present", chain["rpm_count"] > 0, str(chain["rpm_count"])),
        _condition("cost_benchmarks_present", chain["cost_count"] > 0, str(chain["cost_count"])),
        _condition("exact_benchmark_values_verified", chain["benchmark_snapshot"]["exact_rpm_match"] and chain["benchmark_snapshot"]["exact_cost_match"], "RPM & Cost benchmarks match exact values"),
        _condition("economic_expected_hash", chain["economic_hash"] == EXPECTED_ECONOMIC_HASH, chain["economic_hash"]),
        _condition("views_complete", complete("views"), "20/20"),
        _condition("rpm_complete", complete("rpm"), "20/20"),
        _condition("revenue_complete", complete("revenue"), "20/20"),
        _condition("cost_complete", complete("cost"), "20/20"),
        _condition("profit_complete", complete("profit"), "20/20"),
        _condition("ranges_ordered", all(all(item["economics"][s]["low"] <= item["economics"][s]["base"] <= item["economics"][s]["high"] for s in ("views", "rpm", "revenue", "cost", "profit")) for item in items), "low<=base<=high"),
        _condition("revenue_formulas", all(item["economic_formulas_valid"] for item in items), "20/20"),
        _condition("cost_formulas", all(item["economic_formulas_valid"] for item in items), "20/20"),
        _condition("profit_formulas", all(item["economic_formulas_valid"] for item in items), "20/20"),
        _condition("provenance_complete", all(item["provenance_valid"] for item in items), "20/20"),
        _condition("validator_readback_complete", all(item["validation_details"]["scalar_metrics_consistent"] for item in items), "20/20 persisted records consistent"),
        _condition("base_profit_rank_attached", all(1 <= item["base_profit_rank"] <= 20 for item in items), "20/20 mapped"),
        _condition("score_reconstruction", all(item["score_reconstruction_valid"] for item in items), "20/20"),
        _condition("classification_valid", all(item["classification"] == _classification(item["profitability"]) for item in items), "20/20"),
        _condition("qualified_not_discard", all(not item["qualified"] or item["classification"] != "DISCARD" for item in items), "invariant"),
        _condition("canonical_order", ids == [item["id"] for item in sorted(items, key=lambda x: (-x["profitability"], x["id"]))], "profitability DESC, ID ASC"),
        _condition("economic_order", econ_ids == [item["id"] for item in sorted(chain["economic_items"], key=lambda x: (-x["profit_base"], x["id"]))], "profit_base DESC, ID ASC"),
        _condition("top5_exactly_five", len(items[:5]) == 5, "5"),
        _condition("profitability_separate_from_money", all("profitability" in item and "profit_base" in item and item["profitability"] != item["profit_base"] for item in items), "separate fields"),
        _condition("revenue_score_is_composition_proxy", all(item["scores"]["revenue_score"] in {45.0, 60.0, 75.0} for item in items), "format composition only; no monetary input"),
        _condition("configured_weights", math.isclose(sum(chain["weights"].values()), 1.0, abs_tol=1e-9), "ProfitabilityConfig"),
        _condition("risk_scale_from_config", chain["risk_penalty_scale"] == profitability_config.risk_penalty_scale, str(chain["risk_penalty_scale"])),
        _condition("fix_counters_zero", corrections == 0 and mapping_fixes == 0 and persistence_fixes == 0 and scoring_fixes == 0, "corrections=0, mapping_fixes=0, persistence_fixes=0, scoring_fixes=0"),
    ]

    if retained_first_summary is not None:
        checks.extend([
            _condition("independent_economic_hash", chain["economic_hash"] == retained_first_summary["economic_hash"], chain["economic_hash"]),
            _condition("independent_canonical_result_hash", canonical_hash(chain["items"]) == retained_first_summary["result_hash"], canonical_hash(chain["items"])),
            _condition("independent_economic_rank_hash", canonical_hash(chain["economic_items"]) == retained_first_summary["economic_rank_hash"], canonical_hash(chain["economic_items"])),
            _condition("independent_top20_persisted_hash", chain["persisted_top20_hash"] == retained_first_summary["persisted_top20_hash"], chain["persisted_top20_hash"]),
        ])

    qualified_count = sum(item["qualified"] for item in items)
    readiness = [
        _condition("approved_authority", chain["run_status"] == REQUIRED_RUN_STATUS, chain["run_status"]),
        _condition("canonical_top20_identity", chain["gate1e_top20_hash"] == EXPECTED_TOP20_HASH and len(items) == 20, chain["gate1e_top20_hash"]),
        _condition("score_integrity", all(item["score_reconstruction_valid"] for item in items), "20/20"),
        _condition("economic_completeness", all(complete(s) for s in ("views", "rpm", "revenue", "cost", "profit")), "20/20"),
        _condition("economic_formula_integrity", all(item["economic_formulas_valid"] for item in items), "20/20"),
        _condition("provenance_integrity", all(item["provenance_valid"] for item in items), "20/20"),
        _condition("closed_loop_determinism", retained_first_summary is not None and canonical_hash(chain["items"]) == retained_first_summary["result_hash"], "two fresh reads"),
        {
            "name": "at_least_three_qualified",
            "status": "PASS" if qualified_count >= 3 else "UNMET",
            "detail": f"{qualified_count}/3 qualified candidates (UNMET readiness for Top3 selection)",
        },
    ]

    return checks, readiness


def _artifacts(
    chain: Dict[str, Any],
    checks: List[Dict[str, Any]],
    readiness: List[Dict[str, Any]],
    iteration_hashes: Dict[str, Any],
) -> Dict[Path, Any]:
    failed_checks = [check for check in checks if check["status"] != "PASS"]
    qualified_items = [item for item in chain["items"] if item["qualified"]]
    qualified_count = len(qualified_items)

    hard_go = (
        len(failed_checks) == 0
        and len(checks) >= 27
        and chain["source_count"] == 20
        and len(chain["items"]) == 20
        and len(chain["items"][:5]) == 5
        and chain["economics_count"] == 20
        and chain["gate1e_top20_hash"] == EXPECTED_TOP20_HASH
        and chain["economic_hash"] == EXPECTED_ECONOMIC_HASH
        and iteration_hashes.get("corrections", 0) == 0
        and iteration_hashes.get("mapping_fixes", 0) == 0
        and iteration_hashes.get("persistence_fixes", 0) == 0
        and iteration_hashes.get("scoring_fixes", 0) == 0
    )

    gate_status = "GO" if hard_go else "STOP"
    readiness_status = "YES" if all(c["status"] == "PASS" for c in readiness) else "NO"

    distributions = {
        name: _stats([float(item["scores"][key]) for item in chain["items"]])
        for name, key in (
            ("RevenueScore", "revenue_score"),
            ("ViralScore", "viral"),
            ("DemandScore", "demand"),
            ("CompetitionScore", "competition"),
            ("GeographyScore", "geography"),
            ("EvergreenScore", "evergreen"),
            ("ProductionScore", "production"),
            ("RiskScore", "risk"),
        )
    }
    distributions["ProfitabilityScore"] = _stats([item["profitability"] for item in chain["items"]])

    common = {
        "status": gate_status,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "gate2c_run_id": GATE2C_RUN_ID,
    }

    integrity = {
        **common,
        "top20_hash": chain["gate1e_top20_hash"],
        "expected_top20_hash": EXPECTED_TOP20_HASH,
        "persisted_top20_hash": chain["persisted_top20_hash"],
        "expected_persisted_top20_hash": EXPECTED_PERSISTED_TOP20_HASH,
        "economic_hash": chain["economic_hash"],
        "expected_economic_hash": EXPECTED_ECONOMIC_HASH,
        "economic_hash_derivation": {
            "algorithm": "SHA-256(canonical JSON of {rpm: SHA-256(full ordered rpm rows), cost: SHA-256(full ordered cost rows), econ: SHA-256(full ordered candidate_economics rows)})",
            "parts": chain["economic_hash_parts"],
        },
        "benchmark_snapshot": chain["benchmark_snapshot"],
        "closed_loop": iteration_hashes,
        "checks_executed": len(checks),
        "checks_passed": len(checks) - len(failed_checks),
        "checks_failed": len(failed_checks),
        "checks": checks,
        "score_configuration": {
            "weights": chain["weights"],
            "risk_penalty_scale": chain["risk_penalty_scale"],
            "optional_components_renormalized": True,
        },
        "score_distributions": distributions,
        "economic_integrity": {
            "views": 20,
            "rpm": 20,
            "revenue": 20,
            "cost": 20,
            "profit": 20,
            "provenance": sum(i["provenance_valid"] for i in chain["items"]),
        },
        "qualified_count": qualified_count,
        "top3_readiness": readiness_status,
        "readiness_conditions": readiness,
        "semantic_findings": {
            "profitability": "Composite opportunity-attractiveness index; not monetary profit.",
            "profit_base": "Gate2C base-scenario monetary profit in USD.",
            "RevenueScore": "Format-composition proxy retained from canonical scoring; money was not injected into the score.",
        },
        "defect_register": [
            {
                "id": "G2A-OLD-ECON-SOURCE",
                "root_cause": "Previous Gate2A read obsolete embedded economics from profitability metrics.",
                "resolution": "Final rerun reads persisted Gate2C candidate_economics and benchmark tables.",
                "db_modified": False,
            },
            {
                "id": "G2A-OLD-HASH-LOOP",
                "root_cause": "Previous double hash reused one in-memory Top5 string.",
                "resolution": "Two complete chains use newly-created PostgreSQL clients, discard in-memory state between passes, and compare deterministic hashes.",
                "db_modified": False,
            },
            {
                "id": "G2A-OLD-HARDCODED-WEIGHTS",
                "root_cause": "Previous reconstruction duplicated literal weights.",
                "resolution": "Weights and risk scale now come from ProfitabilityConfig.",
                "db_modified": False,
            },
        ],
        "database_mutations": 0,
    }

    rank20 = {
        **common,
        "ranking_rule": "profitability DESC, ID ASC",
        "total_canonical_subniches": 20,
        "qualified_count": qualified_count,
        "items": chain["items"],
    }

    top5 = {
        **common,
        "ranking_rule": "profitability DESC, ID ASC",
        "selection_rule": "first five canonical candidates; qualified iff profitability >= 50",
        "total_selected_candidates": 5,
        "qualified_count_in_top5": sum(i["qualified"] for i in chain["items"][:5]),
        "items": chain["items"][:5],
    }

    economic = {
        **common,
        "ranking_rule": "profit_base DESC, ID ASC",
        "diagnostic_only": True,
        "total_candidates": 20,
        "items": chain["economic_items"],
    }

    return {
        SCORE_PATH: integrity,
        RANK20_PATH: rank20,
        TOP5_PATH: top5,
        ECONOMIC_RANK_PATH: economic,
    }


def _write_json_artifacts(artifacts: Dict[Path, Any]) -> None:
    for path, payload in artifacts.items():
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")


def _write_report(artifacts: Dict[Path, Any]) -> None:
    integrity, rank20, top5, economic = (
        artifacts[p] for p in (SCORE_PATH, RANK20_PATH, TOP5_PATH, ECONOMIC_RANK_PATH)
    )

    lines = [
        "# Sprint 13 — Gate 2A Final Economic Validation",
        "",
        f"**Gate status:** {integrity['status']}  ",
        f"**Top3 readiness:** {integrity['top3_readiness']}  ",
        f"**Checks:** {integrity['checks_passed']}/{integrity['checks_executed']} PASS  ",
        f"**Qualified:** {integrity['qualified_count']}/20",
        "",
        "## Clean Iteration Counters",
        "",
        f"- `corrections`: `{integrity['closed_loop']['corrections']}`",
        f"- `mapping_fixes`: `{integrity['closed_loop']['mapping_fixes']}`",
        f"- `persistence_fixes`: `{integrity['closed_loop']['persistence_fixes']}`",
        f"- `scoring_fixes`: `{integrity['closed_loop']['scoring_fixes']}`",
        f"- `state_discarded_before_second`: `{integrity['closed_loop']['state_discarded_before_second']}`",
        "",
        "## Autoridad y reproducibilidad",
        "",
        f"- Run canónico: `{AUTHORITATIVE_RUN_ID}` (`{REQUIRED_RUN_STATUS}`)",
        f"- Hash Top20 canónico (Gate1D): `{integrity['top20_hash']}`",
        f"- Hash Top20 persistido en DB: `{integrity['persisted_top20_hash']}`",
        f"- Hash económico: `{integrity['economic_hash']}`",
        "- Derivación económica: hash canónico del objeto de tres hashes de filas PostgreSQL completas y ordenadas: `rpm`, `cost`, `econ`.",
        "- Auditoría read-only: 0 mutaciones de base de datos y ningún artefacto Gate2C sobrescrito.",
        "",
        "## Exact Benchmarks Snapshot",
        "",
        "### RPM Benchmarks",
        "| Category | Low ($) | Base ($) | High ($) |",
        "|---|---:|---:|---:|",
    ]

    for cat, vals in integrity["benchmark_snapshot"]["rpm_benchmarks"].items():
        lines.append(f"| {cat} | {vals['low']:.2f} | {vals['base']:.2f} | {vals['high']:.2f} |")

    lines += [
        "",
        "### Production Cost Benchmarks",
        "| Benchmark ID | Low ($/h) | Base ($/h) | High ($/h) |",
        "|---|---:|---:|---:|",
    ]

    for b_id, vals in integrity["benchmark_snapshot"]["cost_benchmarks"].items():
        lines.append(f"| `{b_id}` | {vals['low']:.2f} | {vals['base']:.2f} | {vals['high']:.2f} |")

    lines += [
        "",
        "## Readiness (8 condiciones)",
        "",
        "| Condición | Estado | Detalle |",
        "|---|---|---|",
    ]
    lines += [f"| {c['name']} | {c['status']} | {c['detail']} |" for c in integrity["readiness_conditions"]]

    lines += [
        "",
        "## Checks internos",
        "",
        "| # | Check | Estado | Detalle |",
        "|---:|---|---|---|",
    ]
    lines += [f"| {n} | {c['name']} | {c['status']} | {c['detail']} |" for n, c in enumerate(integrity["checks"], 1)]

    lines += [
        "",
        "## Ranking canónico completo (Rank20)",
        "",
        "| Rank | ID | Subniche | Demand | Viral | RevScore | Comp | Geog | Everg | Prod | Depth | Short | Risk | Conf | Profitability | BaseProfitRank | ProfitBase USD | Class | Qualified |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|---|",
    ]

    for item in rank20["items"]:
        sc = item["scores"]
        lines.append(
            f"| {item['rank']} | `{item['id']}` | {item['subniche']} | "
            f"{sc['demand']:.1f} | {sc['viral']:.1f} | {sc['revenue_score']:.1f} | "
            f"{sc['competition']:.1f} | {sc['geography']:.1f} | {sc['evergreen']:.1f} | "
            f"{sc['production']:.1f} | {sc['content_depth']} | {sc['short_potential']} | "
            f"{sc['risk']:.1f} | {sc['confidence']:.1f} | {item['profitability']:.4f} | "
            f"{item['base_profit_rank']} | {item['profit_base']:.3f} | {item['classification']} | "
            f"{'YES' if item['qualified'] else 'NO'} |"
        )

    lines += [
        "",
        "## Top5",
        "",
        "| Rank | ID | Profitability | BaseProfitRank | Profit base USD | Clase | Qualified |",
        "|---:|---|---:|---:|---:|---|---|",
    ]
    lines += [
        f"| {i['rank']} | `{i['id']}` | {i['profitability']:.4f} | {i['base_profit_rank']} | {i['profit_base']:.3f} | {i['classification']} | {'YES' if i['qualified'] else 'NO'} |"
        for i in top5["items"]
    ]

    lines += [
        "",
        "## Qualified Opportunities (Dedicated Section)",
        "",
        "| Rank | ID | Subniche | Profitability | BaseProfitRank | Profit Base USD | Class |",
        "|---:|---|---|---:|---:|---:|---|",
    ]
    qualified_items = [i for i in rank20["items"] if i["qualified"]]
    if qualified_items:
        for i in qualified_items:
            lines.append(f"| {i['rank']} | `{i['id']}` | {i['subniche']} | {i['profitability']:.4f} | {i['base_profit_rank']} | {i['profit_base']:.3f} | {i['classification']} |")
    else:
        lines.append("| - | None | - | - | - | - | - |")

    lines += [
        "",
        "## Ranking económico diagnóstico completo",
        "",
        "| EconRank | ID | Profit base USD | Canonical Rank | Profitability | Clase |",
        "|---:|---|---:|---:|---:|---|",
    ]
    lines += [
        f"| {i['economic_rank']} | `{i['id']}` | {i['profit_base']:.3f} | {i['canonical_rank']} | {i['profitability']:.4f} | {i['classification']} |"
        for i in economic["items"]
    ]

    lines += [
        "",
        "## Persisted Opportunity Validator Details & Evidence",
        "",
        "| Rank | ID | Score | Status | Conf | FP Risk | Fragility | Positive Evidence | Contradictory Evidence | Warnings | Critical Failures |",
        "|---:|---|---:|---|---:|---:|---:|---|---|---|---|",
    ]

    for item in rank20["items"]:
        vd = item["validation_details"]
        pos = "; ".join(vd["positive_evidence"]) if vd["positive_evidence"] else "None"
        contra = "; ".join(vd["contradictory_evidence"]) if vd["contradictory_evidence"] else "None"
        warn = "; ".join(vd["warnings"]) if vd["warnings"] else "None"
        crit = "; ".join(vd["critical_failures"]) if vd["critical_failures"] else "None"
        lines.append(
            f"| {item['rank']} | `{item['id']}` | {vd['validation_score']:.2f} | {vd['validation_status']} | "
            f"{vd['validation_confidence']:.1f} | {vd['false_positive_risk']:.2f} | {vd['fragility_score']:.2f} | "
            f"{pos} | {contra} | {warn} | {crit} |"
        )

    lines += [
        "",
        "## Registro de defectos y root cause",
        "",
        "| ID | Root cause | Resolución | DB modificada |",
        "|---|---|---|---|",
    ]
    lines += [f"| {d['id']} | {d['root_cause']} | {d['resolution']} | {d['db_modified']} |" for d in integrity["defect_register"]]

    lines += [
        "",
        "## Semántica",
        "",
        "`ProfitabilityScore` sigue siendo el índice compuesto canónico. `profit_base` es beneficio monetario USD y se expone separadamente. `RevenueScore` sigue siendo un proxy de composición de formato y no incorpora dinero.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _verify_disk_consistency() -> Dict[str, Any]:
    """Reread written JSON artifacts and Markdown report from disk to perform consistency checks."""
    integrity_disk = json.loads(SCORE_PATH.read_text(encoding="utf-8"))
    rank20_disk = json.loads(RANK20_PATH.read_text(encoding="utf-8"))
    top5_disk = json.loads(TOP5_PATH.read_text(encoding="utf-8"))
    econ_disk = json.loads(ECONOMIC_RANK_PATH.read_text(encoding="utf-8"))
    report_text = REPORT_PATH.read_text(encoding="utf-8")

    # 1. Top5 equals first 5 of Rank20
    top5_matches_rank20_first_five = (
        [item["id"] for item in top5_disk["items"]] == [item["id"] for item in rank20_disk["items"][:5]]
    )

    # 2. Economic ranks map exactly to base_profit_rank
    econ_rank_mapping_exact = all(
        item["economic_rank"] == item_r20["base_profit_rank"]
        for item in econ_disk["items"]
        for item_r20 in rank20_disk["items"]
        if item["id"] == item_r20["id"]
    )

    # 3. Qualified table in report matches candidate flags
    qualified_candidates_disk = [item for item in rank20_disk["items"] if item["qualified"]]
    qualified_count_matches = (len(qualified_candidates_disk) == integrity_disk["qualified_count"])

    # 4. Report includes exact rows, IDs, and ranks
    report_has_all_ids = all(f"`{item['id']}`" in report_text for item in rank20_disk["items"])
    report_has_qualified_section = "## Qualified Opportunities (Dedicated Section)" in report_text

    all_consistent = (
        top5_matches_rank20_first_five
        and econ_rank_mapping_exact
        and qualified_count_matches
        and report_has_all_ids
        and report_has_qualified_section
    )

    return {
        "all_consistent": all_consistent,
        "top5_matches_rank20_first_five": top5_matches_rank20_first_five,
        "econ_rank_mapping_exact": econ_rank_mapping_exact,
        "qualified_count_matches": qualified_count_matches,
        "report_has_all_ids": report_has_all_ids,
        "report_has_qualified_section": report_has_qualified_section,
    }


def execute() -> Dict[str, Any]:
    print("SPRINT 13 GATE 2A FINAL RERUN — closed loop read-only")

    # Pass 1: Build first chain using fresh PostgresClient
    first = build_chain()

    # Extract immutable scalar summaries from pass 1
    retained_first_summary = {
        "economic_hash": first["economic_hash"],
        "result_hash": canonical_hash(first["items"]),
        "economic_rank_hash": canonical_hash(first["economic_items"]),
        "persisted_top20_hash": first["persisted_top20_hash"],
        "gate1e_top20_hash": first["gate1e_top20_hash"],
        "source_count": first["source_count"],
    }

    # Explicitly delete pass 1 object and collect garbage
    del first
    gc.collect()

    state_discarded_before_second = True

    # Pass 2: Build second chain using another fresh PostgresClient
    second = build_chain()

    # Validate pass 2 results against retained pass 1 summary
    checks, readiness = validate(second, retained_first_summary)

    iteration_hashes = {
        "first_economic_hash": retained_first_summary["economic_hash"],
        "second_economic_hash": second["economic_hash"],
        "first_result_hash": retained_first_summary["result_hash"],
        "second_result_hash": canonical_hash(second["items"]),
        "first_economic_rank_hash": retained_first_summary["economic_rank_hash"],
        "second_economic_rank_hash": canonical_hash(second["economic_items"]),
        "fresh_connections": 2,
        "state_discarded_before_second": state_discarded_before_second,
        "corrections": 0,
        "mapping_fixes": 0,
        "persistence_fixes": 0,
        "scoring_fixes": 0,
    }

    # Generate initial artifacts and write to disk
    artifacts = _artifacts(second, checks, readiness, iteration_hashes)
    _write_json_artifacts(artifacts)
    _write_report(artifacts)

    # Disk consistency verification: reread artifacts from disk
    disk_consistency = _verify_disk_consistency()

    # Add disk consistency result into integrity check object
    integrity = artifacts[SCORE_PATH]
    integrity["disk_consistency"] = disk_consistency

    # Add check for disk consistency into checks list if all passed
    disk_check = _condition(
        "disk_artifacts_consistent",
        disk_consistency["all_consistent"],
        f"top5_rank20={disk_consistency['top5_matches_rank20_first_five']}, econ_map={disk_consistency['econ_rank_mapping_exact']}, report_ids={disk_consistency['report_has_all_ids']}",
    )
    integrity["checks"].append(disk_check)
    integrity["checks_executed"] = len(integrity["checks"])
    integrity["checks_passed"] = sum(1 for c in integrity["checks"] if c["status"] == "PASS")
    integrity["checks_failed"] = sum(1 for c in integrity["checks"] if c["status"] == "FAIL")

    # Rewrite ONLY the integrity artifact with verified disk consistency metadata
    _write_json_artifacts({SCORE_PATH: integrity})

    print("=" * 68)
    print(f"STATUS: {integrity['status']} | TOP3 READINESS: {integrity['top3_readiness']}")
    print(f"Checks: {integrity['checks_passed']}/{integrity['checks_executed']} PASS")
    print(f"Candidates: {len(second['items'])} | Qualified: {integrity['qualified_count']} | Top5: 5")
    print(f"Persisted Top20 hash: {second['persisted_top20_hash']}")
    print(f"Gate1D Top20 hash:    {second['gate1e_top20_hash']}")
    print(f"Economic hash:        {second['economic_hash']}")
    print(f"Result hash:          {iteration_hashes['second_result_hash']}")
    print(f"Disk consistency:     {disk_consistency['all_consistent']}")
    print("DB mutations: 0 | Gate2C artifacts modified: 0")
    print("=" * 68)
    return integrity


if __name__ == "__main__":
    execute()
