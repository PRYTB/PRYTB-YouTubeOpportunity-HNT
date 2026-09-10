"""
Sprint 12 Gate 4 Preflight Verification Script.
"""
import sys
import os
import hashlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient

def main():
    client = PostgresClient()
    gate3_run_id = "sprint12_gate3_clustering_20260910_173651"
    dataset_hash = "6b0ac147d9aae34551c6db0a450ae778d22c6c5132feb89c8878eafeacf69919"
    expected_assignment_hash = "d6ba8832798c3c65003d9a9104726667397ab2b543f896088d26a27350a917c6"

    # Check clusters
    clusters = client.execute("SELECT cluster_id, video_count FROM public.clusters WHERE run_id = %s", [gate3_run_id])
    print(f"Loaded {len(clusters)} clusters from Gate3 run {gate3_run_id}")
    assert len(clusters) == 35, f"Expected 35 clusters, got {len(clusters)}"

    # Check assignments
    assignments = client.execute("SELECT video_id, cluster_id FROM public.cluster_videos WHERE run_id = %s ORDER BY video_id", [gate3_run_id])
    print(f"Loaded {len(assignments)} assignments from Gate3 run {gate3_run_id}")
    assert len(assignments) == 7611, f"Expected 7611 assignments, got {len(assignments)}"

    # Recompute assignment hash (sort by video_id)
    sorted_assignments = sorted([(r['video_id'], r['cluster_id']) for r in assignments], key=lambda x: str(x[0]))
    lines = [f"{vid}|{cid}" for vid, cid in sorted_assignments]
    computed_hash = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    print(f"Computed Assignment Hash: {computed_hash}")
    assert computed_hash == expected_assignment_hash, f"Assignment hash mismatch! Expected {expected_assignment_hash}, got {computed_hash}"

    print("[PASS] Gate 3 preflight verification successful!")

if __name__ == "__main__":
    main()
