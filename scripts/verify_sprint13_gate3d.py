"""Sprint13 Gate3D Verifier.

Independently validates the Gate3D state against all criteria directly from PostgreSQL.
"""

import json
import sys
import subprocess
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
from scripts.sprint13_gate3d_runner import payload_hash_3d, SOURCE_RUN, SEMANTIC_RUN

RUN_TYPE_3D = "GATE3D_ECONOMIC_COVERAGE"


def decoded(val):
    return json.loads(val) if isinstance(val, str) else val


def main():
    failed_checks = []

    checks = {
        "gate3c_precondition": False,
        "candidate_universe": False,
        "economic_coverage": False,
        "score_reproduction": False,
        "lineage_integrity": False,
        "qualification_integrity": False,
        "near_miss_integrity": False,
        "persistence": False,
        "hash_reproducibility": False,
        "database_integrity": False,
    }

    hash1 = None
    hash2 = None
    row_3d = None
    qualified_count = 0
    top3_readiness = "NO"

    # 1. Gate3C precondition
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts" / "verify_sprint13_gate3c.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and "FINAL_STATUS: PASS" in proc.stdout:
            checks["gate3c_precondition"] = True
        else:
            failed_checks.append("Gate3C precondition failed")
    except Exception as e:
        failed_checks.append(f"Gate3C precondition execution error: {str(e)}")

    client = PostgresClient()

    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            # 2. Candidate universe & structural partition
            cur.execute(
                "SELECT * FROM gate7_semantic_definitions WHERE run_id=%s ORDER BY definition_id",
                (SOURCE_RUN,),
            )
            definitions = cur.fetchall()

            cand_ids = [d["definition_id"] for d in definitions]
            if len(definitions) == 58 and len(set(cand_ids)) == 58:
                checks["candidate_universe"] = True
            else:
                failed_checks.append("Candidate universe != 58 or duplicate IDs")

            decisions = semantic_partition(definitions)
            struct_eligible = [
                d for d in decisions if d["semantic_valid"] and d["structural_eligible"]
            ]
            eligible_ids = set(d["candidate_id"] for d in struct_eligible)

            if len(struct_eligible) != 46:
                failed_checks.append(f"Structurally eligible count = {len(struct_eligible)}, expected 46")

            # Read latest Gate3D run from DB
            cur.execute(
                "SELECT run_id, notes, dataset_hash FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
                (RUN_TYPE_3D,),
            )
            row_3d = cur.fetchone()
            if not row_3d:
                failed_checks.append("No Gate3D analytical run found")
                payload_3d = None
            else:
                payload_3d = decoded(row_3d["notes"])

            if payload_3d:
                ledger = payload_3d["ledger"]
                ledger_by_id = {i["candidate_id"]: i for i in ledger}

                # 3 & 4. Economic coverage & disposition for all 46 eligible
                dispositions = {i["candidate_id"]: i.get("disposition") for i in ledger}
                eligible_dispositions = [dispositions[cid] for cid in eligible_ids]

                all_disposed = all(
                    d in ("VERIFIED_SCORE", "LEGITIMATELY_UNEVALUABLE") for d in eligible_dispositions
                )
                if len(ledger) == 58 and all_disposed:
                    checks["economic_coverage"] = True
                else:
                    failed_checks.append("Economic coverage incomplete or invalid disposition present")

                # Fetch analysis tables for score reproduction
                cur.execute("SELECT notes FROM analytical_runs WHERE run_id=%s", (SOURCE_RUN,))
                source_notes = decoded(cur.fetchone()["notes"])
                mapping_rows = source_notes["top20_evaluation_mapping"]
                mapping = {m["definition_id"]: m["evaluation_cluster_id"] for m in mapping_rows}

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
                analysis_runs = {k: source_notes["sprint_run_ids"][v] for k, v in run_keys.items()}
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

                repro_ok = True
                lineage_ok = True

                for item in ledger:
                    cid = item["candidate_id"]
                    score = item["economic_score"]

                    if item["score_status"] == "VERIFIED":
                        if cid not in mapping:
                            lineage_ok = False
                            failed_checks.append(f"Candidate {cid} verified without mapping")
                            continue

                        def_row = source_defs[cid]
                        evidence = {k: rows.get(mapping[cid]) for k, rows in analyses.items()}
                        econ = reconstruct_economics(def_row, mapping, evidence, SOURCE_RUN, analysis_runs)

                        if abs(score - econ["economic_score"]) > 1e-5:
                            repro_ok = False
                            failed_checks.append(
                                f"Candidate {cid} score reproduction mismatch: stored {score} vs repro {econ['economic_score']}"
                            )

                        if item["formula_version"] != FORMULA_VERSION:
                            lineage_ok = False
                            failed_checks.append(f"Formula version mismatch for {cid}")
                    elif item["score_status"] in ("MISSING_CANDIDATE_SCOPED_ECONOMIC_EVIDENCE", "NOT_EVALUATED"):
                        if score is not None:
                            repro_ok = False
                            failed_checks.append(f"Candidate {cid} has score but status is {item['score_status']}")

                if repro_ok:
                    checks["score_reproduction"] = True
                if lineage_ok:
                    checks["lineage_integrity"] = True

                # Qualification integrity & pool rebuild
                qual_ok = True
                qualified_items = [i for i in ledger if i["combined_qualified"] is True]
                qualified_count = len(qualified_items)

                for item in qualified_items:
                    if not (
                        item["semantic_valid"]
                        and item["structural_eligible"]
                        and item["score_status"] == "VERIFIED"
                        and item["economic_score"] >= THRESHOLD
                    ):
                        qual_ok = False
                        failed_checks.append(f"Candidate {item['candidate_id']} falsely qualified")

                if qual_ok and payload_3d["summary"]["combined_qualified_count"] == qualified_count:
                    checks["qualification_integrity"] = True
                else:
                    failed_checks.append("Qualification integrity failure")

                top3_readiness = "YES" if qualified_count >= 3 else "NO"

                # Near Miss integrity
                near_misses = payload_3d["near_misses"]
                near_miss_ok = True
                for nm in near_misses:
                    cid = nm["candidate_id"]
                    item = ledger_by_id[cid]
                    if not (
                        item["semantic_valid"]
                        and item["structural_eligible"]
                        and item["score_status"] == "VERIFIED"
                        and item["economic_score"] < THRESHOLD
                    ):
                        near_miss_ok = False
                        failed_checks.append(f"Near miss candidate {cid} violates criteria")

                if near_miss_ok and len(near_misses) <= 10:
                    checks["near_miss_integrity"] = True
                else:
                    failed_checks.append("Near miss integrity failure")

                # Persistence
                if len(ledger) == 58 and len(set(ledger_by_id.keys())) == 58:
                    checks["persistence"] = True
                else:
                    failed_checks.append("Persistence 58/58 check failed")

                # Hash reproducibility (Connection 1: hash1)
                hash1 = payload_hash_3d(payload_3d)

    except Exception as e:
        failed_checks.append(f"DB Error during connection 1: {str(e)}")
        hash1 = None

    # Connection 2: HASH2
    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT notes, dataset_hash FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
                (RUN_TYPE_3D,),
            )
            row_3d_b = cur.fetchone()
            notes_3d_b = decoded(row_3d_b["notes"])
            hash2 = payload_hash_3d(notes_3d_b)
    except Exception as e:
        failed_checks.append(f"DB Error during connection 2: {str(e)}")
        hash2 = None

    if hash1 and hash2 and hash1 == hash2 and hash1 == row_3d["dataset_hash"]:
        checks["hash_reproducibility"] = True
    else:
        failed_checks.append(f"Hash reproducibility failed: HASH1={hash1}, HASH2={hash2}")

    # Database integrity
    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT status FROM analytical_runs WHERE run_id=%s", (SOURCE_RUN,))
            source_status = cur.fetchone()["status"]
            cur.execute("SELECT COUNT(*) FROM gate7_semantic_definitions WHERE run_id=%s", (SOURCE_RUN,))
            def_cnt = cur.fetchone()["count"]

            if source_status == "SPRINT12_FINAL_ANALYTICS_APPROVED" and def_cnt == 58:
                checks["database_integrity"] = True
            else:
                failed_checks.append("Database integrity check failed")
    except Exception as e:
        failed_checks.append(f"DB Error during database integrity check: {str(e)}")

    all_passed = all(checks.values()) and len(failed_checks) == 0

    print("PRYTB GATE3D VERIFIER\n")
    print(f"gate3c_precondition: {'PASS' if checks['gate3c_precondition'] else 'FAIL'}")
    print(f"candidate_universe: {'PASS' if checks['candidate_universe'] else 'FAIL'}")
    print(f"economic_coverage: {'PASS' if checks['economic_coverage'] else 'FAIL'}")
    print(f"score_reproduction: {'PASS' if checks['score_reproduction'] else 'FAIL'}")
    print(f"lineage_integrity: {'PASS' if checks['lineage_integrity'] else 'FAIL'}")
    print(f"qualification_integrity: {'PASS' if checks['qualification_integrity'] else 'FAIL'}")
    print(f"near_miss_integrity: {'PASS' if checks['near_miss_integrity'] else 'FAIL'}")
    print(f"persistence: {'PASS' if checks['persistence'] else 'FAIL'}")
    print(f"hash_reproducibility: {'PASS' if checks['hash_reproducibility'] else 'FAIL'}")
    print(f"database_integrity: {'PASS' if checks['database_integrity'] else 'FAIL'}\n")

    print(f"qualified_count: {qualified_count}")
    print(f"top3_readiness: {top3_readiness}\n")

    print("failed_checks:")
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
