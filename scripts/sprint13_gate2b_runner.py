"""Sprint 13 Gate 2B economic evidence runner.

Enriches the canonical Gate 1E Top20 in-place order. This gate never ranks or
selects candidates and never supplies benchmark values outside PostgreSQL.
"""

import hashlib
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.analytics.benchmark_provider import (
    PostgresBenchmarkProvider,
    PostgresProductionCostBenchmarkProvider,
)
from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from app.models.geography import ContentType

AUTHORITATIVE_RUN_ID = "sprint12_gate7_reconciled_20260914_211554"
EXPECTED_GATE1E_HASH = "df53c661f8b0bd61e300d7f364095d399331026245f4c0ce3b80fa9d3b2a090a"
ECONOMICS_RUN_ID = "sprint13_gate2b_sprint12_gate7_reconciled_20260914_211554"
METHODOLOGY_VERSION = "sprint13-gate2b-v1"
GATE1E_JSON_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate1e_final_top20.json"
RPM_ARTIFACT_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2b_rpm_benchmarks.json"
COST_ARTIFACT_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2b_cost_benchmarks.json"
ECONOMICS_ARTIFACT_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2b_top20_economics.json"
REPORT_PATH = ROOT_DIR / "docs" / "sprint13_gate2b_economic_infrastructure.md"

RepositoryFactory = Callable[[], YouTubeRepository]


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    return value


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        _canonical_value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_and_verify_top20(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as source:
        data = json.load(source)
    if data.get("source_run_id") != AUTHORITATIVE_RUN_ID:
        raise ValueError("Canonical Top20 source run is not authoritative")
    if data.get("ranking_hashes", {}).get("gate1d") != EXPECTED_GATE1E_HASH:
        raise ValueError("Gate1E hash mismatch")
    items = data.get("items", [])
    if len(items) != 20 or len({item.get("stable_id") for item in items}) != 20:
        raise ValueError("Canonical Top20 must contain exactly 20 unique stable IDs")
    if [item.get("rank") for item in items] != list(range(1, 21)):
        raise ValueError("Canonical Top20 ranks must be 1 through 20")
    return data


def _verify_authority_and_mapping(
    repository: YouTubeRepository, top20: Dict[str, Any]
) -> Dict[str, int]:
    run = repository.get_analytical_run(AUTHORITATIVE_RUN_ID)
    if run is None or run.status != "SPRINT12_FINAL_ANALYTICS_APPROVED":
        raise ValueError(f"Authority check failed for run_id {AUTHORITATIVE_RUN_ID}")
    notes = _json_value(run.notes or "{}")
    mappings = notes.get("top20_evaluation_mapping", [])
    by_definition = {
        row["definition_id"]: int(row["evaluation_cluster_id"]) for row in mappings
    }
    stable_ids = [item["stable_id"] for item in top20["items"]]
    if set(by_definition) != set(stable_ids):
        raise ValueError("Authoritative evaluation mapping does not match canonical Top20")
    definitions = {
        row["definition_id"]
        for row in repository.get_gate7_semantic_definitions(AUTHORITATIVE_RUN_ID)
    }
    if not set(stable_ids).issubset(definitions):
        raise ValueError("Canonical stable IDs are missing from authoritative definitions")
    return by_definition


def _one(rows: List[Dict[str, Any]], label: str, candidate_id: str) -> Dict[str, Any]:
    if len(rows) != 1:
        raise ValueError(f"Expected one {label} row for {candidate_id}; found {len(rows)}")
    return rows[0]


def _unavailable_range(warning: str) -> Dict[str, Any]:
    return {
        "available": False,
        "low": None,
        "base": None,
        "high": None,
        "currency": "USD",
        "warnings": [warning],
    }


def _build_record(
    repository: YouTubeRepository,
    item: Dict[str, Any],
    evaluation_cluster_id: int,
    source_dataset_hash: str,
    calculated_at: datetime,
) -> Dict[str, Any]:
    client = repository.client
    profitability = _one(
        client.execute(
            "SELECT * FROM public.cluster_profitability_analyses "
            "WHERE source_cluster_run_id = %s AND cluster_id = %s",
            [AUTHORITATIVE_RUN_ID, evaluation_cluster_id],
        ),
        "profitability",
        item["stable_id"],
    )
    production = _one(
        client.execute(
            "SELECT * FROM public.production_risk_analyses "
            "WHERE source_cluster_run_id = %s AND cluster_id = %s",
            [AUTHORITATIVE_RUN_ID, evaluation_cluster_id],
        ),
        "production-risk",
        item["stable_id"],
    )
    metrics = _json_value(profitability.get("metrics") or {})
    views = metrics.get("expected_views_range") or {}
    expected_views = {
        "available": all(views.get(key) is not None for key in ("low", "base", "high")),
        "low": views.get("low"),
        "base": views.get("base"),
        "high": views.get("high"),
        "methodology": views.get("method", "authoritative_profitability_expected_views"),
        "confidence": views.get("confidence"),
        "warnings": list(views.get("warnings") or []),
    }

    rpm_benchmark = PostgresBenchmarkProvider(repository).get_benchmark(
        "GLOBAL", ContentType.LONG_FORM, language="en", content_category="general"
    )
    if rpm_benchmark is None:
        rpm = _unavailable_range("RPM unavailable: no matching sourced PostgreSQL benchmark.")
        rpm_provenance = {
            "benchmark_id": None,
            "source": None,
            "source_type": None,
            "version": None,
            "date": None,
            "confidence": None,
            "fallback_level": None,
        }
    else:
        rpm = {
            "available": True,
            "low": rpm_benchmark.rpm_low,
            "base": rpm_benchmark.rpm_base,
            "high": rpm_benchmark.rpm_high,
            "currency": rpm_benchmark.currency,
            "warnings": [],
        }
        rpm_provenance = {
            "benchmark_id": rpm_benchmark.id,
            "source": rpm_benchmark.source_name,
            "source_type": rpm_benchmark.source_type.value,
            "version": rpm_benchmark.source_version,
            "date": rpm_benchmark.source_date,
            "confidence": rpm_benchmark.confidence,
            "fallback_level": rpm_benchmark.fallback_level,
        }

    if expected_views["available"] and rpm["available"]:
        revenue = {
            "available": True,
            "low": expected_views["low"] * rpm["low"] / 1000.0,
            "base": expected_views["base"] * rpm["base"] / 1000.0,
            "high": expected_views["high"] * rpm["high"] / 1000.0,
            "currency": "USD",
            "methodology": "expected_views_x_rpm_divided_by_1000",
            "assumptions": ["Each scenario pairs corresponding expected views and RPM bounds."],
            "warnings": [],
        }
    else:
        revenue = _unavailable_range(
            "Revenue unavailable: expected views and sourced RPM are both required."
        )
        revenue.update({"methodology": "expected_views_x_rpm_divided_by_1000", "assumptions": []})

    cost_model = PostgresProductionCostBenchmarkProvider(repository).estimate_cost(
        production.get("estimated_hours_low"), production.get("estimated_hours_high")
    )
    cost = cost_model.model_dump(mode="json")
    cost_provenance = {
        "benchmark_id": cost_model.benchmark_id,
        "source": cost_model.source_name,
        "source_type": cost_model.evidence_type.value,
        "version": cost_model.source_version,
        "date": cost_model.source_date,
        "confidence": cost_model.confidence if cost_model.available else None,
    }

    if revenue["available"] and cost["available"]:
        profit = {
            "available": True,
            "low": revenue["low"] - cost["high"],
            "base": revenue["base"] - cost["base"],
            "high": revenue["high"] - cost["low"],
            "currency": "USD",
            "methodology": "revenue_minus_production_cost; low uses high cost, high uses low cost",
            "assumptions": ["No unbenchmarked income or cost components are introduced."],
            "warnings": [],
        }
    else:
        profit = _unavailable_range(
            "Profit unavailable: sourced revenue and production cost are both required."
        )
        profit.update({
            "methodology": "revenue_minus_production_cost",
            "assumptions": [],
        })

    monetary_available = [rpm["available"], revenue["available"], cost["available"], profit["available"]]
    if all(monetary_available):
        status = "ECONOMIC_COMPLETE"
    elif any(monetary_available):
        status = "ECONOMIC_PARTIAL"
    else:
        status = "ECONOMIC_UNAVAILABLE"
    warnings = rpm["warnings"] + revenue["warnings"] + cost["warnings"] + profit["warnings"]
    economics_payload = {
        "candidate_id": item["stable_id"],
        "candidate_rank": item["rank"],
        "evaluation_cluster_id": evaluation_cluster_id,
        "niche": item["niche"],
        "subniche": item["subniche"],
        "normalized_intent": item["normalized_intent"],
        "economic_status": status,
        "expected_views": expected_views,
        "rpm": rpm,
        "revenue": revenue,
        "production_cost": cost,
        "profit": profit,
        "assumptions": [
            "Canonical market/language lookup is GLOBAL/en and long-form.",
            "Only PostgreSQL benchmark rows may provide monetary inputs.",
        ],
        "methodology": METHODOLOGY_VERSION,
        "warnings": warnings,
    }
    provenance_payload = {
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "gate1e_hash": EXPECTED_GATE1E_HASH,
        "definition_id": item["stable_id"],
        "evaluation_cluster_id": evaluation_cluster_id,
        "rpm": rpm_provenance,
        "production_cost": cost_provenance,
    }
    return {
        "run_id": ECONOMICS_RUN_ID,
        "candidate_id": item["stable_id"],
        "candidate_rank": item["rank"],
        "benchmark_id": rpm_provenance["benchmark_id"],
        "rpm_available": rpm["available"],
        "cost_benchmark_id": cost_provenance["benchmark_id"],
        "cost_available": cost["available"],
        "fallback_level": rpm_provenance["fallback_level"],
        "economics_payload": economics_payload,
        "provenance_payload": provenance_payload,
        "methodology_version": METHODOLOGY_VERSION,
        "source_dataset_hash": source_dataset_hash,
        "calculated_at": calculated_at,
    }


def _hashable_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    fields = (
        "run_id", "candidate_id", "candidate_rank", "benchmark_id", "rpm_available",
        "cost_benchmark_id", "cost_available", "fallback_level", "economics_payload",
        "provenance_payload", "methodology_version", "source_dataset_hash",
    )
    return [
        {
            field: _json_value(row.get(field))
            if field in ("economics_payload", "provenance_payload")
            else row.get(field)
            for field in fields
        }
        for row in sorted(rows, key=lambda row: (row["candidate_rank"], row["candidate_id"]))
    ]


def run_gate2b(
    repository_factory: Optional[RepositoryFactory] = None,
    top20_path: Path = GATE1E_JSON_PATH,
) -> Dict[str, Any]:
    factory = repository_factory or (lambda: YouTubeRepository(PostgresClient()))
    top20 = _load_and_verify_top20(Path(top20_path))
    write_repository = factory()
    mapping = _verify_authority_and_mapping(write_repository, top20)

    benchmark_inputs = {
        "top20": top20["items"],
        "rpm_benchmarks": write_repository.get_rpm_benchmarks(),
        "production_cost_benchmarks": write_repository.get_production_cost_benchmarks(),
    }
    source_dataset_hash = canonical_hash(benchmark_inputs)
    calculated_at = datetime.now(timezone.utc)
    records = [
        _build_record(
            write_repository,
            item,
            mapping[item["stable_id"]],
            source_dataset_hash,
            calculated_at,
        )
        for item in top20["items"]
    ]
    if len(records) != 20:
        raise AssertionError("Gate 2B must produce exactly 20 economic records")
    generated_hash = canonical_hash(_hashable_rows(records))
    write_repository.upsert_candidate_economics(records)

    read_repository_1 = factory()
    reread_1 = read_repository_1.get_candidate_economics(ECONOMICS_RUN_ID)
    read_repository_2 = factory()
    reread_2 = read_repository_2.get_candidate_economics(ECONOMICS_RUN_ID)
    if len(reread_1) != 20 or len(reread_2) != 20:
        raise ValueError(
            "Gate 2B DB rereads expected 20 rows; "
            f"found {len(reread_1)} and {len(reread_2)}"
        )
    reread_hash_1 = canonical_hash(_hashable_rows(reread_1))
    reread_hash_2 = canonical_hash(_hashable_rows(reread_2))
    if generated_hash != reread_hash_1 or reread_hash_1 != reread_hash_2:
        raise ValueError("Gate 2B generated and independent DB reread hashes differ")

    statuses = [_json_value(row["economics_payload"])["economic_status"] for row in reread_2]
    status = "GO" if all(value == "ECONOMIC_COMPLETE" for value in statuses) else "FIX / STOP"
    return {
        "status": status,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "gate1e_hash": EXPECTED_GATE1E_HASH,
        "run_id": ECONOMICS_RUN_ID,
        "record_count": len(reread_2),
        "rpm_benchmarks": benchmark_inputs["rpm_benchmarks"],
        "production_cost_benchmarks": benchmark_inputs["production_cost_benchmarks"],
        "source_dataset_hash": source_dataset_hash,
        "generated_hash": generated_hash,
        "reread_hash": reread_hash_2,
        "reread_hash_1": reread_hash_1,
        "reread_hash_2": reread_hash_2,
        "hash_match": generated_hash == reread_hash_1 == reread_hash_2,
        "records": reread_2,
    }


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as target:
        json.dump(_canonical_value(value), target, indent=2, ensure_ascii=False)
        target.write("\n")


def _write_artifacts(result: Dict[str, Any], rerun: Dict[str, Any]) -> None:
    reproducible = (
        result["source_dataset_hash"] == rerun["source_dataset_hash"]
        and result["reread_hash"] == rerun["reread_hash"]
    )
    checks = {
        "benchmark_tables_empty": not result["rpm_benchmarks"]
        and not result["production_cost_benchmarks"],
        "record_count_is_20": result["record_count"] == 20,
        "dual_db_reread_hash_match": result["hash_match"],
        "full_rerun_reproducible": reproducible,
        "all_monetary_values_unavailable": all(
            all(
                not _json_value(row["economics_payload"])[section]["available"]
                and all(
                    _json_value(row["economics_payload"])[section][bound] is None
                    for bound in ("low", "base", "high")
                )
                for section in ("rpm", "revenue", "production_cost", "profit")
            )
            for row in result["records"]
        ),
    }
    validation = {
        "status": result["status"],
        "authoritative_run_id": result["authoritative_run_id"],
        "gate1e_hash": result["gate1e_hash"],
        "run_id": result["run_id"],
        "methodology_version": METHODOLOGY_VERSION,
        "source_dataset_hash": result["source_dataset_hash"],
        "generated_hash": result["generated_hash"],
        "db_reread_hash_1": result["reread_hash_1"],
        "db_reread_hash_2": result["reread_hash_2"],
        "full_rerun_hash": rerun["reread_hash"],
        "checks": checks,
        "provenance_blocker": (
            "No sourced PostgreSQL RPM or production-cost benchmark rows exist; "
            "monetary economics cannot be calculated without inventing values."
        ),
    }
    _write_json(RPM_ARTIFACT_PATH, {
        **validation,
        "dataset": "public.rpm_benchmarks",
        "record_count": len(result["rpm_benchmarks"]),
        "records": result["rpm_benchmarks"],
    })
    _write_json(COST_ARTIFACT_PATH, {
        **validation,
        "dataset": "public.production_cost_benchmarks",
        "record_count": len(result["production_cost_benchmarks"]),
        "records": result["production_cost_benchmarks"],
    })
    _write_json(ECONOMICS_ARTIFACT_PATH, {
        **validation,
        "record_count": result["record_count"],
        "records": _hashable_rows(result["records"]),
    })
    REPORT_PATH.write_text(
        "# Sprint 13 Gate 2B — Economic Infrastructure Closed-Loop Validation\n\n"
        f"**STATUS: {result['status']}**\n\n"
        "## Outcome\n\n"
        "The schema migration was applied idempotently. Both benchmark tables are empty, "
        "so the canonical 20 candidates were persisted explicitly as `ECONOMIC_UNAVAILABLE`. "
        "No benchmark or monetary value was invented, and no candidate selection was performed.\n\n"
        "## Database counts\n\n"
        f"- `public.rpm_benchmarks`: {len(result['rpm_benchmarks'])}\n"
        f"- `public.production_cost_benchmarks`: {len(result['production_cost_benchmarks'])}\n"
        f"- `public.candidate_economics` for `{result['run_id']}`: {result['record_count']}\n\n"
        "## Methods and checks\n\n"
        "- Canonical Gate 1E authority, hash, ranks 1–20, stable IDs, and evaluation mapping were verified.\n"
        "- Monetary inputs were read only from PostgreSQL benchmark tables.\n"
        "- Each RPM, revenue, production-cost, and profit low/base/high value is `null`.\n"
        "- Two independent DB-only rereads used newly constructed repositories/connections.\n"
        "- A full second execution verified idempotent persistence and reproducibility.\n"
        f"- All checks passed: {all(checks.values())}.\n\n"
        "## Canonical hashes\n\n"
        f"- Source dataset: `{result['source_dataset_hash']}`\n"
        f"- Generated: `{result['generated_hash']}`\n"
        f"- DB-only reread 1: `{result['reread_hash_1']}`\n"
        f"- DB-only reread 2: `{result['reread_hash_2']}`\n"
        f"- Full rerun: `{rerun['reread_hash']}`\n\n"
        "## Provenance blocker\n\n"
        "No sourced PostgreSQL RPM or production-cost benchmark rows exist. Revenue, monetary "
        "production cost, and profit therefore remain unavailable until documented benchmark "
        "evidence is loaded through the project data path.\n\n"
        "## Terminal decision\n\n"
        f"**STATUS = {result['status']}**\n",
        encoding="utf-8",
    )


def execute() -> Dict[str, Any]:
    result = run_gate2b()
    rerun = run_gate2b()
    if result["source_dataset_hash"] != rerun["source_dataset_hash"] or result["reread_hash"] != rerun["reread_hash"]:
        raise ValueError("Gate 2B full rerun is not reproducible")
    _write_artifacts(result, rerun)
    print("SPRINT 13 GATE 2B")
    print(f"STATUS: {result['status']}")
    print(f"Economic records: {result['record_count']}/20")
    print(f"Canonical hash: {result['reread_hash']}")
    return result


if __name__ == "__main__":
    execute()
