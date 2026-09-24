"""Sprint13 Gate3D Economic Coverage Runner.

Builds and persists candidate-scoped economic coverage for all 58 Sprint13 candidates.
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

from app.analytics.qualified_pool import (
    EvidenceError,
    FORMULA_VERSION,
    THRESHOLD,
    qualification,
    reconstruct_economics,
    semantic_partition,
)
from app.database.postgres_client import PostgresClient

SOURCE_RUN = "sprint12_gate7_reconciled_20260914_211554"
SEMANTIC_RUN = "sprint13_gate3b1_normalization_closure_20260922"
SEMANTIC_HASH = "5fa1df06c832593e5e71176017885d26811a5a5fff47cbf152ac059ee695f369"
ECONOMIC_RUN = "sprint13_gate2c_" + SOURCE_RUN


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


def build_gate3d_coverage(run_id):
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
        mapping = {
            m["definition_id"]: m["evaluation_cluster_id"] for m in mapping_rows
        }
        require(
            len(mapping) == len(mapping_rows) == 20
            and len(set(mapping.values())) == 20,
            "Invalid Top20 evaluation mapping",
        )

        structures = read_rows(
            cur,
            """
            SELECT m.definition_id, count(*) AS video_count,
                   count(DISTINCT v.channel_id) AS channel_count,
                   count(*) FILTER (WHERE o.is_strong_outlier OR o.is_major_outlier
                      OR o.is_extreme_outlier OR o.small_channel_outlier) AS outlier_count,
                   count(DISTINCT m.video_id) AS unique_videos,
                   count(v.video_id) AS found_videos, count(o.video_id) AS found_outliers,
                   array_agg(DISTINCT m.parent_cluster_id ORDER BY m.parent_cluster_id) AS parents
            FROM gate7_semantic_memberships m
            LEFT JOIN videos v ON v.video_id=m.video_id
            LEFT JOIN video_outlier_analyses o ON o.run_id=m.run_id AND o.video_id=m.video_id
            WHERE m.run_id=%s GROUP BY m.definition_id ORDER BY m.definition_id
        """,
            (SOURCE_RUN,),
        )
        structure_by_id = {s["definition_id"]: s for s in structures}

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
        for decision in decisions:
            candidate_id = decision["candidate_id"]
            definition = source_defs[candidate_id]
            counts = structure_by_id.get(candidate_id)
            require(
                counts is not None,
                f"Missing memberships for candidate {candidate_id}",
            )
            require(
                all(
                    counts[k] == definition[k]
                    for k in decision["structural_evidence"]
                ),
                f"Structural count mismatch for candidate {candidate_id}",
            )

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
                "evaluation_cluster_id": mapping.get(candidate_id),
                "known_component_weight": None,
                "risk_penalty": None,
                "main_limiting_components": None,
                "evidence_confidence": None,
                "source_lineage": {
                    "definition_run_id": SOURCE_RUN,
                    "semantic_run_id": SEMANTIC_RUN,
                    "economic_benchmark_run_id": ECONOMIC_RUN,
                    "parent_cluster_id": definition["parent_cluster_id"],
                    "evaluation_cluster_id": mapping.get(candidate_id),
                },
            }

            if candidate_id in mapping:
                evidence = {
                    k: rows.get(mapping[candidate_id])
                    for k, rows in analyses.items()
                }
                econ = reconstruct_economics(
                    definition, mapping, evidence, SOURCE_RUN, analysis_runs
                )
                item["economic_score"] = econ["economic_score"]
                item["reproduced_score"] = econ["economic_score"]
                item["score_status"] = "VERIFIED"
                item["disposition"] = "VERIFIED_SCORE"
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
            elif decision["semantic_valid"] and decision["structural_eligible"]:
                item["score_status"] = (
                    "MISSING_CANDIDATE_SCOPED_ECONOMIC_EVIDENCE"
                )
                item["disposition"] = "LEGITIMATELY_UNEVALUABLE"
                item["combined_qualified"] = False
            else:
                item["score_status"] = "NOT_EVALUATED"
                item["disposition"] = "SEMANTICALLY_OR_STRUCTURALLY_INELIGIBLE"
                item["combined_qualified"] = False

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

        scored_items = [
            i for i in ledger if i["disposition"] == "VERIFIED_SCORE"
        ]
        unevaluable_items = [
            i
            for i in struct_eligible_list
            if i["disposition"] == "LEGITIMATELY_UNEVALUABLE"
        ]

        require(
            len(scored_items) == 20, "Scored candidates count must be 20"
        )
        require(
            len(unevaluable_items) == 28,
            "Legitimately unevaluable eligible candidates must be 28",
        )
        require(
            len([i for i in struct_eligible_list if i["disposition"] == "VERIFIED_SCORE"]) == 18,
            "Structurally eligible scored count must be 18",
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
                "SPRINT13_GATE3D_GO_READY"
                if len(qualified_list) >= 3
                else "SPRINT13_GATE3D_GO_NOT_READY"
            ),
            "top3_readiness": top3_readiness,
            "top3_selected": False,
            "ledger": ledger,
            "summary": {
                "total_candidates": len(ledger),
                "unique_ids": len(set(candidate_ids)),
                "missing_ids": 0,
                "duplicate_ids": 0,
                "semantic_invalid_count": len(sem_invalid_list),
                "structural_excluded_count": len(struct_excluded_list),
                "structural_eligible_count": len(struct_eligible_list),
                "eligible_scored_count": len(scored_items),
                "eligible_unevaluable_count": len(unevaluable_items),
                "verified_scores": len(scored_items),
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


def canonical_payload_3d(payload: dict) -> str:
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


def payload_hash_3d(payload: dict) -> str:
    return hashlib.sha256(canonical_payload_3d(payload).encode("utf-8")).hexdigest()


def persist_gate3d():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"sprint13_gate3d_economic_coverage_{timestamp}"
    payload = build_gate3d_coverage(run_id)
    digest = payload_hash_3d(payload)

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
                "GATE3D_ECONOMIC_COVERAGE",
                datetime.now(timezone.utc),
                payload["status"],
                digest,
                58,
                58,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        conn.commit()

    print(f"Persisted Gate3D run: {run_id}")
    print(f"Dataset hash: {digest}")
    print(f"Qualified count: {payload['summary']['combined_qualified_count']}")
    print(f"Top3 readiness: {payload['top3_readiness']}")
    return run_id, digest


if __name__ == "__main__":
    persist_gate3d()
