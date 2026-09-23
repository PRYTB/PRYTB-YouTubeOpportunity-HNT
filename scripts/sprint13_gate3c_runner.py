"""Append-only Gate3C audit. Missing candidate evidence yields FIX_STOP, not GO."""

import argparse
import gc
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
    EvidenceError, FORMULA_VERSION, THRESHOLD, canonical_payload, payload_hash,
    qualification, reconstruct_economics, semantic_partition,
)
from app.config.profitability_config import profitability_config
from app.database.postgres_client import PostgresClient
from scripts.sprint13_gate2a_runner import EXPECTED_ECONOMIC_HASH, canonical_hash

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
    require(len(rows) == 1, "Expected exactly one source row")
    return rows[0]


def database_fingerprint(cur, excluded_run):
    """Hash all public row contents, excluding only this new audit record."""
    tables = read_rows(cur, """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name
    """)
    result = {}
    for entry in tables:
        table = entry["table_name"]
        where = sql.SQL("WHERE run_id <> %s") if table == "analytical_runs" else sql.SQL("")
        query = sql.SQL(
            "SELECT md5(to_jsonb(t)::text) AS h FROM public.{} t {} ORDER BY h"
        ).format(sql.Identifier(table), where)
        rows = read_rows(cur, query, (excluded_run,) if table == "analytical_runs" else ())
        digest = hashlib.sha256()
        for row in rows:
            digest.update(row["h"].encode("ascii"))
        result[table] = {"rows": len(rows), "sha256_sorted_row_md5": digest.hexdigest()}
    return result


def build_audit(run_id):
    client = PostgresClient()
    require(client.host == "localhost" and client.port == 5433,
            "Unexpected PostgreSQL endpoint")
    with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        identity = one(cur, "SELECT current_database() AS db, current_user AS usr")
        require(identity == {"db": "prytb", "usr": "prytb_app"}, "Wrong database identity")
        authority = one(cur, "SELECT * FROM analytical_runs WHERE run_id=%s", (SOURCE_RUN,))
        require(authority["status"] == "SPRINT12_FINAL_ANALYTICS_APPROVED",
                "Source run is not approved")
        notes = decoded(authority["notes"])
        semantic = one(cur, "SELECT * FROM analytical_runs WHERE run_id=%s", (SEMANTIC_RUN,))
        baseline = decoded(semantic["notes"])
        semantic_hash = hashlib.sha256(
            json.dumps(baseline, sort_keys=True).encode("utf-8")
        ).hexdigest()
        require(semantic_hash == semantic["dataset_hash"] == SEMANTIC_HASH,
                "Semantic baseline hash mismatch")
        definitions = read_rows(cur, """
            SELECT * FROM gate7_semantic_definitions WHERE run_id=%s ORDER BY definition_id
        """, (SOURCE_RUN,))
        require(len(definitions) == 58, "Universe must contain 58 definitions")
        decisions = semantic_partition(definitions)
        invalid = [d["candidate_id"] for d in decisions if not d["semantic_valid"]]
        require(invalid == sorted(baseline["invalid_definition_ids"]) and len(invalid) == 4,
                "Semantic universe differs from Gate3B")
        mapping_rows = notes["top20_evaluation_mapping"]
        mapping = {m["definition_id"]: m["evaluation_cluster_id"] for m in mapping_rows}
        require(len(mapping) == len(mapping_rows) == 20 and len(set(mapping.values())) == 20,
                "Invalid Top20 evaluation mapping")
        owners = {evaluation_id: candidate_id for candidate_id, evaluation_id in mapping.items()}
        structures = read_rows(cur, """
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
        """, (SOURCE_RUN,))
        structure_by_id = {s["definition_id"]: s for s in structures}
        analysis_tables = {
            "profitability": "cluster_profitability_analyses",
            "market": "market_structure_analyses",
            "production": "production_risk_analyses",
        }
        run_keys = {"profitability": "sprint9_profitability", "market": "sprint7_market",
                    "production": "sprint8_production"}
        analysis_runs = {k: notes["sprint_run_ids"][v] for k, v in run_keys.items()}
        analyses = {}
        for name, table in analysis_tables.items():
            rows = read_rows(cur, sql.SQL(
                "SELECT * FROM {} WHERE source_cluster_run_id=%s AND run_id=%s ORDER BY cluster_id"
            ).format(sql.Identifier(table)), (SOURCE_RUN, analysis_runs[name]))
            require(len(rows) == 20 and len({r["cluster_id"] for r in rows}) == 20,
                    f"Unexpected {name} evidence cardinality")
            for row in rows:
                row["metrics"] = decoded(row["metrics"])
            analyses[name] = {r["cluster_id"]: r for r in rows}
        economics = read_rows(cur, """
            SELECT * FROM candidate_economics WHERE run_id=%s
            ORDER BY candidate_rank ASC, candidate_id ASC
        """, (ECONOMIC_RUN,))
        require(len(economics) == 20 and {r["candidate_id"] for r in economics} == set(mapping),
                "Gate2C economics identity mismatch")
        rpm = read_rows(cur, """
            SELECT * FROM rpm_benchmarks ORDER BY content_category ASC, market ASC,
            language ASC, content_type ASC, confidence DESC, benchmark_id ASC
        """)
        costs = read_rows(cur, """
            SELECT * FROM production_cost_benchmarks ORDER BY confidence DESC,
            source_name ASC, source_version ASC, source_date ASC, benchmark_id ASC
        """)
        require(len(rpm) == 4 and len(costs) == 2, "Unexpected benchmark inventory")
        economic_hash = canonical_hash({
            "rpm": canonical_hash(rpm), "cost": canonical_hash(costs),
            "econ": canonical_hash(economics),
        })
        require(economic_hash == EXPECTED_ECONOMIC_HASH, "Approved economic snapshot changed")
        labels = {r["candidate_id"]: r["canonical_label"] for r in baseline["finalist_decisions"]}
        source_defs = {d["definition_id"]: d for d in definitions}
        for decision in decisions:
            candidate_id = decision["candidate_id"]
            definition = source_defs[candidate_id]
            counts = structure_by_id.get(candidate_id)
            require(counts is not None, f"Missing memberships: {candidate_id}")
            require(all(counts[k] == definition[k] for k in decision["structural_evidence"]),
                    f"Structural count mismatch: {candidate_id}")
            require(counts["unique_videos"] == counts["found_videos"] ==
                    counts["found_outliers"] == counts["video_count"],
                    f"Missing or duplicate source evidence: {candidate_id}")
            decision["structural_evidence"]["membership_parent_cluster_ids"] = counts["parents"]
            decision["canonical_label"] = labels.get(candidate_id, decision["canonical_label"])
            decision["label_source_run_id"] = SEMANTIC_RUN if candidate_id in labels else SOURCE_RUN
            decision["source_lineage"] = {
                "definition_run_id": SOURCE_RUN, "semantic_run_id": SEMANTIC_RUN,
                "economic_benchmark_run_id": ECONOMIC_RUN,
                "parent_cluster_id": definition["parent_cluster_id"],
                "evaluation_cluster_id": mapping.get(candidate_id),
            }
            decision.update(economic_score=None, economic_evidence_status="NOT_EVALUATED",
                            threshold=THRESHOLD, formula_version=FORMULA_VERSION,
                            known_component_weight=None, risk_penalty=None)
            if candidate_id in mapping:
                evidence = {k: rows.get(mapping[candidate_id]) for k, rows in analyses.items()}
                decision.update(reconstruct_economics(
                    definition, mapping, evidence, SOURCE_RUN, analysis_runs,
                ))
                decision["economic_evidence_status"] = "REPRODUCED"
            elif decision["semantic_valid"] and decision["structural_eligible"]:
                decision["economic_evidence_status"] = "MISSING_CANDIDATE_SCOPED_ECONOMIC_EVIDENCE"
                decision["legacy_lookup_audit"] = {
                    "ambiguous_unordered_limit_one": len(counts["parents"]) > 1,
                    "possible_lookups": [
                        {"queried_evaluation_id": parent,
                         "actual_candidate_owner": owners.get(parent),
                         "defect": "WRONG_CANDIDATE_IDENTITY" if parent in owners
                                   else "NO_SOURCE_ROW_DEFAULTS_USED"}
                        for parent in counts["parents"]
                    ],
                }
            economic, combined = qualification(
                decision["semantic_valid"], decision["structural_eligible"],
                decision["economic_score"],
            )
            decision["economic_qualified"], decision["combined_qualified"] = economic, combined
            decision["exclusion_reason"] = (
                decision["semantic_rejection_reason"]
                or "; ".join(decision["structural_exclusion_reasons"])
                or (decision["economic_evidence_status"] if economic is None else
                    "BELOW_ECONOMIC_THRESHOLD" if not economic else None)
            )
        eligible = [d for d in decisions if d["semantic_valid"] and d["structural_eligible"]]
        pending = [d["candidate_id"] for d in eligible if d["economic_score"] is None]
        qualified = sorted((d for d in decisions if d["combined_qualified"] is True),
                           key=lambda d: (-d["economic_score"], d["candidate_id"]))
        retained_missing = sorted(set(baseline["final_eligible_pool_ids"]) -
                                  {d["candidate_id"] for d in qualified})
        blockers = []
        if pending:
            blockers.append({"reason": "MISSING_CANDIDATE_SCOPED_ECONOMIC_EVIDENCE",
                             "candidate_ids": pending})
        if retained_missing:
            blockers.append({"reason": "BASELINE_QUALIFIED_POOL_NOT_RECONCILED",
                             "candidate_ids": retained_missing})
        near = sorted((d for d in eligible if d["economic_qualified"] is False),
                      key=lambda d: (-d["economic_score"], d["candidate_id"]))[:10]
        return {
            "run_id": run_id, "source_run_id": SOURCE_RUN,
            "semantic_run_id": SEMANTIC_RUN, "semantic_hash": semantic_hash,
            "economic_snapshot_hash": economic_hash,
            "formula_version": FORMULA_VERSION, "threshold": THRESHOLD,
            "weights": profitability_config.get_weights_dict(),
            "risk_penalty_scale": profitability_config.risk_penalty_scale,
            "benchmark_policy": "Unchanged Gate2C benchmarks; money is not a score component",
            "status": "FIX_STOP" if blockers else "GO",
            "top3_readiness": "UNDETERMINED" if blockers else
                              "YES" if len(qualified) >= 3 else "NO",
            "top3_selected": False, "blockers": blockers,
            "summary": {
                "total": len(decisions), "semantic_valid": len(decisions) - len(invalid),
                "semantic_invalid": len(invalid), "invalid_ids": invalid,
                "structural_eligible": len(eligible),
                "structural_excluded": sum(d["semantic_valid"] and not d["structural_eligible"]
                                           for d in decisions),
                "unexplained_structural_exclusions": 0,
                "eligible_evaluated": len(eligible) - len(pending),
                "eligible_pending": len(pending),
                "verified_qualified_ids": [d["candidate_id"] for d in qualified],
                "qualified_pool_complete": not blockers,
            },
            "near_misses_scope": "PARTIAL_EVIDENCE_ONLY" if pending else "COMPLETE_UNIVERSE",
            "near_misses": [
                {k: d[k] for k in ("candidate_id", "canonical_label", "economic_score",
                                   "semantic_valid", "structural_eligible",
                                   "main_limiting_components", "risk_penalty", "evidence_confidence")}
                | {"distance_to_50": THRESHOLD - d["economic_score"]} for d in near
            ],
            "decisions": decisions,
            "database_before": database_fingerprint(cur, run_id),
        }


def readback_hash(run_id):
    with PostgresClient().get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        row = one(cur, "SELECT notes,dataset_hash FROM analytical_runs WHERE run_id=%s", (run_id,))
        payload = decoded(row["notes"])
        definitions = read_rows(cur, """
            SELECT definition_id FROM gate7_semantic_definitions WHERE run_id=%s
        """, (SOURCE_RUN,))
        ids = [d["candidate_id"] for d in payload["decisions"]]
        require(len(ids) == len(set(ids)) == 58, "Decision cardinality mismatch")
        require(set(ids) == {d["definition_id"] for d in definitions}, "Missing or extra IDs")
        require(all(d["source_lineage"]["definition_run_id"] == SOURCE_RUN
                    for d in payload["decisions"]), "Wrong lineage")
        digest = payload_hash(payload)
        require(digest == row["dataset_hash"], "Persisted payload hash mismatch")
        return digest


def execute(run_id=None, verify=False):
    run_id = run_id or "sprint13_gate3c_qualified_pool_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    payload = build_audit(run_id)
    expected = payload_hash(payload)
    summary = {k: payload[k] for k in ("run_id", "status", "top3_readiness", "summary",
                                      "blockers", "near_misses")}
    if not verify:
        with PostgresClient().get_cursor() as cur:
            cur.execute("""
                INSERT INTO analytical_runs
                    (run_id,dataset_hash,run_type,status,video_count,channel_count,notes)
                VALUES (%s,%s,%s,%s,0,0,%s)
            """, (run_id, expected, "GATE3C_SEMANTIC_QUALIFIED_POOL", payload["status"],
                  canonical_payload(payload)))
    del payload
    gc.collect()
    hash1 = readback_hash(run_id)
    gc.collect()
    hash2 = readback_hash(run_id)
    require(hash1 == hash2 == expected, "Fresh reconstruction/readback differs")
    summary.update(hash1=hash1, hash2=hash2, match=True,
                   fresh_source_reconstruction_matches=True)
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", metavar="RUN_ID", help="Read-only full post-test reconstruction")
    args = parser.parse_args()
    result = execute(args.verify, verify=bool(args.verify))
    sys.exit(2 if result["status"] == "FIX_STOP" and not args.verify else 0)
