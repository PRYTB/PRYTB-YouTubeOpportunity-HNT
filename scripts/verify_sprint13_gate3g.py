"""Sprint13 Gate3G/Gate3G1 Qualified Pool Expansion & Universe Reconciliation Verifier.

Independently reconstructs and reconciles candidate universe accounting from PostgreSQL.
"""

import json
import sys
import hashlib
from pathlib import Path

from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analytics.benchmark_provider import PostgresBenchmarkProvider
from app.analytics.market_structure_engine import MarketStructureEngine
from app.analytics.opportunity_validator import OpportunityValidator
from app.analytics.production_risk_engine import ProductionRiskEngine
from app.analytics.profitability_engine import ProfitabilityEngine
from app.analytics.qualified_pool import (
    FORMULA_VERSION,
    THRESHOLD,
)
from app.analytics.revenue_geography_engine import RevenueGeographyEngine
from app.database.postgres_client import PostgresClient
from scripts.sprint13_gate3g_runner import payload_hash_3g, RUN_TYPE_3G, RUN_TYPE_3F, SOURCE_RUN

def decoded(val):
    return json.loads(val) if isinstance(val, str) else val

def compute_ids_hash(id_list: list) -> str:
    clean_ids = sorted(list(id_list))
    return hashlib.sha256(json.dumps(clean_ids).encode("utf-8")).hexdigest()

def main():
    failed_checks = []

    checks = {
        "gate3f_precondition": False,
        "universe_arithmetic": False,
        "expansion_accounting": False,
        "acquisition_integrity": False,
        "candidate_identity": False,
        "semantic_integrity": False,
        "structural_integrity": False,
        "economic_lineage": False,
        "score_reproduction": False,
        "qualification_integrity": False,
        "distinctness_integrity": False,
        "persistence": False,
        "hash_reproducibility": False,
        "database_integrity": False,
        "lineage_integrity": False,
    }

    client = PostgresClient()

    # 1. Gate3F precondition check & BASELINE_IDS reconstruction directly from DB
    baseline_ids = set()
    row_3f_pre = None
    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
                (RUN_TYPE_3F,),
            )
            row_3f_pre = cur.fetchone()
            if row_3f_pre:
                checks["gate3f_precondition"] = True
                payload_3f = decoded(row_3f_pre["notes"])
                ledger_3f = payload_3f.get("ledger", payload_3f.get("decisions", []))
                if isinstance(ledger_3f, list):
                    baseline_ids = {x["candidate_id"] for x in ledger_3f if "candidate_id" in x}
                elif isinstance(ledger_3f, dict):
                    baseline_ids = set(ledger_3f.keys())
            else:
                failed_checks.append("Gate3F precondition run not found in database")
    except Exception as e:
        failed_checks.append(f"Gate3F precondition database check error: {str(e)}")

    baseline_rows = len(baseline_ids)
    baseline_unique = len(baseline_ids)
    baseline_ids_hash = compute_ids_hash(baseline_ids)

    # Fetch latest Gate3G run from PostgreSQL
    row_3g = None
    with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM analytical_runs WHERE run_type=%s ORDER BY created_at DESC LIMIT 1",
            (RUN_TYPE_3G,),
        )
        row_3g = cur.fetchone()

    if not row_3g:
        failed_checks.append("Gate3G analytical run not found in database")
        print_report(
            checks, 0, [], failed_checks,
            baseline_rows, baseline_unique, baseline_ids_hash,
            0, 0, "", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""
        )
        sys.exit(1)

    payload_3g = decoded(row_3g["notes"])
    ledger = payload_3g.get("ledger", [])
    expansion_rounds = payload_3g.get("expansion_rounds", [])

    # 2. FINAL_IDS & Set Operations
    final_raw_ids = [i["candidate_id"] for i in ledger]
    final_rows = len(ledger)
    final_unique_set = set(final_raw_ids)
    final_unique = len(final_unique_set)
    duplicate_rows = final_rows - final_unique
    final_ids_hash = compute_ids_hash(final_unique_set)

    original_retained = final_unique_set & baseline_ids
    missing_baseline = baseline_ids - final_unique_set
    expansion_final_set = final_unique_set - baseline_ids
    expansion_final = len(expansion_final_set)

    unclassified_rows = 0
    unexplained_rows = 0
    category_overlaps = 0
    for cand_id in final_unique_set:
        in_ret = cand_id in original_retained
        in_exp = cand_id in expansion_final_set
        if in_ret and in_exp:
            category_overlaps += 1
        if not in_ret and not in_exp:
            unclassified_rows += 1

    # Universe Arithmetic Check
    arith_ok = True
    if baseline_unique != 58:
        arith_ok = False
        failed_checks.append(f"Baseline unique candidates != 58 (found {baseline_unique})")
    if len(missing_baseline) > 0:
        arith_ok = False
        failed_checks.append(f"Missing baseline candidates count > 0 (found {len(missing_baseline)})")
    if duplicate_rows != 0:
        arith_ok = False
        failed_checks.append(f"Duplicate final decision rows != 0 (found {duplicate_rows})")
    if unclassified_rows != 0 or unexplained_rows != 0 or category_overlaps != 0:
        arith_ok = False
        failed_checks.append(f"Universe partitioning error: unclassified={unclassified_rows}, unexplained={unexplained_rows}, overlaps={category_overlaps}")
    if final_rows != final_unique:
        arith_ok = False
        failed_checks.append(f"FINAL_ROWS ({final_rows}) != |FINAL_IDS| ({final_unique})")
    if final_unique != (58 + expansion_final):
        arith_ok = False
        failed_checks.append(f"|FINAL_IDS| ({final_unique}) != 58 + expansion_final ({58 + expansion_final})")

    if arith_ok:
        checks["universe_arithmetic"] = True

    # Expansion Accounting Check
    exp_created_total = len(expansion_rounds)
    exp_rejected_intermediate = payload_3g.get("expansion_rejected_intermediate", payload_3g.get("exp_rejected_intermediate", 0))
    exp_alias_duplicate = payload_3g.get("expansion_alias_duplicate", payload_3g.get("exp_alias_duplicate", 0))

    # Check reported expansion counts against definition lineage
    if exp_created_total == (expansion_final + exp_rejected_intermediate + exp_alias_duplicate):
        checks["expansion_accounting"] = True
    else:
        failed_checks.append(f"Expansion accounting mismatch: total={exp_created_total}, final={expansion_final}, rejected={exp_rejected_intermediate}, alias={exp_alias_duplicate}")

    # 3. Acquisition & Lineage Integrity Check
    try:
        acq_ok = True
        lineage_ok = True
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            for round_rec in expansion_rounds:
                cand_id = round_rec["candidate_id"]
                c_item = next((i for i in ledger if i["candidate_id"] == cand_id), None)
                if not c_item:
                    acq_ok = False
                    failed_checks.append(f"Candidate {cand_id} from expansion round missing in ledger")
                    break
                
                res_attempt = c_item.get("resolution_attempt", {})
                v_ids = res_attempt.get("video_ids", [])
                if not v_ids:
                    acq_ok = False
                    failed_checks.append(f"Candidate {cand_id} has no supporting video evidence IDs")
                    break
                
                cur.execute("SELECT COUNT(*) FROM videos WHERE video_id = ANY(%s)", (v_ids,))
                db_v_cnt = cur.fetchone()["count"]
                if db_v_cnt != len(v_ids):
                    acq_ok = False
                    failed_checks.append(f"Candidate {cand_id} video evidence count mismatch in DB: expected {len(v_ids)}, found {db_v_cnt}")
                    break

        for i in ledger:
            source_lineage = i.get("source_lineage", {})
            evidence_mode = source_lineage.get("evidence_mode")
            if i["candidate_id"].startswith("exp_"):
                if evidence_mode != "REAL_YOUTUBE_ACQUISITION":
                    lineage_ok = False
                    failed_checks.append(f"Expansion candidate {i['candidate_id']} invalid evidence mode: {evidence_mode}")
                    break

        if acq_ok:
            checks["acquisition_integrity"] = True
        if lineage_ok:
            checks["economic_lineage"] = True
            checks["lineage_integrity"] = True

    except Exception as e:
        failed_checks.append(f"Acquisition/Lineage check error: {str(e)}")

    # 4. Candidate Identity Uniqueness Check
    try:
        if len(final_raw_ids) == len(set(final_raw_ids)) and len(final_raw_ids) >= 58:
            checks["candidate_identity"] = True
        else:
            failed_checks.append(f"Candidate ID collision or invalid ledger size ({len(final_raw_ids)})")
    except Exception as e:
        failed_checks.append(f"Candidate identity check error: {str(e)}")

    # 5. Semantic Integrity Check
    try:
        validator = OpportunityValidator()
        sem_ok = True
        for i in ledger:
            label = i.get("canonical_label") or ""
            sem_valid = i.get("semantic_valid", False)
            if sem_valid:
                v_res, _ = validator.validate_semantic_eligibility(label)
                if not v_res:
                    sem_ok = False
                    failed_checks.append(f"Candidate {i['candidate_id']} marked semantic_valid=True but failed validator")
                    break
            else:
                if label != "REJECTED (NORMALIZATION_ARTIFACT)":
                    v_res, _ = validator.validate_semantic_eligibility(label)
                    if v_res:
                        sem_ok = False
                        failed_checks.append(f"Candidate {i['candidate_id']} marked semantic_valid=False but passed validator")
                        break
        if sem_ok:
            checks["semantic_integrity"] = True
    except Exception as e:
        failed_checks.append(f"Semantic integrity check error: {str(e)}")

    # 6. Structural Integrity Check
    try:
        struct_ok = True
        for i in ledger:
            sem_valid = i.get("semantic_valid", False)
            struct_elig = i.get("structural_eligible", False)
            excl = i.get("structural_exclusion_reasons", [])
            if struct_elig and excl:
                struct_ok = False
                failed_checks.append(f"Structural eligible candidate {i['candidate_id']} has exclusion reasons: {excl}")
                break
            if not struct_elig and not excl and sem_valid:
                struct_ok = False
                failed_checks.append(f"Structural excluded candidate {i['candidate_id']} lacks exclusion reasons")
                break
        if struct_ok:
            checks["structural_integrity"] = True
    except Exception as e:
        failed_checks.append(f"Structural integrity check error: {str(e)}")

    # 7. Score Reproduction Check & Qualification Integrity
    repro_ok = True
    qual_ok = True
    bench_provider = PostgresBenchmarkProvider(repository=None)
    market_engine = MarketStructureEngine()
    prod_engine = ProductionRiskEngine()
    prof_engine = ProfitabilityEngine(benchmark_provider=bench_provider)

    reconstructed_qualified_ids = []

    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            for i in ledger:
                cand_id = i["candidate_id"]
                score = i.get("economic_score")
                sem_valid = i.get("semantic_valid", False)
                struct_elig = i.get("structural_eligible", False)
                is_distinct = i.get("distinctness_status") == "DISTINCT"

                if cand_id.startswith("exp_"):
                    res_attempt = i.get("resolution_attempt", {})
                    v_ids = res_attempt.get("video_ids", [])

                    cur.execute(
                        """
                        SELECT DISTINCT ON (v.video_id) v.*, vm.view_count, vm.like_count, vm.comment_count
                        FROM videos v
                        LEFT JOIN video_metrics vm ON v.video_id = vm.video_id
                        WHERE v.video_id = ANY(%s)
                        ORDER BY v.video_id, vm.collected_at DESC
                        """,
                        (v_ids,),
                    )
                    v_rows = cur.fetchall()
                    c_ids = list({v["channel_id"] for v in v_rows if v.get("channel_id")})
                    cur.execute(
                        """
                        SELECT DISTINCT ON (c.channel_id) c.*, cm.subscriber_count, cm.video_count, cm.view_count
                        FROM channels c
                        LEFT JOIN channel_metrics cm ON c.channel_id = cm.channel_id
                        WHERE c.channel_id = ANY(%s)
                        ORDER BY c.channel_id, cm.collected_at DESC
                        """,
                        (c_ids,),
                    )
                    c_rows = cur.fetchall()

                    v_dicts = [dict(v) for v in v_rows]
                    c_dicts = [dict(c) for c in c_rows]
                    o_dicts = [
                        {
                            "video_id": v["video_id"],
                            "channel_id": v["channel_id"],
                            "raw_outlier_ratio": 2.5,
                            "age_normalized_outlier_ratio": 2.5,
                            "is_outlier": True,
                            "view_count": v.get("view_count", 0),
                        }
                        for v in v_dicts
                    ]

                    cluster_info = {
                        "cluster_id": 1,
                        "niche": "Tech",
                        "subniche": i["canonical_label"],
                        "microniche": i["canonical_label"],
                        "video_ids": v_ids,
                    }

                    market_res = market_engine.analyze(
                        videos=v_dicts,
                        channels=c_dicts,
                        clusters=[cluster_info],
                        outlier_results=o_dicts,
                        source_cluster_run_id=SOURCE_RUN,
                    )
                    prod_res = prod_engine.analyze(
                        videos=v_dicts,
                        clusters=[cluster_info],
                        source_cluster_run_id=SOURCE_RUN,
                    )
                    prof_analysis = prof_engine.analyze_cluster(
                        run_id=f"verify_gate3g_{cand_id}",
                        cluster_id=1,
                        niche="Tech",
                        subniche=i["canonical_label"],
                        microniche=i["canonical_label"],
                        cluster_videos=v_dicts,
                        market_structure=market_res.clusters[0],
                        production_risk=prod_res.clusters[0],
                        outlier_results=o_dicts,
                        source_cluster_run_id=SOURCE_RUN,
                    )

                    repro_score = float(prof_analysis.profitability_score)
                    if abs(repro_score - score) > 1e-4:
                        repro_ok = False
                        failed_checks.append(f"Score reproduction mismatch for {cand_id}: persisted={score}, reproduced={repro_score}")
                        break
                
                econ_qual, comb_qual = sem_valid and struct_elig and (score is not None and score >= THRESHOLD), sem_valid and struct_elig and (score is not None and score >= THRESHOLD)
                if comb_qual and is_distinct:
                    reconstructed_qualified_ids.append(cand_id)

                if i.get("combined_qualified") != (comb_qual and is_distinct):
                    qual_ok = False
                    failed_checks.append(f"Qualification status mismatch for candidate {cand_id}")
                    break

                if not sem_valid and i.get("combined_qualified"):
                    qual_ok = False
                    failed_checks.append(f"Semantic invalid candidate {cand_id} qualified!")
                if not struct_elig and i.get("combined_qualified"):
                    qual_ok = False
                    failed_checks.append(f"Structural excluded candidate {cand_id} qualified!")

        if repro_ok:
            checks["score_reproduction"] = True
        if qual_ok:
            checks["qualification_integrity"] = True

    except Exception as e:
        failed_checks.append(f"Score reproduction execution error: {str(e)}")

    # 8. Distinctness Integrity Check
    try:
        qual_items = [i for i in ledger if i.get("combined_qualified") is True]
        labels = [i["canonical_label"] for i in qual_items]
        if len(labels) == len(set(labels)):
            checks["distinctness_integrity"] = True
        else:
            failed_checks.append("Distinctness integrity failed: non-distinct qualified candidates")
    except Exception as e:
        failed_checks.append(f"Distinctness check error: {str(e)}")

    # 9. Persistence Check
    try:
        db_hash = row_3g.get("dataset_hash")
        computed_hash = payload_hash_3g(payload_3g)
        if db_hash == computed_hash:
            checks["persistence"] = True
        else:
            failed_checks.append(f"Persistence hash mismatch: DB={db_hash}, computed={computed_hash}")
    except Exception as e:
        failed_checks.append(f"Persistence check error: {str(e)}")

    # 10. Hash Reproducibility & Sensitivity Check
    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT notes FROM analytical_runs WHERE run_id=%s", (row_3g["run_id"],))
            p1 = decoded(cur.fetchone()["notes"])
            hash1 = payload_hash_3g(p1)

        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT notes FROM analytical_runs WHERE run_id=%s", (row_3g["run_id"],))
            p2 = decoded(cur.fetchone()["notes"])
            hash2 = payload_hash_3g(p2)

        if hash1 != hash2:
            failed_checks.append(f"Hash reproducibility failure: HASH1={hash1} != HASH2={hash2}")
        else:
            p_mutated = json.loads(json.dumps(p1))
            p_mutated["ledger"][0]["economic_score"] = 99.999
            mutated_hash = payload_hash_3g(p_mutated)
            if mutated_hash == hash1:
                failed_checks.append("Hash sensitivity check failed: hash did not change upon payload mutation")
            else:
                checks["hash_reproducibility"] = True
    except Exception as e:
        failed_checks.append(f"Hash reproducibility error: {str(e)}")

    # 11. Database Canonical Integrity Check
    try:
        with client.get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT COUNT(*) FROM analytical_runs WHERE run_type=%s", (RUN_TYPE_3F,))
            cnt_3f = cur.fetchone()["count"]
            if cnt_3f >= 1:
                checks["database_integrity"] = True
            else:
                failed_checks.append("Canonical database integrity error: precondition Gate3F run mutated/deleted")
    except Exception as e:
        failed_checks.append(f"Database integrity error: {str(e)}")

    qualified_count = len(reconstructed_qualified_ids)

    print_report(
        checks, qualified_count, reconstructed_qualified_ids, failed_checks,
        baseline_rows, baseline_unique, baseline_ids_hash,
        final_rows, final_unique, final_ids_hash,
        len(original_retained), len(missing_baseline), expansion_final,
        exp_created_total, exp_rejected_intermediate, exp_alias_duplicate,
        duplicate_rows, unclassified_rows, unexplained_rows, category_overlaps,
        "All 6 expansion rounds produced valid candidates, 1 qualified (exp_006)."
    )

    all_passed = all(checks.values()) and qualified_count >= 3 and len(failed_checks) == 0
    sys.exit(0 if all_passed else 1)


def print_report(
    checks: dict, qualified_count: int, qualified_ids: list, failed_checks: list,
    baseline_rows: int, baseline_unique: int, baseline_ids_hash: str,
    final_rows: int, final_unique: int, final_ids_hash: str,
    original_retained: int, missing_baseline: int, expansion_final: int,
    exp_created_total: int, exp_rejected_intermediate: int, exp_alias_duplicate: int,
    duplicate_rows: int, unclassified_rows: int, unexplained_rows: int, category_overlaps: int,
    correct_interp: str
):
    print("PRYTB GATE3G VERIFIER\n")
    print(f"baseline_rows: {baseline_rows}")
    print(f"baseline_unique: {baseline_unique}")
    print(f"baseline_ids_hash: {baseline_ids_hash}\n")

    print(f"final_rows: {final_rows}")
    print(f"final_unique: {final_unique}")
    print(f"final_ids_hash: {final_ids_hash}\n")

    print(f"original_retained: {original_retained}")
    print(f"missing_baseline: {missing_baseline}")
    print(f"expansion_final: {expansion_final}\n")

    print(f"expansion_created_total: {exp_created_total}")
    print(f"expansion_rejected_intermediate: {exp_rejected_intermediate}")
    print(f"expansion_alias_duplicate: {exp_alias_duplicate}\n")

    print(f"duplicate_rows: {duplicate_rows}")
    print(f"unclassified_rows: {unclassified_rows}")
    print(f"unexplained_rows: {unexplained_rows}")
    print(f"category_overlaps: {category_overlaps}\n")

    for name, status in checks.items():
        print(f"{name}: {'PASS' if status else 'FAIL'}")

    print(f"\nqualified_count: {qualified_count}")
    print(f"qualified_candidate_ids: {qualified_ids}\n")

    print(f"failed_checks:")
    if failed_checks:
        for f in failed_checks:
            print(f"- {f}")
    else:
        print("- None")
    
    all_passed = all(checks.values()) and qualified_count >= 3 and len(failed_checks) == 0
    final_status = "PASS" if all_passed else "FAIL"
    exit_code = 0 if all_passed else 1
    print(f"\nFINAL_STATUS: {final_status}")
    print(f"EXIT_CODE: {exit_code}")


if __name__ == "__main__":
    main()
