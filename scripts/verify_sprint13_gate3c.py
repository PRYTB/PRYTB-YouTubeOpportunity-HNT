"""Sprint13 Gate3C State Verifier.

Independently validates the current Gate3C state against all forensic and structural requirements.
SOURCE OF TRUTH: PostgreSQL local (localhost:5433/prytb, user: prytb_app).
"""

import hashlib
import json
import sys
from pathlib import Path

from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analytics.qualified_pool import (
    FORMULA_VERSION,
    THRESHOLD,
    reconstruct_economics,
    semantic_partition,
)
from app.database.postgres_client import PostgresClient
from scripts.sprint13_gate3c2_runner import payload_hash_c2

SOURCE_RUN = "sprint12_gate7_reconciled_20260914_211554"
SEMANTIC_RUN = "sprint13_gate3b1_normalization_closure_20260922"
FORENSIC_RUN_TYPE = "GATE3C2_LINEAGE_FORENSICS"


def decoded(val):
    return json.loads(val) if isinstance(val, str) else val


def main():
    failed_checks = []

    # System status dict
    checks = {
        "candidate_universe": False,
        "semantic_state": False,
        "structural_partition": False,
        "identity_integrity": False,
        "economic_lineage": False,
        "def_039_invariant": False,
        "def_045_reproduction": False,
        "qualified_pool_integrity": False,
        "near_miss_integrity": False,
        "persistence": False,
        "hash_reproducibility": False,
        "hash_sensitivity": False,
        "database_integrity": False,
    }

    client = PostgresClient()

    # Shared DB connection or data fetch
    try:
        # Check database integrity basics / connection
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            # 1. Candidate universe
            cur.execute(
                "SELECT * FROM gate7_semantic_definitions WHERE run_id=%s ORDER BY definition_id",
                (SOURCE_RUN,),
            )
            definitions = cur.fetchall()

            cand_ids = [d["definition_id"] for d in definitions]
            if len(definitions) == 58 and len(set(cand_ids)) == 58:
                checks["candidate_universe"] = True
            else:
                failed_checks.append(
                    f"Candidate universe invalid: count={len(definitions)}, unique={len(set(cand_ids))}"
                )

            # 2. Semantic state
            decisions = semantic_partition(definitions)
            sem_invalid = [
                d["candidate_id"] for d in decisions if not d["semantic_valid"]
            ]
            sem_valid = [
                d["candidate_id"] for d in decisions if d["semantic_valid"]
            ]
            expected_invalid = ["def_043", "def_046", "def_051", "def_052"]
            if len(sem_valid) == 54 and sorted(sem_invalid) == expected_invalid:
                checks["semantic_state"] = True
            else:
                failed_checks.append(
                    f"Semantic state invalid: valid={len(sem_valid)}, invalid={sem_invalid}"
                )

            # 3. Structural partition
            # invalid + excluded + eligible = 58
            struct_excluded = [
                d
                for d in decisions
                if d["semantic_valid"] and not d["structural_eligible"]
            ]
            struct_eligible = [
                d
                for d in decisions
                if d["semantic_valid"] and d["structural_eligible"]
            ]
            overlap = set(d["candidate_id"] for d in struct_excluded).intersection(
                set(d["candidate_id"] for d in struct_eligible)
            )

            if (
                len(decisions) == 58
                and len(sem_invalid) + len(struct_excluded) + len(struct_eligible)
                == 58
                and not overlap
            ):
                checks["structural_partition"] = True
            else:
                failed_checks.append(
                    "Structural partition mismatch or overlapping sets"
                )

            # 4. Identity integrity & Mapping
            cur.execute(
                "SELECT notes FROM analytical_runs WHERE run_id=%s",
                (SOURCE_RUN,),
            )
            source_notes = decoded(cur.fetchone()["notes"])
            mapping_rows = source_notes["top20_evaluation_mapping"]
            mapping = {
                m["definition_id"]: m["evaluation_cluster_id"]
                for m in mapping_rows
            }

            # Fetch forensic run payload from DB
            cur.execute(
                "SELECT run_id, notes, dataset_hash FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
                (FORENSIC_RUN_TYPE,),
            )
            forensic_row = cur.fetchone()
            forensic_notes = decoded(forensic_row["notes"])
            forensic_ledger = {
                item["candidate_id"]: item for item in forensic_notes["ledger"]
            }

            # Validate identities
            def_039_item = forensic_ledger.get("def_039")
            def_045_item = forensic_ledger.get("def_045")
            def_052_item = forensic_ledger.get("def_052")

            identity_ok = True
            if not def_039_item or def_039_item["parent_cluster_id"] != 7:
                identity_ok = False
                failed_checks.append(
                    "def_039 parent_cluster_id identity mismatch"
                )
            if not def_045_item or def_045_item["parent_cluster_id"] != 11 or def_045_item["evaluation_cluster_id"] != 7:
                identity_ok = False
                failed_checks.append(
                    "def_045 parent/evaluation cluster identity mismatch"
                )
            if not def_052_item or def_052_item["semantic_valid"] is not False:
                identity_ok = False
                failed_checks.append("def_052 semantic status mismatch")

            if identity_ok:
                checks["identity_integrity"] = True

            # 5. Economic lineage & Reproduction
            # Fetch analysis tables
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
                k: source_notes["sprint_run_ids"][v] for k, v in run_keys.items()
            }
            analyses = {}
            for name, table in analysis_tables.items():
                cur.execute(
                    sql.SQL(
                        "SELECT * FROM {} WHERE source_cluster_run_id=%s AND run_id=%s ORDER BY cluster_id"
                    ).format(sql.Identifier(table)),
                    (SOURCE_RUN, analysis_runs[name]),
                )
                rows = cur.fetchall()
                for r in rows:
                    r["metrics"] = decoded(r["metrics"])
                analyses[name] = {r["cluster_id"]: r for r in rows}

            source_defs = {d["definition_id"]: d for d in definitions}

            econ_lineage_ok = True
            reproduced_scores = {}
            for cand_id, item in forensic_ledger.items():
                if item["economic_score"] is not None:
                    if cand_id not in mapping:
                        econ_lineage_ok = False
                        failed_checks.append(
                            f"Candidate {cand_id} scored without mapping"
                        )
                        continue
                    definition = source_defs[cand_id]
                    evidence = {
                        k: rows.get(mapping[cand_id])
                        for k, rows in analyses.items()
                    }
                    econ = reconstruct_economics(
                        definition,
                        mapping,
                        evidence,
                        SOURCE_RUN,
                        analysis_runs,
                    )
                    reproduced_scores[cand_id] = econ["economic_score"]
                    if item["formula_version"] != FORMULA_VERSION:
                        econ_lineage_ok = False
                        failed_checks.append(
                            f"Formula version mismatch for {cand_id}"
                        )
                    if abs(item["economic_score"] - econ["economic_score"]) > 1e-9:
                        econ_lineage_ok = False
                        failed_checks.append(
                            f"Score reproduction mismatch for {cand_id}: stored {item['economic_score']} vs repro {econ['economic_score']}"
                        )

            if econ_lineage_ok:
                checks["economic_lineage"] = True

            # 6. Known forensic invariants
            def_039_ok = (
                def_039_item["economic_score"] is None
                and def_039_item["score_status"] == "MISSING_CANDIDATE_SCOPED_ECONOMIC_EVIDENCE"
            )
            if def_039_ok:
                checks["def_039_invariant"] = True
            else:
                failed_checks.append("def_039 score invariant failed (must be None/MISSING)")

            def_045_repro_score = reproduced_scores.get("def_045")
            expected_def_045_score = 50.05638012646635
            if (
                def_045_repro_score is not None
                and abs(def_045_repro_score - expected_def_045_score) < 1e-5
                and abs(def_045_item["economic_score"] - expected_def_045_score) < 1e-5
                and abs(def_045_item["risk_penalty"] - 1.74) < 1e-5
            ):
                checks["def_045_reproduction"] = True
            else:
                failed_checks.append(
                    f"def_045 reproduction failed: got {def_045_repro_score}, expected {expected_def_045_score}"
                )

            # 7. Qualified pool integrity
            qual_ok = True
            qualified_items = [
                i for i in forensic_notes["ledger"] if i["combined_qualified"] is True
            ]
            for item in qualified_items:
                if not (
                    item["semantic_valid"]
                    and item["structural_eligible"]
                    and item["score_status"] == "VERIFIED"
                    and item["economic_score"] >= THRESHOLD
                ):
                    qual_ok = False
                    failed_checks.append(
                        f"Candidate {item['candidate_id']} qualified invalidly"
                    )

            if len(qualified_items) == 1 and qualified_items[0]["candidate_id"] == "def_045" and qual_ok:
                checks["qualified_pool_integrity"] = True
            else:
                failed_checks.append(
                    f"Qualified pool count/candidate mismatch: count={len(qualified_items)}"
                )

            # 8. Near Miss integrity
            near_misses = forensic_notes["near_misses"]
            near_miss_ok = True
            for nm in near_misses:
                cid = nm["candidate_id"]
                item = forensic_ledger[cid]
                if not (
                    item["semantic_valid"]
                    and item["structural_eligible"]
                    and item["score_status"] == "VERIFIED"
                    and item["economic_score"] < THRESHOLD
                ):
                    near_miss_ok = False
                    failed_checks.append(
                        f"Near miss candidate {cid} violates criteria"
                    )

            if near_miss_ok and len(near_misses) == 10:
                checks["near_miss_integrity"] = True
            else:
                failed_checks.append("Near miss count or criteria failure")

            # 9. Persistence
            persistence_ok = (
                len(forensic_notes["ledger"]) == 58
                and len(set(i["candidate_id"] for i in forensic_notes["ledger"])) == 58
                and forensic_notes["summary"]["total_candidates"] == 58
            )
            if persistence_ok:
                checks["persistence"] = True
            else:
                failed_checks.append("Forensic ledger persistence mismatch")

            # 10. Hash reproducibility (Dual fresh DB read)
            cur.execute(
                "SELECT notes, dataset_hash FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
                (FORENSIC_RUN_TYPE,),
            )
            row_a = cur.fetchone()
            notes_a = decoded(row_a["notes"])
            hash1 = payload_hash_c2(notes_a)

    except Exception as e:
        failed_checks.append(f"DB Error during connection 1: {str(e)}")
        hash1 = None

    # Connection 2: HASH2
    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT notes, dataset_hash FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
                (FORENSIC_RUN_TYPE,),
            )
            row_b = cur.fetchone()
            notes_b = decoded(row_b["notes"])
            hash2 = payload_hash_c2(notes_b)
    except Exception as e:
        failed_checks.append(f"DB Error during connection 2: {str(e)}")
        hash2 = None

    if hash1 and hash2 and hash1 == hash2 and hash1 == row_a["dataset_hash"]:
        checks["hash_reproducibility"] = True
    else:
        failed_checks.append(f"Hash reproducibility failed: HASH1={hash1}, HASH2={hash2}")

    # Hash sensitivity check
    if hash1 and notes_a:
        mutated_notes = json.loads(json.dumps(notes_a))
        for item in mutated_notes["ledger"]:
            if item["candidate_id"] == "def_045":
                item["economic_score"] = 55.00000
                break
        mutated_hash = payload_hash_c2(mutated_notes)
        if mutated_hash != hash1:
            checks["hash_sensitivity"] = True
        else:
            failed_checks.append("Hash sensitivity check failed: mutation produced same hash")

    # 11. Database integrity
    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT status FROM analytical_runs WHERE run_id=%s", (SOURCE_RUN,))
            source_status = cur.fetchone()["status"]

            cur.execute("SELECT COUNT(*) FROM gate7_semantic_definitions WHERE run_id=%s", (SOURCE_RUN,))
            def_cnt = cur.fetchone()["count"]

            if source_status == "SPRINT12_FINAL_ANALYTICS_APPROVED" and def_cnt == 58:
                checks["database_integrity"] = True
            else:
                failed_checks.append("Database integrity check failed (canonical modified or counts mismatch)")
    except Exception as e:
        failed_checks.append(f"DB Error during integrity check: {str(e)}")

    # Calculate overall status
    all_passed = all(checks.values()) and len(failed_checks) == 0

    print("PRYTB GATE3C VERIFIER\n")
    for key, val in checks.items():
        print(f"{key}: {'PASS' if val else 'FAIL'}")

    print("\nfailed_checks:")
    if failed_checks:
        for fc in failed_checks:
            print(f"- {fc}")
    else:
        print("- none")

    print(f"\nFINAL_STATUS: {'PASS' if all_passed else 'FAIL'}")
    print(f"EXIT_CODE: {0 if all_passed else 1}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
