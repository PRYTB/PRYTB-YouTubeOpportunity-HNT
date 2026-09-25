"""Sprint13 Gate3E Verifier.

Independently validates the Gate3E state against all criteria directly from PostgreSQL.
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
from scripts.sprint13_gate3e_runner import payload_hash_3e, SOURCE_RUN, SEMANTIC_RUN

RUN_TYPE_3E = "GATE3E_ECONOMIC_EVIDENCE"


def decoded(val):
    return json.loads(val) if isinstance(val, str) else val


def main():
    failed_checks = []

    checks = {
        "gate3d_precondition": False,
        "candidate_universe": False,
        "economic_disposition": False,
        "resolution_attempt_audit": False,
        "evidence_lineage": False,
        "score_reproduction": False,
        "qualification_integrity": False,
        "near_miss_integrity": False,
        "safe_integration_suite": False,
        "persistence": False,
        "hash_reproducibility": False,
        "database_integrity": False,
    }

    hash1 = None
    hash2 = None
    row_3e = None
    verified_count = 0
    unevaluable_count = 0
    qualified_count = 0
    top3_readiness = "NO"

    # 1. Gate3D precondition
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts" / "verify_sprint13_gate3d.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and "FINAL_STATUS: PASS" in proc.stdout:
            checks["gate3d_precondition"] = True
        else:
            failed_checks.append("Gate3D precondition failed")
    except Exception as e:
        failed_checks.append(f"Gate3D precondition execution error: {str(e)}")

    # 1b. SAFE integration test suite execution
    try:
        proc_tests = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "tests/integration/test_sprint13_gate3.py",
                "tests/integration/test_sprint13_gate2c.py",
                "tests/integration/test_sprint13_gate2b.py",
                "tests/integration/test_sprint13_gate2a.py",
                "tests/integration/test_sprint13_gate2.py",
                "-q",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc_tests.returncode == 0:
            checks["safe_integration_suite"] = True
        else:
            failed_checks.append(f"SAFE integration suite failed: {proc_tests.stderr or proc_tests.stdout}")
    except Exception as e:
        failed_checks.append(f"SAFE integration suite execution error: {str(e)}")

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

            # Read latest Gate3E run from DB
            cur.execute(
                "SELECT run_id, notes, dataset_hash FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
                (RUN_TYPE_3E,),
            )
            row_3e = cur.fetchone()
            if not row_3e:
                failed_checks.append("No Gate3E analytical run found")
                payload_3e = None
            else:
                payload_3e = decoded(row_3e["notes"])

            if payload_3e:
                ledger = payload_3e["ledger"]
                ledger_by_id = {i["candidate_id"]: i for i in ledger}

                # 3. Economic disposition for all 46 eligible candidates
                dispositions = {i["candidate_id"]: i.get("disposition") for i in ledger}
                eligible_dispositions = [dispositions[cid] for cid in eligible_ids]

                all_disposed = all(
                    d in ("VERIFIED", "LEGITIMATELY_UNEVALUABLE") for d in eligible_dispositions
                )
                verified_items = [i for i in ledger if i["candidate_id"] in eligible_ids and i["disposition"] == "VERIFIED"]
                unevaluable_items = [i for i in ledger if i["candidate_id"] in eligible_ids and i["disposition"] == "LEGITIMATELY_UNEVALUABLE"]

                verified_count = len(verified_items)
                unevaluable_count = len(unevaluable_items)

                if len(ledger) == 58 and all_disposed and (verified_count + unevaluable_count == 46):
                    checks["economic_disposition"] = True
                else:
                    failed_checks.append(
                        f"Economic disposition incomplete or invalid: verified={verified_count}, unevaluable={unevaluable_count}, sum={verified_count+unevaluable_count}"
                    )

                # 3b. Resolution attempt audit for all 28 missing candidates
                resolution_ok = True
                for item in unevaluable_items:
                    cid = item["candidate_id"]
                    attempt = item.get("resolution_attempt")
                    if not attempt or not isinstance(attempt, dict) or not attempt.get("attempted"):
                        resolution_ok = False
                        failed_checks.append(f"Candidate {cid} has no documented resolution attempt")
                    elif not attempt.get("reason"):
                        resolution_ok = False
                        failed_checks.append(f"Candidate {cid} resolution attempt missing explicit reason")

                if resolution_ok:
                    checks["resolution_attempt_audit"] = True
                else:
                    failed_checks.append("Resolution attempt audit failed for missing candidates")

                # Fetch analysis tables for evidence lineage & score reproduction
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

                    if item["disposition"] == "VERIFIED":
                        if cid not in mapping:
                            lineage_ok = False
                            failed_checks.append(f"Candidate {cid} verified without candidate-scoped evaluation mapping")
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
                    elif item["disposition"] in ("LEGITIMATELY_UNEVALUABLE", "SEMANTICALLY_OR_STRUCTURALLY_INELIGIBLE"):
                        if score is not None:
                            repro_ok = False
                            failed_checks.append(f"Candidate {cid} has non-null score but disposition is {item['disposition']}")

                if lineage_ok:
                    checks["evidence_lineage"] = True
                if repro_ok:
                    checks["score_reproduction"] = True

                # Independent reconstruction of qualified pool & near misses
                reconstructed_qualified = [
                    item for item in ledger
                    if item["semantic_valid"] is True
                    and item["structural_eligible"] is True
                    and item["disposition"] == "VERIFIED"
                    and item["economic_score"] is not None
                    and item["economic_score"] >= THRESHOLD
                ]
                qualified_count = len(reconstructed_qualified)

                # Qualification integrity check
                qual_ok = True
                persisted_qualified = [i for i in ledger if i["combined_qualified"] is True]
                if len(persisted_qualified) != qualified_count:
                    qual_ok = False
                    failed_checks.append(
                        f"Persisted vs reconstructed qualified count mismatch: {len(persisted_qualified)} vs {qualified_count}"
                    )

                for item in persisted_qualified:
                    if not (
                        item["semantic_valid"] is True
                        and item["structural_eligible"] is True
                        and item["disposition"] == "VERIFIED"
                        and item["economic_score"] is not None
                        and item["economic_score"] >= THRESHOLD
                    ):
                        qual_ok = False
                        failed_checks.append(f"Candidate {item['candidate_id']} falsely qualified in ledger")

                if qual_ok and payload_3e["summary"]["combined_qualified_count"] == qualified_count:
                    checks["qualification_integrity"] = True
                else:
                    failed_checks.append("Qualification integrity failure")

                top3_readiness = "YES" if qualified_count >= 3 else "NO"

                # Independent reconstruction of Near Misses
                reconstructed_near_misses_raw = [
                    item for item in ledger
                    if item["semantic_valid"] is True
                    and item["structural_eligible"] is True
                    and item["disposition"] == "VERIFIED"
                    and item["economic_score"] is not None
                    and item["economic_score"] < THRESHOLD
                ]
                reconstructed_near_misses_sorted = sorted(
                    reconstructed_near_misses_raw,
                    key=lambda x: (THRESHOLD - x["economic_score"], x["candidate_id"]),
                )[:10]

                near_miss_ok = True
                for forbidden_id in ("def_021", "def_034", "def_051"):
                    if any(nm["candidate_id"] == forbidden_id for nm in reconstructed_near_misses_sorted):
                        near_miss_ok = False
                        failed_checks.append(f"Forbidden candidate {forbidden_id} in reconstructed Near Misses")
                    if any(nm["candidate_id"] == forbidden_id for nm in payload_3e["near_misses"]):
                        near_miss_ok = False
                        failed_checks.append(f"Forbidden candidate {forbidden_id} in persisted Near Misses")

                if near_miss_ok and len(payload_3e["near_misses"]) == len(reconstructed_near_misses_sorted):
                    checks["near_miss_integrity"] = True
                else:
                    failed_checks.append("Near miss integrity failure")

                # Persistence 58/58
                if len(ledger) == 58 and len(set(ledger_by_id.keys())) == 58:
                    checks["persistence"] = True
                else:
                    failed_checks.append("Persistence 58/58 check failed")

                # Hash reproducibility (Connection 1: hash1)
                hash1 = payload_hash_3e(payload_3e)

    except Exception as e:
        failed_checks.append(f"DB Error during connection 1: {str(e)}")
        hash1 = None

    # Connection 2: HASH2
    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT notes, dataset_hash FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
                (RUN_TYPE_3E,),
            )
            row_3e_b = cur.fetchone()
            notes_3e_b = decoded(row_3e_b["notes"])
            hash2 = payload_hash_3e(notes_3e_b)
    except Exception as e:
        failed_checks.append(f"DB Error during connection 2: {str(e)}")
        hash2 = None

    if hash1 and hash2 and hash1 == hash2 and hash1 == row_3e["dataset_hash"]:
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

    print("PRYTB GATE3E VERIFIER\n")
    print(f"gate3d_precondition: {'PASS' if checks['gate3d_precondition'] else 'FAIL'}")
    print(f"candidate_universe: {'PASS' if checks['candidate_universe'] else 'FAIL'}")
    print(f"economic_disposition: {'PASS' if checks['economic_disposition'] else 'FAIL'}")
    print(f"resolution_attempt_audit: {'PASS' if checks['resolution_attempt_audit'] else 'FAIL'}")
    print(f"evidence_lineage: {'PASS' if checks['evidence_lineage'] else 'FAIL'}")
    print(f"score_reproduction: {'PASS' if checks['score_reproduction'] else 'FAIL'}")
    print(f"qualification_integrity: {'PASS' if checks['qualification_integrity'] else 'FAIL'}")
    print(f"near_miss_integrity: {'PASS' if checks['near_miss_integrity'] else 'FAIL'}")
    print(f"safe_integration_suite: {'PASS' if checks['safe_integration_suite'] else 'FAIL'}")
    print(f"persistence: {'PASS' if checks['persistence'] else 'FAIL'}")
    print(f"hash_reproducibility: {'PASS' if checks['hash_reproducibility'] else 'FAIL'}")
    print(f"database_integrity: {'PASS' if checks['database_integrity'] else 'FAIL'}\n")

    print(f"verified_count: {verified_count}")
    print(f"unevaluable_count: {unevaluable_count}")
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
