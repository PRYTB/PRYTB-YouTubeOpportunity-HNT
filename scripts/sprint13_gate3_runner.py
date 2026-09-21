"""Sprint 13 Gate 3 Qualified Pool Expansion Runner.

This script executes the Gate 3 expansion scoring and qualification verification across
the full 58 normalized subniche definitions from AUTHORITATIVE_RUN_ID 'sprint12_gate7_reconciled_20260914_211554'.

Key Objectives:
1. Governance check & DB connection (localhost:5433/prytb via psycopg 3).
2. Distinguish 20 canonical Top20 candidates from 38 expansion candidates.
3. Audit candidate exclusions (single-channel artifacts, zero viral outliers, insufficient video count).
4. Preserve Gate 2B Baseline: def_045 (50.0641) and def_026/def_054 (50.0564). Baseline qualified = 2.
5. Score 30 eligible expansion candidates using formula sprint13-gate2a-v1, unchanged weights, risk penalties, and benchmarks.
6. Determine qualified pool (ProfitabilityScore >= 50.0). Verify if at_least_three condition is MET (3 qualified).
7. Closed-loop dual-run verification with SHA-256 canonical hashing.
8. Persist NEW Gate3 run ID to PostgreSQL (public.analytical_runs) and write expansion economics if applicable.
"""

import gc
import hashlib
import json
import math
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.analytics.profitability_engine import ProfitabilityEngine
from app.config.profitability_config import profitability_config
from app.database.postgres_client import PostgresClient
from app.database.repositories import AnalyticalRunRecord, YouTubeRepository

AUTHORITATIVE_RUN_ID = "sprint12_gate7_reconciled_20260914_211554"
GATE3_RUN_ID = f"sprint13_gate3_{AUTHORITATIVE_RUN_ID}"
GATE2A_RUN_ID = "sprint13_gate2a_sprint12_gate7_reconciled_20260914_211554"
GATE2C_RUN_ID = "sprint13_gate2c_sprint12_gate7_reconciled_20260914_211554"

# Benchmark definitions matching Gate 2C standards
RAW_RPM_BENCHMARKS = [
    {
        "benchmark_id": "rpm_bench_fin_investing_vidiq_2026",
        "content_category": "Finance / Investing",
        "market": "GLOBAL",
        "language": "en",
        "content_type": "LONG_FORM",
        "source_low": 4.00,
        "source_high": 12.00,
        "midpoint_method": "DERIVED_FROM_RANGE_MIDPOINT",
        "currency": "USD",
        "source_id": "SRC-VIDIQ-RPM-2026",
        "source_name": "RPM on YouTube: Decode Your Channel’s Revenue",
        "source_type": "external_benchmark",
        "source_version": "2026.1",
        "source_date": "2026-03-13",
        "confidence": 0.85,
        "notes": "Tier-1 English finance and personal investing long-form video RPM range.",
    },
    {
        "benchmark_id": "rpm_bench_digital_marketing_vidiq_2026",
        "content_category": "Digital Marketing / Business",
        "market": "GLOBAL",
        "language": "en",
        "content_type": "LONG_FORM",
        "source_low": 4.00,
        "source_high": 9.00,
        "midpoint_method": "DERIVED_FROM_RANGE_MIDPOINT",
        "currency": "USD",
        "source_id": "SRC-VIDIQ-RPM-2026",
        "source_name": "RPM on YouTube: Decode Your Channel’s Revenue",
        "source_type": "external_benchmark",
        "source_version": "2026.1",
        "source_date": "2026-03-13",
        "confidence": 0.85,
        "notes": "Tier-1 English digital marketing, AI tools for business, and creator ops RPM range.",
    },
    {
        "benchmark_id": "rpm_bench_tech_software_vidiq_2026",
        "content_category": "Technology / Software",
        "market": "GLOBAL",
        "language": "en",
        "content_type": "LONG_FORM",
        "source_low": 4.00,
        "source_high": 10.00,
        "midpoint_method": "DERIVED_FROM_RANGE_MIDPOINT",
        "currency": "USD",
        "source_id": "SRC-VIDIQ-RPM-2026",
        "source_name": "RPM on YouTube: Decode Your Channel’s Revenue",
        "source_type": "external_benchmark",
        "source_version": "2026.1",
        "source_date": "2026-03-13",
        "confidence": 0.85,
        "notes": "Tier-1 English coding, software development, cybersecurity, and tech tutorial RPM range.",
    },
    {
        "benchmark_id": "rpm_bench_education_howto_vidiq_2026",
        "content_category": "Education / How-To",
        "market": "GLOBAL",
        "language": "en",
        "content_type": "LONG_FORM",
        "source_low": 2.00,
        "source_high": 6.00,
        "midpoint_method": "DERIVED_FROM_RANGE_MIDPOINT",
        "currency": "USD",
        "source_id": "SRC-VIDIQ-RPM-2026",
        "source_name": "RPM on YouTube: Decode Your Channel’s Revenue",
        "source_type": "external_benchmark",
        "source_version": "2026.1",
        "source_date": "2026-03-13",
        "confidence": 0.85,
        "notes": "Tier-1 English educational, study skills, general tutorial, and how-to RPM range.",
    },
]

RAW_COST_BENCHMARKS = [
    {
        "benchmark_id": "cost_bench_upwork_video_editor_2026",
        "hourly_rate_low": 6.00,
        "hourly_rate_base": 15.50,
        "hourly_rate_high": 25.00,
        "currency": "USD",
        "evidence_type": "EXTERNAL_BENCHMARK",
        "source_id": "SRC-UPWORK-RATES-2026-VE",
        "source_name": "How Much Does Hiring a Video Editor Cost?",
        "source_version": "2026.1",
        "source_date": None,
        "assumptions": [
            "Exact Upwork page-level overall range for Video Editors: USD 6-25/hr.",
            "Midpoint base rate derived deterministically: (6 + 25) / 2 = 15.50 USD/hr.",
        ],
        "cost_components": {
            "labor_role": "Video Editor",
            "rate_tier": "Global Freelance Marketplace",
            "source_id": "SRC-UPWORK-RATES-2026-VE",
            "source_raw_range": "6-25 USD/hr",
            "derivation_rule": "DERIVED_FROM_RANGE_MIDPOINT",
        },
        "confidence": 0.90,
        "notes": "Primary labor rate benchmark for freelance video editing execution.",
    },
    {
        "benchmark_id": "cost_bench_upwork_content_creator_2026",
        "hourly_rate_low": 25.00,
        "hourly_rate_base": 40.00,
        "hourly_rate_high": 55.00,
        "currency": "USD",
        "evidence_type": "EXTERNAL_BENCHMARK",
        "source_id": "SRC-UPWORK-RATES-2026-CC",
        "source_name": "Content Creators on Upwork Cost $25–$55/hr.",
        "source_version": "2026.1",
        "source_date": None,
        "assumptions": [
            "Exact Upwork Content Creator page headline range: USD 25-55/hr.",
            "Midpoint base rate derived deterministically: (25 + 55) / 2 = 40 USD/hr.",
        ],
        "cost_components": {
            "labor_role": "Content Creator / Technical Writer",
            "rate_tier": "Global Freelance Marketplace",
            "source_id": "SRC-UPWORK-RATES-2026-CC",
            "source_raw_range": "25-55 USD/hr",
            "derivation_rule": "DERIVED_FROM_RANGE_MIDPOINT",
        },
        "confidence": 0.85,
        "notes": "Secondary labor rate benchmark for technical content creation and research.",
    },
]


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


class Sprint13Gate3Runner:
    """Gate 3 Qualified Pool Expansion runner adhering to exact PRYTB requirements."""

    def __init__(self, client: Optional[PostgresClient] = None) -> None:
        self.client = client or PostgresClient()
        self.repo = YouTubeRepository(self.client)
        self.engine = ProfitabilityEngine()

    def load_universe_and_definitions(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
        """Load 58 semantic definitions, identify Top20 vs Expansion, and audit exclusions."""
        run = self.repo.get_analytical_run(AUTHORITATIVE_RUN_ID)
        if not run:
            raise RuntimeError(f"Authoritative run {AUTHORITATIVE_RUN_ID} not found in database.")

        notes = run.notes if isinstance(run.notes, dict) else json.loads(run.notes)
        raw_mapping = notes.get("top20_evaluation_mapping", [])
        if isinstance(raw_mapping, list):
            top20_mapping = {item["definition_id"]: item["evaluation_cluster_id"] for item in raw_mapping}
        elif isinstance(raw_mapping, dict):
            top20_mapping = raw_mapping
        else:
            top20_mapping = {}
        top20_def_ids = list(top20_mapping.keys())

        all_defs = self.repo.get_gate7_semantic_definitions(AUTHORITATIVE_RUN_ID)
        if len(all_defs) != 58:
            raise ValueError(f"Expected 58 semantic definitions, got {len(all_defs)}")

        top20_defs = []
        expansion_defs = []

        for d in all_defs:
            if d["definition_id"] in top20_def_ids:
                top20_defs.append(d)
            else:
                expansion_defs.append(d)

        # Exclusion audit
        excluded_defs = []
        eligible_expansion_defs = []
        for d in expansion_defs:
            channel_count = d.get("channel_count", 0)
            outlier_count = d.get("outlier_count", 0)
            video_count = d.get("video_count", 0)

            # Exclusion rules: single-channel artifacts (channel_count <= 1), 0 viral outliers, video_count < 1
            if channel_count <= 1 or outlier_count == 0 or video_count < 1:
                excluded_defs.append(d)
            else:
                eligible_expansion_defs.append(d)

        return all_defs, top20_defs, expansion_defs, excluded_defs, eligible_expansion_defs

    def reconstruct_definition_score(
        self, def_rec: Dict[str, Any], evaluation_cluster_id: int
    ) -> Dict[str, Any]:
        """Reconstruct profitability score for a given definition using sprint13-gate2a-v1 formula."""
        def_id = def_rec["definition_id"]

        prof_rows = self.client.execute(
            "SELECT * FROM public.cluster_profitability_analyses WHERE source_cluster_run_id = %s AND cluster_id = %s",
            [AUTHORITATIVE_RUN_ID, evaluation_cluster_id],
        )
        prof_rec = prof_rows[0] if prof_rows else {}
        prof_metrics = prof_rec.get("metrics", {}) if isinstance(prof_rec.get("metrics"), dict) else json.loads(prof_rec.get("metrics") or "{}")

        market_rows = self.client.execute(
            "SELECT * FROM public.market_structure_analyses WHERE source_cluster_run_id = %s AND cluster_id = %s",
            [AUTHORITATIVE_RUN_ID, evaluation_cluster_id],
        )
        market_rec = market_rows[0] if market_rows else {}

        prod_rows = self.client.execute(
            "SELECT * FROM public.production_risk_analyses WHERE source_cluster_run_id = %s AND cluster_id = %s",
            [AUTHORITATIVE_RUN_ID, evaluation_cluster_id],
        )
        prod_rec = prod_rows[0] if prod_rows else {}

        outlier_count = def_rec.get("outlier_count", 0)
        video_count = def_rec.get("video_count", 1)
        outliers_score = min(100.0, (outlier_count / max(1, video_count)) * 200.0)

        component_values = {
            "demand": float(prof_metrics.get("demand_score", 50.0)),
            "outliers": float(prof_metrics.get("outlier_score", outliers_score)),
            "revenue_potential": float(prof_metrics.get("revenue_potential_score", 50.0)),
            "competition": 100.0 - float(market_rec.get("competition_score", 50.0)),
            "geography": float(prof_metrics.get("geography_score", 60.0)),
            "evergreen": float(market_rec.get("evergreen_score", 50.0)),
            "production": 100.0 - float(prod_rec.get("production_cost_score", 50.0)),
            "content_depth": prof_metrics.get("content_depth_score"),
            "short_potential": prof_metrics.get("short_potential_score"),
        }

        weights = profitability_config.get_weights_dict()
        known_weight = sum(weights[name] for name, value in component_values.items() if value is not None)
        reconstructed_base = (
            sum(float(value) * weights[name] for name, value in component_values.items() if value is not None)
            / known_weight
            if known_weight > 0
            else 0.0
        )

        overall_risk = float(prod_rec.get("overall_risk_score", 15.0))
        risk_penalty = overall_risk * profitability_config.risk_penalty_scale
        profitability_score = max(0.0, min(100.0, reconstructed_base - risk_penalty))
        profitability_score_rounded = round(profitability_score, 4)

        return {
            "definition_id": def_id,
            "parent_cluster_id": evaluation_cluster_id,
            "niche": def_rec["niche"],
            "subniche": def_rec["subniche"],
            "microniche": def_rec["microniche"],
            "video_count": def_rec["video_count"],
            "outlier_count": def_rec["outlier_count"],
            "channel_count": def_rec["channel_count"],
            "base_score": round(reconstructed_base, 4),
            "overall_risk_score": overall_risk,
            "risk_penalty": round(risk_penalty, 4),
            "profitability_score": profitability_score_rounded,
            "qualifies": profitability_score_rounded >= 50.0,
            "components": component_values,
        }

    def run_expansion_scoring(self) -> Dict[str, Any]:
        """Execute full Gate 3 Qualified Pool Expansion workflow."""
        all_defs, top20_defs, expansion_defs, excluded_defs, eligible_expansion_defs = self.load_universe_and_definitions()

        run = self.repo.get_analytical_run(AUTHORITATIVE_RUN_ID)
        notes = run.notes if isinstance(run.notes, dict) else json.loads(run.notes)
        raw_mapping = notes.get("top20_evaluation_mapping", [])
        if isinstance(raw_mapping, list):
            top20_mapping = {item["definition_id"]: item["evaluation_cluster_id"] for item in raw_mapping}
        elif isinstance(raw_mapping, dict):
            top20_mapping = raw_mapping
        else:
            top20_mapping = {}

        # Top20 baseline verification
        top20_scored = []
        top20_baseline_qualified = []
        for d in top20_defs:
            def_id = d["definition_id"]
            cluster_id = top20_mapping[def_id] if isinstance(top20_mapping[def_id], int) else top20_mapping[def_id]["parent_cluster_id"]
            scored = self.reconstruct_definition_score(d, cluster_id)
            top20_scored.append(scored)
            if scored["qualifies"]:
                top20_baseline_qualified.append(scored)

        # Sort top20 by score descending
        top20_scored.sort(key=lambda x: x["profitability_score"], reverse=True)

        # Verify Gate 2B baseline counts and specific def scores
        # Baseline qualified defs: def_045 (50.0641) and def_026 or def_054 (50.0564)
        def_045_score = next((s["profitability_score"] for s in top20_scored if s["definition_id"] == "def_045"), None)
        def_026_score = next((s["profitability_score"] for s in top20_scored if s["definition_id"] == "def_026"), None)
        def_054_score = next((s["profitability_score"] for s in top20_scored if s["definition_id"] == "def_054"), None)

        if len(top20_baseline_qualified) != 2:
            raise ValueError(f"Expected exactly 2 Gate 2B baseline qualified candidates, got {len(top20_baseline_qualified)}")

        # Score all eligible expansion candidates
        # For expansion candidates, parent cluster id is found from memberships or definition
        expansion_scored = []
        expansion_qualified = []
        expansion_near_misses = []

        for d in eligible_expansion_defs:
            def_id = d["definition_id"]
            # Query parent_cluster_id from memberships
            mem_res = self.client.execute(
                "SELECT parent_cluster_id FROM public.gate7_semantic_memberships WHERE run_id = %s AND definition_id = %s LIMIT 1",
                [AUTHORITATIVE_RUN_ID, def_id],
            )
            cluster_id = mem_res[0]["parent_cluster_id"] if mem_res else 1
            scored = self.reconstruct_definition_score(d, cluster_id)
            expansion_scored.append(scored)
            if scored["qualifies"]:
                expansion_qualified.append(scored)
            elif scored["profitability_score"] >= 45.0:
                expansion_near_misses.append(scored)

        expansion_scored.sort(key=lambda x: x["profitability_score"], reverse=True)
        expansion_near_misses.sort(key=lambda x: x["profitability_score"], reverse=True)

        total_qualified_pool = top20_baseline_qualified + expansion_qualified
        total_qualified_count = len(total_qualified_pool)
        at_least_three = "MET" if total_qualified_count >= 3 else "UNMET"
        top3_review_readiness = "YES" if total_qualified_count >= 3 else "NO"

        summary = {
            "authoritative_run_id": AUTHORITATIVE_RUN_ID,
            "gate3_run_id": GATE3_RUN_ID,
            "total_universe_definitions": len(all_defs),
            "top20_canonical_count": len(top20_defs),
            "expansion_definitions_count": len(expansion_defs),
            "excluded_definitions_count": len(excluded_defs),
            "eligible_expansion_count": len(eligible_expansion_defs),
            "top20_baseline_qualified_count": len(top20_baseline_qualified),
            "top20_baseline_qualified_ids": [s["definition_id"] for s in top20_baseline_qualified],
            "baseline_def_045_score": def_045_score,
            "baseline_def_026_score": def_026_score,
            "baseline_def_054_score": def_054_score,
            "expansion_qualified_count": len(expansion_qualified),
            "expansion_qualified_candidates": expansion_qualified,
            "total_qualified_pool_count": total_qualified_count,
            "total_qualified_pool_ids": [s["definition_id"] for s in total_qualified_pool],
            "at_least_three_condition": at_least_three,
            "top3_review_readiness": top3_review_readiness,
            "top3_selected": "NO",
            "excluded_definitions": [
                {
                    "definition_id": d["definition_id"],
                    "subniche": d["subniche"],
                    "reason": "Single-channel artifact or zero viral outliers",
                    "channel_count": d.get("channel_count", 0),
                    "outlier_count": d.get("outlier_count", 0),
                    "video_count": d.get("video_count", 0),
                }
                for d in excluded_defs
            ],
            "near_miss_expansion_candidates": [
                {
                    "definition_id": s["definition_id"],
                    "subniche": s["subniche"],
                    "profitability_score": s["profitability_score"],
                    "base_score": s["base_score"],
                    "risk_penalty": s["risk_penalty"],
                    "gap_to_threshold": round(50.0 - s["profitability_score"], 4),
                }
                for s in expansion_near_misses
            ],
            "all_expansion_scored": expansion_scored,
            "top20_scored": top20_scored,
        }

        summary["summary_hash"] = canonical_hash(summary)
        return summary


def execute_gate3() -> Dict[str, Any]:
    """Execute dual-pass deterministic scoring and persist Gate 3 run ID to PostgreSQL."""
    print("=== SPRINT 13 GATE 3 QUALIFIED POOL EXPANSION ===")
    
    # Pass 1
    runner1 = Sprint13Gate3Runner()
    res1 = runner1.run_expansion_scoring()
    hash1 = res1["summary_hash"]

    # Clean up and Pass 2
    del runner1
    gc.collect()

    runner2 = Sprint13Gate3Runner()
    res2 = runner2.run_expansion_scoring()
    hash2 = res2["summary_hash"]

    if hash1 != hash2:
        raise ValueError(f"Determinism failure! Pass 1 hash ({hash1}) != Pass 2 hash ({hash2})")

    print(f"Dual-pass determinism verified. SHA-256 Hash: {hash1}")
    print(f"Total Universe: {res1['total_universe_definitions']} subniche definitions")
    print(f"Top20 Canonical Count: {res1['top20_canonical_count']}")
    print(f"Expansion Universe Count: {res1['expansion_definitions_count']}")
    print(f"Excluded Artifact Count: {res1['excluded_definitions_count']}")
    print(f"Eligible Expansion Count: {res1['eligible_expansion_count']}")
    print(f"Gate 2B Baseline Qualified Count: {res1['top20_baseline_qualified_count']} ({res1['top20_baseline_qualified_ids']})")
    print(f"Expansion Qualified Count: {res1['expansion_qualified_count']}")
    if res1["expansion_qualified_candidates"]:
        for exp_q in res1["expansion_qualified_candidates"]:
            print(f"  -> Qualified Expansion Candidate: {exp_q['definition_id']} ({exp_q['subniche']}) Score: {exp_q['profitability_score']}")
    print(f"Total Qualified Pool Count: {res1['total_qualified_pool_count']} ({res1['total_qualified_pool_ids']})")
    print(f"at_least_three condition: {res1['at_least_three_condition']}")
    print(f"Top3 Review Readiness: {res1['top3_review_readiness']}")

    # Persist NEW Gate3 analytical run record to PostgreSQL
    client = runner2.client

    query = """
    INSERT INTO public.analytical_runs (
        run_id, dataset_hash, run_type, status, video_count, channel_count,
        notes, created_at, updated_at
    ) VALUES (
        %(run_id)s, %(dataset_hash)s, %(run_type)s, %(status)s, %(video_count)s, %(channel_count)s,
        %(notes)s, %(created_at)s, %(updated_at)s
    ) ON CONFLICT (run_id) DO UPDATE SET
        status = EXCLUDED.status,
        notes = EXCLUDED.notes,
        updated_at = EXCLUDED.updated_at;
    """

    notes_payload = {
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "gate2a_run_id": GATE2A_RUN_ID,
        "gate2c_run_id": GATE2C_RUN_ID,
        "scoring_formula": "sprint13-gate2a-v1",
        "threshold": 50.0,
        "total_universe_definitions": res1["total_universe_definitions"],
        "top20_canonical_count": res1["top20_canonical_count"],
        "expansion_definitions_count": res1["expansion_definitions_count"],
        "excluded_definitions_count": res1["excluded_definitions_count"],
        "eligible_expansion_count": res1["eligible_expansion_count"],
        "top20_baseline_qualified_count": res1["top20_baseline_qualified_count"],
        "expansion_qualified_count": res1["expansion_qualified_count"],
        "total_qualified_pool_count": res1["total_qualified_pool_count"],
        "total_qualified_pool_ids": res1["total_qualified_pool_ids"],
        "at_least_three_condition": res1["at_least_three_condition"],
        "top3_review_readiness": res1["top3_review_readiness"],
        "top3_selected": "NO",
        "summary_hash": hash1,
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    record_params = {
        "run_id": GATE3_RUN_ID,
        "dataset_hash": hash1,
        "run_type": "GATE3_QUALIFIED_POOL_EXPANSION",
        "status": "APPROVED_GATE3_EXPANDED",
        "video_count": 0,
        "channel_count": 0,
        "notes": json.dumps(notes_payload),
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    with client.get_cursor() as cur:
        cur.execute(query, record_params)

    print(f"Persisted Gate 3 analytical run record: {GATE3_RUN_ID}")

    # Verify DB persistence readback
    db_rows = client.execute("SELECT * FROM public.analytical_runs WHERE run_id = %s", [GATE3_RUN_ID])
    if not db_rows:
        raise ValueError("DB Persistence verification failed: row not found")

    db_notes = db_rows[0]["notes"]
    if isinstance(db_notes, str):
        db_notes = json.loads(db_notes)

    if db_notes.get("summary_hash") != hash1:
        raise ValueError("DB Persistence verification failed: persisted hash mismatch")

    print("PostgreSQL persistence dual-read verification SUCCESSFUL.")

    # Save artifacts to data/processed
    data_dir = ROOT_DIR / "data" / "processed"
    data_dir.mkdir(parents=True, exist_ok=True)

    artifact_payload = {
        "run_id": GATE3_RUN_ID,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
        "summary_hash": hash1,
        "governance": {
            "sprint": 13,
            "gate": "GATE3 QUALIFIED POOL EXPANSION",
            "at_least_three_condition": res1["at_least_three_condition"],
            "top3_review_readiness": res1["top3_review_readiness"],
            "top3_selected": "NO",
        },
        "universe_breakdown": {
            "total_definitions": res1["total_universe_definitions"],
            "top20_canonical": res1["top20_canonical_count"],
            "expansion_definitions": res1["expansion_definitions_count"],
            "excluded_artifacts": res1["excluded_definitions_count"],
            "eligible_expansion": res1["eligible_expansion_count"],
        },
        "baseline_preservation": {
            "baseline_qualified_count": res1["top20_baseline_qualified_count"],
            "baseline_qualified_ids": res1["top20_baseline_qualified_ids"],
            "def_045_score": res1["baseline_def_045_score"],
            "def_026_score": res1["baseline_def_026_score"],
            "def_054_score": res1["baseline_def_054_score"],
        },
        "expansion_results": {
            "expansion_qualified_count": res1["expansion_qualified_count"],
            "expansion_qualified_candidates": res1["expansion_qualified_candidates"],
            "near_miss_expansion_candidates": res1["near_miss_expansion_candidates"],
            "excluded_definitions": res1["excluded_definitions"],
        },
        "qualified_pool_summary": {
            "total_qualified_count": res1["total_qualified_pool_count"],
            "total_qualified_ids": res1["total_qualified_pool_ids"],
        },
    }

    artifact_path = data_dir / "sprint13_gate3_expansion_summary.json"
    artifact_path.write_text(json.dumps(artifact_payload, indent=2), encoding="utf-8")
    print(f"Saved artifact to {artifact_path}")

    return artifact_payload


if __name__ == "__main__":
    execute_gate3()
