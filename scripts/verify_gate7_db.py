import sys
import json
import hashlib
import psycopg
from pathlib import Path
from typing import List, Tuple, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scripts.create_sprint12_dataset_contract import clean_text_for_embedding, compute_dataset_hash, is_test_video

EXPECTED_GATE7_RUN = "sprint12_gate7_final_analytics_20260910_231500"
EXPECTED_DATASET_HASH = "ecc6ad6d164e586bd718ff8c17be3801b5e3c0bbfa4e39cfc555b26f5c82c4ba"
EXPECTED_RAW = 10613
EXPECTED_PROD = 10585
EXPECTED_CHANNELS = 6487
EXPECTED_FIXTURES = 28
EXPECTED_K = 35

def compute_assignments_hash_from_tuples(assignments: List[Tuple[str, int]]) -> str:
    sorted_assignments = sorted(assignments, key=lambda x: str(x[0]))
    lines = [f"{x[0]}|{x[1]}" for x in sorted_assignments]
    payload = "\n".join(lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def verify_gate7():
    conn = psycopg.connect("postgresql://prytb_app:pyrtb@localhost:5433/prytb")
    errors = []
    with conn.cursor() as cur:
        # 1. Dataset check
        cur.execute("SELECT video_id, title, description, channel_id FROM videos;")
        all_videos = cur.fetchall()
        raw_cnt = len(all_videos)

        prod_videos = []
        excluded_fixtures = []
        for v in all_videos:
            v_dict = {"video_id": v[0], "title": v[1], "description": v[2], "channel_id": v[3]}
            if is_test_video(v_dict):
                excluded_fixtures.append(v_dict)
            else:
                prod_videos.append(v_dict)

        precanonical_excl = len(excluded_fixtures)
        prod_cnt = len(prod_videos)
        prod_channels = len(set(v["channel_id"] for v in prod_videos if v["channel_id"]))

        print(f"Dataset guard: raw={raw_cnt}, precanonical_excl={precanonical_excl}, prod={prod_cnt}, channels={prod_channels}")

        if raw_cnt != EXPECTED_RAW:
            errors.append(f"Raw videos count mismatch: expected {EXPECTED_RAW}, got {raw_cnt}")
        if precanonical_excl != EXPECTED_FIXTURES:
            errors.append(f"Excluded fixtures count mismatch: expected {EXPECTED_FIXTURES}, got {precanonical_excl}")
        if prod_cnt != EXPECTED_PROD:
            errors.append(f"Productive videos count mismatch: expected {EXPECTED_PROD}, got {prod_cnt}")
        if prod_channels != EXPECTED_CHANNELS:
            errors.append(f"Productive channels count mismatch: expected {EXPECTED_CHANNELS}, got {prod_channels}")

        prod_rows = [
            {"video_id": v["video_id"], "semantic_text": clean_text_for_embedding(v["title"] or "", v["description"])}
            for v in prod_videos
        ]
        hash1 = compute_dataset_hash(prod_rows)
        hash2 = compute_dataset_hash(prod_rows)
        print(f"Dataset Hash: hash1={hash1}, hash2={hash2}, match={hash1==hash2}")

        if hash1 != EXPECTED_DATASET_HASH or hash2 != EXPECTED_DATASET_HASH:
            errors.append(f"Dataset hash mismatch: expected {EXPECTED_DATASET_HASH}, got {hash1}")

        # Check analytical run
        cur.execute("SELECT run_id, run_type, dataset_hash, video_count, channel_count, status FROM analytical_runs WHERE run_id = %s;", [EXPECTED_GATE7_RUN])
        run_row = cur.fetchone()
        if not run_row:
            errors.append(f"Analytical run {EXPECTED_GATE7_RUN} missing from analytical_runs")
        else:
            print("Analytical run row:", run_row)
            if run_row[5] != "EXECUTION_COMPLETED_PENDING_EXTERNAL_CLOSE":
                errors.append(f"Analytical run status invalid: got {run_row[5]}")

        # Check cluster_videos
        cur.execute("SELECT video_id, cluster_id FROM cluster_videos WHERE run_id = %s ORDER BY video_id;", [EXPECTED_GATE7_RUN])
        cv_rows_1 = cur.fetchall()
        cur.execute("SELECT video_id, cluster_id FROM cluster_videos WHERE run_id = %s ORDER BY video_id;", [EXPECTED_GATE7_RUN])
        cv_rows_2 = cur.fetchall()

        print(f"Cluster videos assigned for {EXPECTED_GATE7_RUN}: {len(cv_rows_1)}")
        if len(cv_rows_1) != EXPECTED_PROD:
            errors.append(f"Assigned videos count mismatch: expected {EXPECTED_PROD}, got {len(cv_rows_1)}")

        if cv_rows_1:
            assign_hash1 = compute_assignments_hash_from_tuples(cv_rows_1)
            assign_hash2 = compute_assignments_hash_from_tuples(cv_rows_2)
            print(f"Persisted Assignment Hash: hash1={assign_hash1}, hash2={assign_hash2}, match={assign_hash1==assign_hash2}")
            if assign_hash1 != assign_hash2:
                errors.append("Persisted assignment hashes do not match across independent reads")

        cur.execute("SELECT COUNT(*) FROM video_outlier_analyses WHERE run_id = %s;", [EXPECTED_GATE7_RUN])
        outlier_cnt = cur.fetchone()[0]
        print(f"Outlier analyses in DB for {EXPECTED_GATE7_RUN}: {outlier_cnt}")
        if outlier_cnt != EXPECTED_PROD:
            errors.append(f"Outlier analyses count mismatch: expected {EXPECTED_PROD}, got {outlier_cnt}")

        cur.execute("SELECT COUNT(*) FROM clusters WHERE run_id = %s;", [EXPECTED_GATE7_RUN])
        cluster_cnt = cur.fetchone()[0]
        print(f"Clusters in DB for {EXPECTED_GATE7_RUN}: {cluster_cnt}")
        if cluster_cnt != EXPECTED_K:
            errors.append(f"Clusters count mismatch: expected {EXPECTED_K}, got {cluster_cnt}")

    if errors:
        print("\n[FAIL] Gate 7 Database Verification Failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\n[PASS] Gate 7 Database Verification Passed completely.")

if __name__ == "__main__":
    verify_gate7()
