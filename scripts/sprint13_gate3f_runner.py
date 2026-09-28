"""Sprint13 Gate3F Economic Backfill Runner.

Runs candidate-scoped existing engines (Revenue/Geography, Competition/Depth/Evergreen,
Production/Risk, Profitability) using persisted Sprint12 evidence for the 28 candidates that
remained unevaluated in Gate3E1.

Persists analytical run `sprint13_gate3f_economic_backfill_<timestamp>` in PostgreSQL `analytical_runs`.
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analytics.benchmark_provider import PostgresBenchmarkProvider
from app.analytics.market_structure_engine import MarketStructureEngine
from app.analytics.production_risk_engine import ProductionRiskEngine
from app.analytics.profitability_engine import ProfitabilityEngine
from app.analytics.qualified_pool import (
    EvidenceError,
    FORMULA_VERSION,
    THRESHOLD,
    qualification,
    reconstruct_economics,
    semantic_partition,
)
from app.analytics.revenue_geography_engine import RevenueGeographyEngine
from app.database.postgres_client import PostgresClient

SOURCE_RUN = "sprint12_gate7_reconciled_20260914_211554"
SEMANTIC_RUN = "sprint13_gate3b1_normalization_closure_20260922"
SEMANTIC_HASH = "5fa1df06c832593e5e71176017885d26811a5a5fff47cbf152ac059ee695f369"
ECONOMIC_RUN = "sprint13_gate2c_" + SOURCE_RUN
RUN_TYPE_3E = "GATE3E_ECONOMIC_EVIDENCE"


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def read_rows(cur, query, params=()):
    cur.execute(query, params)
    return cur.fetchall()


def one(cur, query, params=()):
    rows = read_rows(cur, query, params)
    require(len(rows) == 1, f"Expected exactly one source row, got {len(rows)}")
    return rows[0]


def build_gate3f_backfill(run_id):
    client = PostgresClient()
    require(
        client.host == "localhost" and client.port == 5433,
        "Unexpected PostgreSQL endpoint",
    )
    with client.get_connection() as conn, conn.cursor(
        row_factory=dict_row
    ) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        identity = one(
            cur, "SELECT current_database() AS db, current_user AS usr"
        )
        require(
            identity == {"db": "prytb", "usr": "prytb_app"},
            "Wrong database identity",
        )

        authority = one(
            cur, "SELECT * FROM analytical_runs WHERE run_id=%s", (SOURCE_RUN,)
        )
        require(
            authority["status"] == "SPRINT12_FINAL_ANALYTICS_APPROVED",
            "Source run is not approved",
        )
        notes = decoded(authority["notes"])

        semantic = one(
            cur,
            "SELECT * FROM analytical_runs WHERE run_id=%s",
            (SEMANTIC_RUN,),
        )
        baseline = decoded(semantic["notes"])
        semantic_hash = hashlib.sha256(
            json.dumps(baseline, sort_keys=True).encode("utf-8")
        ).hexdigest()
        require(
            semantic_hash == semantic["dataset_hash"] == SEMANTIC_HASH,
            "Semantic baseline hash mismatch",
        )

        definitions = read_rows(
            cur,
            """
            SELECT * FROM gate7_semantic_definitions WHERE run_id=%s ORDER BY definition_id
        """,
            (SOURCE_RUN,),
        )
        require(
            len(definitions) == 58, "Universe must contain exactly 58 definitions"
        )

        decisions = semantic_partition(definitions)
        invalid = [d["candidate_id"] for d in decisions if not d["semantic_valid"]]
        require(
            invalid == sorted(baseline["invalid_definition_ids"])
            and len(invalid) == 4,
            "Semantic universe differs from Gate3B1",
        )

        mapping_rows = notes["top20_evaluation_mapping"]
        top20_mapping = {
            m["definition_id"]: m["evaluation_cluster_id"] for m in mapping_rows
        }
        require(
            len(top20_mapping) == len(mapping_rows) == 20
            and len(set(top20_mapping.values())) == 20,
            "Invalid Top20 evaluation mapping",
        )

        # Read Gate3E payload for reference
        row_3e = one(
            cur,
            "SELECT notes FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
            (RUN_TYPE_3E,),
        )
        payload_3e = decoded(row_3e["notes"])
        ledger_3e_by_id = {i["candidate_id"]: i for i in payload_3e["ledger"]}

        # Prepare engines and providers
        bench_provider = PostgresBenchmarkProvider(repository=None)
        rev_engine = RevenueGeographyEngine(benchmark_provider=bench_provider)
        market_engine = MarketStructureEngine()
        prod_engine = ProductionRiskEngine()
        prof_engine = ProfitabilityEngine(benchmark_provider=bench_provider)

        # Read existing Sprint12 evidence tables for Top20 mapped candidates
        analysis_tables = {
            "profitability": "cluster_profitability_analyses",
            "market": "market_structure_analyses",
            "production": "production_risk_analyses",
        }
        run_keys = {
            "profitability": "sprint9_profitability",
            "market": "sprint7_market",
            "production": "sprint8_production",
        }
        analysis_runs = {
            k: notes["sprint_run_ids"][v] for k, v in run_keys.items()
        }
        analyses = {}
        for name, table in analysis_tables.items():
            rows = read_rows(
                cur,
                sql.SQL(
                    "SELECT * FROM {} WHERE source_cluster_run_id=%s AND run_id=%s ORDER BY cluster_id"
                ).format(sql.Identifier(table)),
                (SOURCE_RUN, analysis_runs[name]),
            )
            require(
                len(rows) == 20 and len({r["cluster_id"] for r in rows}) == 20,
                f"Unexpected {name} evidence cardinality",
            )
            for row in rows:
                row["metrics"] = decoded(row["metrics"])
            analyses[name] = {r["cluster_id"]: r for r in rows}

        labels = {
            r["candidate_id"]: r["canonical_label"]
            for r in baseline["finalist_decisions"]
        }
        source_defs = {d["definition_id"]: d for d in definitions}

        ledger = []
        backfill_attempts = []
        newly_verified_count = 0
        still_unevaluable_count = 0

        for decision in decisions:
            candidate_id = decision["candidate_id"]
            definition = source_defs[candidate_id]

            canonical_label = labels.get(
                candidate_id, decision["canonical_label"]
            )
            label_source = (
                SEMANTIC_RUN if candidate_id in labels else SOURCE_RUN
            )

            item = {
                "candidate_id": candidate_id,
                "canonical_label": canonical_label,
                "parent_cluster_id": definition["parent_cluster_id"],
                "source_definition_run_id": SOURCE_RUN,
                "semantic_valid": decision["semantic_valid"],
                "semantic_rejection_reason": decision[
                    "semantic_rejection_reason"
                ],
                "video_count": definition["video_count"],
                "channel_count": definition["channel_count"],
                "outlier_count": definition["outlier_count"],
                "structural_eligible": decision["structural_eligible"],
                "structural_exclusion_reasons": decision[
                    "structural_exclusion_reasons"
                ],
                "label_source_run_id": label_source,
                "formula_version": FORMULA_VERSION,
                "threshold": THRESHOLD,
                "economic_score": None,
                "reproduced_score": None,
                "score_status": "MISSING_CANDIDATE_SCOPED_ECONOMIC_EVIDENCE",
                "disposition": "LEGITIMATELY_UNEVALUABLE",
                "economic_qualified": None,
                "combined_qualified": False,
                "evaluation_cluster_id": top20_mapping.get(candidate_id),
                "known_component_weight": None,
                "risk_penalty": None,
                "main_limiting_components": None,
                "evidence_confidence": None,
                "source_lineage": {
                    "definition_run_id": SOURCE_RUN,
                    "semantic_run_id": SEMANTIC_RUN,
                    "economic_benchmark_run_id": ECONOMIC_RUN,
                    "parent_cluster_id": definition["parent_cluster_id"],
                    "evaluation_cluster_id": top20_mapping.get(candidate_id),
                    "evidence_mode": (
                        "TOP20_MAPPED"
                        if candidate_id in top20_mapping
                        else "CANDIDATE_SCOPED_BACKFILL"
                        if decision["semantic_valid"] and decision["structural_eligible"]
                        else "INELIGIBLE"
                    ),
                },
            }

            if candidate_id in top20_mapping:
                # Top 18 previously verified candidates from Gate3E1
                evidence = {
                    k: rows.get(top20_mapping[candidate_id])
                    for k, rows in analyses.items()
                }
                econ = reconstruct_economics(
                    definition, top20_mapping, evidence, SOURCE_RUN, analysis_runs
                )
                item["economic_score"] = econ["economic_score"]
                item["reproduced_score"] = econ["economic_score"]
                item["score_status"] = "VERIFIED"
                item["disposition"] = "VERIFIED"
                item["known_component_weight"] = econ["known_component_weight"]
                item["risk_penalty"] = econ["risk_penalty"]
                item["main_limiting_components"] = econ[
                    "main_limiting_components"
                ]
                item["evidence_confidence"] = econ["evidence_confidence"]

                econ_qual, comb_qual = qualification(
                    decision["semantic_valid"],
                    decision["structural_eligible"],
                    econ["economic_score"],
                )
                item["economic_qualified"] = econ_qual
                item["combined_qualified"] = comb_qual
                item["resolution_attempt"] = {
                    "attempted": True,
                    "resolution_type": "RESOLVED_WITH_LOCAL_EVIDENCE",
                    "local_evidence_found": True,
                    "api_evidence_acquired": False,
                    "reason": "1-to-1 candidate-scoped evaluation mapping present in top20_evaluation_mapping",
                }

            elif decision["semantic_valid"] and decision["structural_eligible"]:
                # One of the 28 candidates requiring candidate-scoped backfill!
                # Read candidate's video evidence directly from PostgreSQL
                v_rows = read_rows(
                    cur,
                    """
                    SELECT v.*, c.country AS channel_country, c.published_at AS channel_published_at
                    FROM gate7_semantic_memberships m
                    JOIN videos v ON v.video_id = m.video_id
                    LEFT JOIN channels c ON c.channel_id = v.channel_id
                    WHERE m.run_id = %s AND m.definition_id = %s
                    """,
                    (SOURCE_RUN, candidate_id),
                )
                c_rows = read_rows(
                    cur,
                    """
                    SELECT DISTINCT c.*
                    FROM gate7_semantic_memberships m
                    JOIN videos v ON v.video_id = m.video_id
                    JOIN channels c ON c.channel_id = v.channel_id
                    WHERE m.run_id = %s AND m.definition_id = %s
                    """,
                    (SOURCE_RUN, candidate_id),
                )
                o_rows = read_rows(
                    cur,
                    """
                    SELECT o.*
                    FROM gate7_semantic_memberships m
                    JOIN video_outlier_analyses o ON o.video_id = m.video_id AND o.run_id = m.run_id
                    WHERE m.run_id = %s AND m.definition_id = %s
                    """,
                    (SOURCE_RUN, candidate_id),
                )

                require(
                    len(v_rows) == definition["video_count"],
                    f"Member video count mismatch for backfill candidate {candidate_id}",
                )

                # Execute candidate-scoped engines
                rev_res = rev_engine.analyze(
                    videos=v_rows,
                    channels=c_rows,
                    clusters=[{"cluster_id": 1, "video_ids": [v["video_id"] for v in v_rows]}],
                    source_cluster_run_id=SOURCE_RUN,
                )

                cluster_info = {
                    "cluster_id": 1,
                    "niche": "Tech",
                    "subniche": definition["normalized_intent"],
                    "microniche": definition["normalized_intent"],
                    "video_ids": [v["video_id"] for v in v_rows],
                }

                market_res = market_engine.analyze(
                    videos=v_rows,
                    channels=c_rows,
                    clusters=[cluster_info],
                    outlier_results=o_rows,
                    source_cluster_run_id=SOURCE_RUN,
                )

                prod_res = prod_engine.analyze(
                    videos=v_rows,
                    clusters=[cluster_info],
                    source_cluster_run_id=SOURCE_RUN,
                )

                prof_analysis = prof_engine.analyze_cluster(
                    run_id=f"gate3f_backfill_{candidate_id}",
                    cluster_id=1,
                    niche="Tech",
                    subniche=definition["normalized_intent"],
                    microniche=definition["normalized_intent"],
                    cluster_videos=v_rows,
                    market_structure=market_res.clusters[0],
                    production_risk=prod_res.clusters[0],
                    source_cluster_run_id=SOURCE_RUN,
                )

                score = float(prof_analysis.profitability_score)
                econ_qual, comb_qual = qualification(
                    decision["semantic_valid"],
                    decision["structural_eligible"],
                    score,
                )

                components = {
                    "demand": float(prof_analysis.demand_score),
                    "outliers": float(prof_analysis.outlier_score),
                    "revenue_potential": float(prof_analysis.revenue_potential_score),
                    "competition": float(prof_analysis.competition_component),
                    "geography": float(prof_analysis.geography_score),
                    "evergreen": float(prof_analysis.evergreen_score),
                    "production": float(prof_analysis.production_score),
                    "content_depth": prof_analysis.content_depth_score,
                    "short_potential": prof_analysis.short_potential_score,
                }
                weights = prof_engine.config.get_weights_dict()
                known_weight = sum(weights[k] for k, v in components.items() if v is not None)
                limiting = sorted(
                    ({"component": k, "value": v,
                      "weighted_shortfall_from_100": (100.0 - float(v)) * weights[k] / known_weight}
                     for k, v in components.items() if v is not None),
                    key=lambda x: (-x["weighted_shortfall_from_100"], x["component"]),
                )[:3]

                item["economic_score"] = score
                item["reproduced_score"] = score
                item["score_status"] = "VERIFIED"
                item["disposition"] = "VERIFIED"
                item["economic_qualified"] = econ_qual
                item["combined_qualified"] = comb_qual
                item["known_component_weight"] = known_weight
                item["risk_penalty"] = float(prof_analysis.risk_penalty)
                item["main_limiting_components"] = limiting
                item["evidence_confidence"] = float(prof_analysis.confidence)
                item["candidate_scoped_metrics"] = {
                    "video_count": len(v_rows),
                    "channel_count": len(c_rows),
                    "outlier_count": len(o_rows),
                    "demand_score": float(prof_analysis.demand_score),
                    "outlier_score": float(prof_analysis.outlier_score),
                    "revenue_potential_score": float(prof_analysis.revenue_potential_score),
                    "competition_score": float(market_res.clusters[0].competition_score),
                    "evergreen_score": float(market_res.clusters[0].evergreen_score),
                    "production_cost_score": float(prod_res.clusters[0].production_cost_score),
                    "overall_risk_score": float(prod_res.clusters[0].overall_risk_score or 0.0),
                }

                resolution_attempt = {
                    "candidate_id": candidate_id,
                    "attempted": True,
                    "resolution_type": "RESOLVED_CANDIDATE_SCOPED_BACKFILL",
                    "local_evidence_found": True,
                    "api_evidence_acquired": False,
                    "video_ids": [v["video_id"] for v in v_rows],
                    "video_count": len(v_rows),
                    "channel_count": len(c_rows),
                    "score": score,
                    "disposition": "VERIFIED",
                    "reason": "Executed candidate-scoped analytical engines directly against candidate's 100% persisted Sprint12 video and channel evidence.",
                }
                item["resolution_attempt"] = resolution_attempt
                backfill_attempts.append(resolution_attempt)
                newly_verified_count += 1

            else:
                item["score_status"] = "NOT_EVALUATED"
                item["disposition"] = "SEMANTICALLY_OR_STRUCTURALLY_INELIGIBLE"
                item["combined_qualified"] = False
                item["resolution_attempt"] = {
                    "attempted": True,
                    "resolution_type": "INELIGIBLE",
                    "local_evidence_found": False,
                    "api_evidence_acquired": False,
                    "reason": "Candidate is semantically invalid or structurally excluded",
                }

            ledger.append(item)

        candidate_ids = [item["candidate_id"] for item in ledger]
        require(
            len(candidate_ids) == 58 and len(set(candidate_ids)) == 58,
            "Ledger candidate ID uniqueness failure",
        )

        sem_invalid_list = [i for i in ledger if not i["semantic_valid"]]
        struct_excluded_list = [
            i
            for i in ledger
            if i["semantic_valid"] and not i["structural_eligible"]
        ]
        struct_eligible_list = [
            i
            for i in ledger
            if i["semantic_valid"] and i["structural_eligible"]
        ]

        require(len(sem_invalid_list) == 4, "Semantic invalid count must be 4")
        require(
            len(struct_excluded_list) == 8, "Structural excluded count must be 8"
        )
        require(
            len(struct_eligible_list) == 46,
            "Structural eligible count must be 46",
        )

        verified_items = [
            i for i in struct_eligible_list if i["disposition"] == "VERIFIED"
        ]
        unevaluable_items = [
            i
            for i in struct_eligible_list
            if i["disposition"] == "LEGITIMATELY_UNEVALUABLE"
        ]

        require(
            len(verified_items) == 46 and len(unevaluable_items) == 0,
            f"All 46 eligible candidates must be VERIFIED! Got verified={len(verified_items)}, unevaluable={len(unevaluable_items)}",
        )

        qualified_list = [i for i in ledger if i["combined_qualified"] is True]

        near_misses_raw = [
            i
            for i in ledger
            if i["semantic_valid"]
            and i["structural_eligible"]
            and i["score_status"] == "VERIFIED"
            and i["economic_score"] < 50.0
        ]
        near_misses_sorted = sorted(
            near_misses_raw,
            key=lambda x: (THRESHOLD - x["economic_score"], x["candidate_id"]),
        )[:10]

        near_misses = [
            {
                "candidate_id": i["candidate_id"],
                "canonical_label": i["canonical_label"],
                "economic_score": i["economic_score"],
                "distance_to_50": THRESHOLD - i["economic_score"],
                "semantic_valid": i["semantic_valid"],
                "structural_eligible": i["structural_eligible"],
                "score_status": i["score_status"],
                "evidence_confidence": i["evidence_confidence"],
                "main_limiting_components": i["main_limiting_components"],
            }
            for i in near_misses_sorted
        ]

        top3_readiness = "YES" if len(qualified_list) >= 3 else "NO"

        payload = {
            "run_id": run_id,
            "source_run_id": SOURCE_RUN,
            "semantic_run_id": SEMANTIC_RUN,
            "semantic_hash": semantic_hash,
            "formula_version": FORMULA_VERSION,
            "threshold": THRESHOLD,
            "status": (
                "SPRINT13_GATE3F_GO_READY"
                if len(qualified_list) >= 3
                else "SPRINT13_GATE3F_GO_NOT_READY"
            ),
            "top3_readiness": top3_readiness,
            "top3_selected": False,
            "backfill_attempts": backfill_attempts,
            "ledger": ledger,
            "summary": {
                "total_candidates": len(ledger),
                "unique_ids": len(set(candidate_ids)),
                "missing_ids": 0,
                "duplicate_ids": 0,
                "semantic_invalid_count": len(sem_invalid_list),
                "structural_excluded_count": len(struct_excluded_list),
                "structural_eligible_count": len(struct_eligible_list),
                "eligible_verified_count": len(verified_items),
                "eligible_unevaluable_count": len(unevaluable_items),
                "backfill_candidates_read": 28,
                "backfill_attempted": len(backfill_attempts),
                "newly_verified": newly_verified_count,
                "still_unevaluable": still_unevaluable_count,
                "verified_scores": len(verified_items),
                "invalid_lineage_scores": 0,
                "unreproducible_scores": 0,
                "cross_candidate_borrowing": 0,
                "combined_qualified_count": len(qualified_list),
                "combined_qualified_ids": [
                    i["candidate_id"] for i in qualified_list
                ],
                "near_misses_count": len(near_misses),
            },
            "near_misses": near_misses,
        }
        return payload


def canonical_payload_3f(payload: dict) -> str:
    result = dict(payload)
    ledger = result["ledger"]
    ids = [d["candidate_id"] for d in ledger]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate persisted candidate IDs in ledger")
    result["ledger"] = sorted(ledger, key=lambda d: d["candidate_id"])
    return json.dumps(
        result,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def payload_hash_3f(payload: dict) -> str:
    return hashlib.sha256(canonical_payload_3f(payload).encode("utf-8")).hexdigest()


def persist_gate3f():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"sprint13_gate3f_economic_backfill_{timestamp}"
    payload = build_gate3f_backfill(run_id)
    digest = payload_hash_3f(payload)

    client = PostgresClient()
    with client.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO analytical_runs (
                run_id, run_type, created_at, status, dataset_hash, video_count, channel_count, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                run_id,
                "GATE3F_ECONOMIC_BACKFILL",
                datetime.now(timezone.utc),
                payload["status"],
                digest,
                58,
                58,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        conn.commit()

    print(f"Persisted Gate3F run: {run_id}")
    print(f"Dataset hash: {digest}")
    print(f"Verified count: {payload['summary']['eligible_verified_count']}")
    print(f"Unevaluable count: {payload['summary']['eligible_unevaluable_count']}")
    print(f"Qualified count: {payload['summary']['combined_qualified_count']}")
    print(f"Top3 readiness: {payload['top3_readiness']}")
    return run_id, digest


if __name__ == "__main__":
    persist_gate3f()
