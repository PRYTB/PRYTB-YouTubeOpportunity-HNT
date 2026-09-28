"""Sprint13 Gate3F Economic Backfill Verifier.

Independently validates Gate3F backfill results and integrity.
"""

import json
import sys
import subprocess
from pathlib import Path
import pytest

from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analytics.benchmark_provider import PostgresBenchmarkProvider
from app.analytics.revenue_geography_engine import RevenueGeographyEngine
from app.analytics.market_structure_engine import MarketStructureEngine
from app.analytics.production_risk_engine import ProductionRiskEngine
from app.analytics.profitability_engine import ProfitabilityEngine
from app.analytics.qualified_pool import (
    FORMULA_VERSION,
    THRESHOLD,
    reconstruct_economics,
    semantic_partition,
)
from app.database.postgres_client import PostgresClient
from scripts.sprint13_gate3f_runner import payload_hash_3f, SOURCE_RUN, SEMANTIC_RUN

RUN_TYPE_3F = "GATE3F_ECONOMIC_BACKFILL"


def decoded(val):
    return json.loads(val) if isinstance(val, str) else val


def main():
    failed_checks = []

    checks = {
        "gate3e_precondition": False,
        "candidate_universe": False,
        "backfill_attempted_audit": False,
        "lineage_integrity": False,
        "no_borrowed_scores": False,
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
    row_3f = None
    backfill_candidates = 28
    backfill_attempted = 0
    newly_verified = 0
    still_unevaluable = 0
    verified_total = 0
    unevaluable_total = 0
    qualified_count = 0
    top3_readiness = "NO"

    # 1. Gate3E precondition
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts" / "verify_sprint13_gate3e.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and "FINAL_STATUS: PASS" in proc.stdout:
            checks["gate3e_precondition"] = True
        else:
            failed_checks.append("Gate3E precondition failed")
    except Exception as e:
        failed_checks.append(f"Gate3E precondition execution error: {str(e)}")

    # 2. SAFE integration test suite execution
    safe_discovered = 0
    safe_executed = 0
    safe_passed = 0
    safe_failed = 0
    live_discovered = 0
    live_executed = 0
    try:
        class CollectPlugin:
            def __init__(self):
                self.items = []
            def pytest_collection_modifyitems(self, session, config, items):
                self.items = list(items)

        collect_plugin = CollectPlugin()
        pytest.main(["--collect-only", "-q", "--disable-warnings"], plugins=[collect_plugin])

        safe_nodeids = []
        live_nodeids = []
        for item in collect_plugin.items:
            is_in_integration_dir = "tests/integration/" in item.nodeid.replace("\\", "/")
            has_integration_mark = any(m.name == "integration" for m in item.iter_markers())
            is_live = any(m.name == "live_youtube" for m in item.iter_markers())

            if is_in_integration_dir or has_integration_mark:
                if is_live:
                    live_nodeids.append(item.nodeid)
                else:
                    safe_nodeids.append(item.nodeid)

        safe_discovered = len(safe_nodeids)
        live_discovered = len(live_nodeids)

        if safe_discovered != 143:
            failed_checks.append(f"SAFE discovered count mismatch: expected 143, got {safe_discovered}")
        if live_discovered != 2:
            failed_checks.append(f"LIVE discovered count mismatch: expected 2, got {live_discovered}")

        if safe_discovered == 143:
            class RunPlugin:
                def __init__(self):
                    self.passed = 0
                    self.failed = 0
                    self.executed = 0
                def pytest_runtest_logreport(self, report):
                    if report.when == "call":
                        self.executed += 1
                        if report.passed:
                            self.passed += 1
                        elif report.failed:
                            self.failed += 1

            run_plugin = RunPlugin()
            pytest.main(["-q", "--disable-warnings"] + safe_nodeids, plugins=[run_plugin])

            safe_executed = run_plugin.executed
            safe_passed = run_plugin.passed
            safe_failed = run_plugin.failed
            live_executed = 0

            if safe_executed == 143 and safe_passed == 143 and safe_failed == 0 and live_executed == 0:
                checks["safe_integration_suite"] = True
            else:
                failed_checks.append(
                    f"SAFE integration suite execution mismatch: executed={safe_executed}, passed={safe_passed}, failed={safe_failed}"
                )
    except Exception as e:
        failed_checks.append(f"SAFE integration suite execution error: {str(e)}")

    client = PostgresClient()

    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            # 3. Candidate universe & structural partition
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

            # Read latest Gate3F run from DB
            cur.execute(
                "SELECT run_id, notes, dataset_hash FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
                (RUN_TYPE_3F,),
            )
            row_3f = cur.fetchone()
            if not row_3f:
                failed_checks.append("No Gate3F analytical run found")
                payload_3f = None
            else:
                payload_3f = decoded(row_3f["notes"])

            if payload_3f:
                ledger = payload_3f["ledger"]
                ledger_by_id = {i["candidate_id"]: i for i in ledger}

                verified_items = [i for i in ledger if i["candidate_id"] in eligible_ids and i["disposition"] == "VERIFIED"]
                unevaluable_items = [i for i in ledger if i["candidate_id"] in eligible_ids and i["disposition"] == "LEGITIMATELY_UNEVALUABLE"]

                verified_total = len(verified_items)
                unevaluable_total = len(unevaluable_items)

                attempts = payload_3f.get("backfill_attempts", [])
                backfill_attempted = len(attempts)
                newly_verified = payload_3f["summary"].get("newly_verified", 0)
                still_unevaluable = payload_3f["summary"].get("still_unevaluable", 0)

                if backfill_attempted == 28 and newly_verified == 28 and still_unevaluable == 0:
                    checks["backfill_attempted_audit"] = True
                else:
                    failed_checks.append(
                        f"Backfill audit mismatch: attempted={backfill_attempted}, newly_verified={newly_verified}, still_unevaluable={still_unevaluable}"
                    )

                # Fetch evidence mapping & engine dependencies
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

                bench_provider = PostgresBenchmarkProvider(repository=None)
                rev_engine = RevenueGeographyEngine(benchmark_provider=bench_provider)
                market_engine = MarketStructureEngine()
                prod_engine = ProductionRiskEngine()
                prof_engine = ProfitabilityEngine(benchmark_provider=bench_provider)

                repro_ok = True
                lineage_ok = True
                no_borrowing_ok = True

                for item in ledger:
                    cid = item["candidate_id"]
                    score = item["economic_score"]

                    if item["disposition"] == "VERIFIED":
                        if item["formula_version"] != FORMULA_VERSION:
                            lineage_ok = False
                            failed_checks.append(f"Formula version mismatch for {cid}")

                        if cid in mapping:
                            # Top 18 candidate-mapped candidate
                            def_row = source_defs[cid]
                            evidence = {k: rows.get(mapping[cid]) for k, rows in analyses.items()}
                            econ = reconstruct_economics(def_row, mapping, evidence, SOURCE_RUN, analysis_runs)

                            if abs(score - econ["economic_score"]) > 1e-5:
                                repro_ok = False
                                failed_checks.append(
                                    f"Candidate {cid} score reproduction mismatch: stored {score} vs repro {econ['economic_score']}"
                                )
                        else:
                            # Candidate-scoped backfill candidate!
                            cur.execute(
                                """
                                SELECT v.*, c.country AS channel_country, c.published_at AS channel_published_at
                                FROM gate7_semantic_memberships m
                                JOIN videos v ON v.video_id = m.video_id
                                LEFT JOIN channels c ON c.channel_id = v.channel_id
                                WHERE m.run_id = %s AND m.definition_id = %s
                                """,
                                (SOURCE_RUN, cid),
                            )
                            v_rows = cur.fetchall()

                            cur.execute(
                                """
                                SELECT DISTINCT c.*
                                FROM gate7_semantic_memberships m
                                JOIN videos v ON v.video_id = m.video_id
                                JOIN channels c ON c.channel_id = v.channel_id
                                WHERE m.run_id = %s AND m.definition_id = %s
                                """,
                                (SOURCE_RUN, cid),
                            )
                            c_rows = cur.fetchall()

                            cur.execute(
                                """
                                SELECT o.*
                                FROM gate7_semantic_memberships m
                                JOIN video_outlier_analyses o ON o.video_id = m.video_id AND o.run_id = m.run_id
                                WHERE m.run_id = %s AND m.definition_id = %s
                                """,
                                (SOURCE_RUN, cid),
                            )
                            o_rows = cur.fetchall()

                            cluster_info = {
                                "cluster_id": 1,
                                "niche": "Tech",
                                "subniche": source_defs[cid]["normalized_intent"],
                                "microniche": source_defs[cid]["normalized_intent"],
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
                                run_id=f"gate3f_backfill_{cid}",
                                cluster_id=1,
                                niche="Tech",
                                subniche=source_defs[cid]["normalized_intent"],
                                microniche=source_defs[cid]["normalized_intent"],
                                cluster_videos=v_rows,
                                market_structure=market_res.clusters[0],
                                production_risk=prod_res.clusters[0],
                                source_cluster_run_id=SOURCE_RUN,
                            )

                            repro_score = float(prof_analysis.profitability_score)
                            if abs(score - repro_score) > 1e-5:
                                repro_ok = False
                                failed_checks.append(
                                    f"Candidate-scoped backfill score mismatch for {cid}: stored {score} vs repro {repro_score}"
                                )

                            parent_cid = source_defs[cid]["parent_cluster_id"]
                            if parent_cid in analyses["profitability"]:
                                parent_prof_score = float(analyses["profitability"][parent_cid]["metrics"]["profitability_score"])
                                if abs(score - parent_prof_score) < 1e-5:
                                    no_borrowing_ok = False
                                    failed_checks.append(
                                        f"Candidate {cid} score matches parent cluster {parent_cid} score ({score}), potential score borrowing!"
                                    )

                if lineage_ok:
                    checks["lineage_integrity"] = True
                if repro_ok:
                    checks["score_reproduction"] = True
                if no_borrowing_ok:
                    checks["no_borrowed_scores"] = True

                # Qualification integrity check
                reconstructed_qualified = [
                    item for item in ledger
                    if item["semantic_valid"] is True
                    and item["structural_eligible"] is True
                    and item["disposition"] == "VERIFIED"
                    and item["economic_score"] is not None
                    and item["economic_score"] >= THRESHOLD
                ]
                qualified_count = len(reconstructed_qualified)

                qual_ok = True
                persisted_qualified = [i for i in ledger if i["combined_qualified"] is True]
                if len(persisted_qualified) != qualified_count:
                    qual_ok = False
                    failed_checks.append(
                        f"Persisted vs reconstructed qualified count mismatch: {len(persisted_qualified)} vs {qualified_count}"
                    )

                if qual_ok and payload_3f["summary"]["combined_qualified_count"] == qualified_count:
                    checks["qualification_integrity"] = True
                else:
                    failed_checks.append("Qualification integrity failure")

                top3_readiness = "YES" if qualified_count >= 3 else "NO"

                # Near Miss integrity check
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
                    if any(nm["candidate_id"] == forbidden_id for nm in payload_3f["near_misses"]):
                        near_miss_ok = False
                        failed_checks.append(f"Forbidden candidate {forbidden_id} in persisted Near Misses")

                if near_miss_ok and len(payload_3f["near_misses"]) == len(reconstructed_near_misses_sorted):
                    checks["near_miss_integrity"] = True
                else:
                    failed_checks.append("Near miss integrity failure")

                # Persistence 58/58
                if len(ledger) == 58 and len(set(ledger_by_id.keys())) == 58:
                    checks["persistence"] = True
                else:
                    failed_checks.append("Persistence 58/58 check failed")

                # Hash reproducibility (Connection 1: hash1)
                hash1 = payload_hash_3f(payload_3f)

    except Exception as e:
        failed_checks.append(f"DB Error during connection 1: {str(e)}")
        hash1 = None

    # Connection 2: HASH2
    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT notes, dataset_hash FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
                (RUN_TYPE_3F,),
            )
            row_3f_b = cur.fetchone()
            notes_3f_b = decoded(row_3f_b["notes"])
            hash2 = payload_hash_3f(notes_3f_b)
    except Exception as e:
        failed_checks.append(f"DB Error during connection 2: {str(e)}")
        hash2 = None

    if hash1 and hash2 and hash1 == hash2 and hash1 == row_3f["dataset_hash"]:
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

    print("PRYTB GATE3F VERIFIER\n")
    print(f"backfill_candidates: {backfill_candidates}")
    print(f"backfill_attempted: {backfill_attempted}")
    print(f"newly_verified: {newly_verified}")
    print(f"still_unevaluable: {still_unevaluable}")
    print(f"qualified_count: {qualified_count}")
    print(f"top3_readiness: {top3_readiness}\n")

    print(f"candidate_universe: {'PASS' if checks['candidate_universe'] else 'FAIL'}")
    print(f"lineage_integrity: {'PASS' if checks['lineage_integrity'] else 'FAIL'}")
    print(f"score_reproduction: {'PASS' if checks['score_reproduction'] else 'FAIL'}")
    print(f"qualification_integrity: {'PASS' if checks['qualification_integrity'] else 'FAIL'}")
    print(f"near_miss_integrity: {'PASS' if checks['near_miss_integrity'] else 'FAIL'}")
    print(f"persistence: {'PASS' if checks['persistence'] else 'FAIL'}")
    print(f"hash_reproducibility: {'PASS' if checks['hash_reproducibility'] else 'FAIL'}")
    print(f"database_integrity: {'PASS' if checks['database_integrity'] else 'FAIL'}\n")

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
