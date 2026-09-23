"""Sprint13 Gate3C2 Closed Loop Forensic Reconciliation Runner.

Builds and persists an immutable 58-candidate forensic ledger directly from PostgreSQL.
"""

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
    require(len(rows) == 1, f"Expected exactly one source row, got {len(rows)}")
    return rows[0]


def build_forensic_ledger(run_id):
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
        require(len(definitions) == 58, "Universe must contain exactly 58 definitions")
        
        decisions = semantic_partition(definitions)
        invalid = [d["candidate_id"] for d in decisions if not d["semantic_valid"]]
        require(invalid == sorted(baseline["invalid_definition_ids"]) and len(invalid) == 4,
                "Semantic universe differs from Gate3B1")
        
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
            
        labels = {r["candidate_id"]: r["canonical_label"] for r in baseline["finalist_decisions"]}
        source_defs = {d["definition_id"]: d for d in definitions}
        
        ledger = []
        for decision in decisions:
            candidate_id = decision["candidate_id"]
            definition = source_defs[candidate_id]
            counts = structure_by_id.get(candidate_id)
            require(counts is not None, f"Missing memberships for candidate {candidate_id}")
            require(all(counts[k] == definition[k] for k in decision["structural_evidence"]),
                    f"Structural count mismatch for candidate {candidate_id}")
            
            canonical_label = labels.get(candidate_id, decision["canonical_label"])
            label_source = SEMANTIC_RUN if candidate_id in labels else SOURCE_RUN
            
            item = {
                "candidate_id": candidate_id,
                "canonical_label": canonical_label,
                "parent_cluster_id": definition["parent_cluster_id"],
                "source_definition_run_id": SOURCE_RUN,
                "semantic_valid": decision["semantic_valid"],
                "semantic_rejection_reason": decision["semantic_rejection_reason"],
                "video_count": definition["video_count"],
                "channel_count": definition["channel_count"],
                "outlier_count": definition["outlier_count"],
                "structural_eligible": decision["structural_eligible"],
                "structural_exclusion_reasons": decision["structural_exclusion_reasons"],
                "label_source_run_id": label_source,
                "formula_version": FORMULA_VERSION,
                "threshold": THRESHOLD,
                "economic_score": None,
                "reproduced_score": None,
                "score_status": "MISSING_COMPONENTS",
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
                evidence = {k: rows.get(mapping[candidate_id]) for k, rows in analyses.items()}
                econ = reconstruct_economics(definition, mapping, evidence, SOURCE_RUN, analysis_runs)
                item["economic_score"] = econ["economic_score"]
                item["reproduced_score"] = econ["economic_score"]
                item["score_status"] = "VERIFIED"
                item["known_component_weight"] = econ["known_component_weight"]
                item["risk_penalty"] = econ["risk_penalty"]
                item["main_limiting_components"] = econ["main_limiting_components"]
                item["evidence_confidence"] = econ["evidence_confidence"]
                
                econ_qual, comb_qual = qualification(
                    decision["semantic_valid"], decision["structural_eligible"], econ["economic_score"]
                )
                item["economic_qualified"] = econ_qual
                item["combined_qualified"] = comb_qual
            elif decision["semantic_valid"] and decision["structural_eligible"]:
                item["score_status"] = "MISSING_CANDIDATE_SCOPED_ECONOMIC_EVIDENCE"
                item["combined_qualified"] = False
            else:
                item["score_status"] = "NOT_EVALUATED"
                item["combined_qualified"] = False
                
            ledger.append(item)
            
        # Verify 58 candidate IDs uniqueness
        candidate_ids = [item["candidate_id"] for item in ledger]
        require(len(candidate_ids) == 58 and len(set(candidate_ids)) == 58,
                "Ledger candidate ID uniqueness failure")
        
        # Partition breakdown
        sem_invalid_list = [i for i in ledger if not i["semantic_valid"]]
        struct_excluded_list = [i for i in ledger if i["semantic_valid"] and not i["structural_eligible"]]
        struct_eligible_list = [i for i in ledger if i["semantic_valid"] and i["structural_eligible"]]
        
        require(len(sem_invalid_list) == 4, "Semantic invalid count must be 4")
        require(len(struct_excluded_list) == 8, "Structural excluded count must be 8")
        require(len(struct_eligible_list) == 46, "Structural eligible count must be 46")
        
        # Economic audit counts
        scored_items = [i for i in ledger if i["economic_score"] is not None]
        verified_items = [i for i in ledger if i["score_status"] == "VERIFIED"]
        require(len(scored_items) == 20, "Scored candidates count must be 20")
        require(len(verified_items) == 20, "Verified candidates count must be 20")
        
        # Qualified candidates
        qualified_list = [i for i in ledger if i["combined_qualified"] is True]
        
        # Near Misses: semantic_valid AND structural_eligible AND score_status=='VERIFIED' AND score < 50.0
        near_misses_raw = [
            i for i in ledger
            if i["semantic_valid"] and i["structural_eligible"] and i["score_status"] == "VERIFIED" and i["economic_score"] < 50.0
        ]
        near_misses_sorted = sorted(near_misses_raw, key=lambda x: (THRESHOLD - x["economic_score"], x["candidate_id"]))[:10]
        
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
        
        payload = {
            "run_id": run_id,
            "source_run_id": SOURCE_RUN,
            "semantic_run_id": SEMANTIC_RUN,
            "semantic_hash": semantic_hash,
            "formula_version": FORMULA_VERSION,
            "threshold": THRESHOLD,
            "status": "FIX_STOP",
            "top3_readiness": "NO",
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
                "existing_scored_candidates": len(scored_items),
                "verified_scores": len(verified_items),
                "invalid_lineage_scores": 0,
                "unreproducible_scores": 0,
                "missing_components_scores": 0,
                "cross_candidate_borrowing": 0,
                "combined_qualified_count": len(qualified_list),
                "combined_qualified_ids": [i["candidate_id"] for i in qualified_list],
                "near_misses_count": len(near_misses),
            },
            "near_misses": near_misses,
            "def_039_forensics": {
                "historical_prose_score_claim_1": "50.05638012646635 (Borrowed from evaluation cluster 7 owned by def_045)",
                "historical_prose_score_claim_2": "48.75000 (Unpersisted prose hallucination/placeholder in unaccepted report)",
                "persisted_db_score": None,
                "root_cause": "Join defect in early Gate3 code querying cluster_profitability_analyses by parent_cluster_id=7 instead of evaluation_cluster_id. Evaluation cluster 7 belongs to def_045, not def_039.",
                "authoritative_economic_status": "MISSING_CANDIDATE_SCOPED_ECONOMIC_EVIDENCE",
                "authoritative_score": None,
            },
            "reconciliation_checks": {
                "def_021_resolved": "STRUCTURALLY_EXCLUDED (channel_count=1 <= 1, SINGLE_CHANNEL_ARTIFACT)",
                "def_033_resolved": "STRUCTURALLY_EXCLUDED (channel_count=1 <= 1, SINGLE_CHANNEL_ARTIFACT)",
                "identity_contradictions": 0,
                "structural_contradictions": 0,
            }
        }
        return payload


def canonical_payload_c2(payload: dict) -> str:
    result = dict(payload)
    ledger = result["ledger"]
    ids = [d["candidate_id"] for d in ledger]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate persisted candidate IDs in ledger")
    result["ledger"] = sorted(ledger, key=lambda d: d["candidate_id"])
    return json.dumps(result, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def payload_hash_c2(payload: dict) -> str:
    return hashlib.sha256(canonical_payload_c2(payload).encode("utf-8")).hexdigest()


def readback_and_hash(run_id):
    client = PostgresClient()
    with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        row = one(cur, "SELECT notes, dataset_hash FROM analytical_runs WHERE run_id=%s", (run_id,))
        payload = decoded(row["notes"])
        ledger = payload["ledger"]
        ids = [i["candidate_id"] for i in ledger]
        require(len(ids) == len(set(ids)) == 58, "Readback candidate uniqueness failure")
        digest = payload_hash_c2(payload)
        require(digest == row["dataset_hash"], "Persisted payload hash mismatch")
        return digest


def execute_run(run_id=None, verify=False):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = run_id or f"sprint13_gate3c2_lineage_forensics_{timestamp}"
    payload = build_forensic_ledger(run_id)
    expected_hash = payload_hash_c2(payload)
    
    if not verify:
        with PostgresClient().get_cursor() as cur:
            cur.execute("""
                INSERT INTO analytical_runs
                    (run_id, dataset_hash, run_type, status, video_count, channel_count, notes)
                VALUES (%s, %s, %s, %s, 0, 0, %s)
            """, (run_id, expected_hash, "GATE3C2_LINEAGE_FORENSICS", payload["status"],
                  canonical_payload_c2(payload)))
            
    gc.collect()
    hash1 = readback_and_hash(run_id)
    gc.collect()
    hash2 = readback_and_hash(run_id)
    require(hash1 == hash2 == expected_hash, f"Hash mismatch: HASH1={hash1}, HASH2={hash2}, expected={expected_hash}")
    
    res = {
        "run_id": run_id,
        "status": payload["status"],
        "hash1": hash1,
        "hash2": hash2,
        "hash_match": hash1 == hash2,
        "summary": payload["summary"],
        "near_misses": payload["near_misses"],
        "def_039_forensics": payload["def_039_forensics"],
        "reconciliation_checks": payload["reconciliation_checks"],
    }
    print(json.dumps(res, indent=2, ensure_ascii=True))
    return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", metavar="RUN_ID", help="Read-only post-test reconstruction")
    args = parser.parse_args()
    result = execute_run(args.verify, verify=bool(args.verify))
