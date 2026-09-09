"""
Sprint 12 Gate 2A: Authoritative Run Provenance Finalization Script.

Checks run_metadata for run_id='sprint12_interim_reconciled_20260908_202912',
repairs metadata if stale values exist, verifies dataset hash & video/channel counts,
validates Gate 2 analytical rows & provenance in InsForge, creates local manifest,
and verifies zero stale contract contamination.
"""

import datetime
import hashlib
import json
import os
import sys
from typing import Dict, Any, List

from app.database.insforge_client import InsForgeClient
from app.database.repositories import YouTubeRepository
from app.analytics.outlier_engine import is_test_video

EXPECTED_RUN_ID = "sprint12_interim_reconciled_20260908_202912"
EXPECTED_SOURCE_RUN = "sprint12_prod_run_01"
EXPECTED_VIDEO_COUNT = 7611
EXPECTED_CHANNEL_COUNT = 4773
EXPECTED_DATASET_HASH = "6b0ac147d9aae34551c6db0a450ae778d22c6c5132feb89c8878eafeacf69919"
EXPECTED_RUN_TYPE = "INTERIM"
EXPECTED_STATUS = "OUTLIER_GATE_READY"
EXPECTED_METHODOLOGY_VERSION = "2.0"
EXPECTED_ACTUAL_OUTLIERS = 528
EXPECTED_SMALL_CHANNEL_OUTLIERS = 230

MANIFEST_PATH = os.path.join("data", "processed", "sprint12_interim_manifest.json")


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
    return " ".join(text.split())


def compute_canonical_dataset_hash(prod_videos: List[Dict[str, Any]]) -> str:
    sorted_vids = sorted(prod_videos, key=lambda v: str(v.get("video_id", "")))
    lines = []
    for v in sorted_vids:
        vid = str(v.get("video_id", ""))
        title = clean_text(str(v.get("title", "") or ""))
        desc = clean_text(str(v.get("description", "") or ""))
        sem = f"{title} {desc}".strip()
        lines.append(f"{vid}|{sem}")
    payload = "\n".join(lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_outlier_hash(outlier_rows: List[Dict[str, Any]]) -> str:
    actual_rows = [r for r in outlier_rows if r.get("is_actual_outlier") is True]
    sorted_actuals = sorted(actual_rows, key=lambda r: str(r.get("video_id", "")))
    lines = []
    for r in sorted_actuals:
        vid = str(r.get("video_id", ""))
        cid = str(r.get("channel_id", ""))
        ratio = f"{float(r.get('outlier_ratio', 0.0)):.6f}"
        score = f"{float(r.get('outlier_rank_score', 0.0)):.6f}"
        flag = "1" if r.get("small_channel_flag") else "0"
        lines.append(f"{vid}|{cid}|{ratio}|{score}|{flag}")
    payload = "\n".join(lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_provenance_finalization():
    print("=" * 60)
    print("PRYTB — SPRINT 12 GATE 2A PROVENANCE FINALIZATION")
    print("=" * 60)

    # 1. INSFORGE PRE-FLIGHT
    print("\n1. InsForge Pre-flight...")
    client = InsForgeClient()

    if not client.url or not client.api_key:
        print("[FAIL] InsForge client missing credentials.")
        sys.exit(1)

    print(f"INSFORGE CONNECTION: OK ({client.url})")
    repo = YouTubeRepository(client)

    # 2. READ CURRENT RUN METADATA
    print("\n2. Reading Current Run Metadata for run_id:", EXPECTED_RUN_ID)
    runs = repo._get_records("run_metadata", params={"run_id": f"eq.{EXPECTED_RUN_ID}"})
    if not runs:
        print(f"[FAIL] No run_metadata record found for run_id '{EXPECTED_RUN_ID}'.")
        sys.exit(1)

    run_meta_before = runs[0]
    print("Run Metadata BEFORE:")
    print("  run_id:", run_meta_before.get("run_id"))
    print("  run_type:", run_meta_before.get("run_type"))
    print("  source_collection_run:", run_meta_before.get("source_collection_run"))
    print("  video_count:", run_meta_before.get("video_count"))
    print("  channel_count:", run_meta_before.get("channel_count"))
    print("  dataset_hash:", run_meta_before.get("dataset_hash"))
    print("  methodology_version:", run_meta_before.get("methodology_version"))
    print("  status:", run_meta_before.get("status"))

    # 3. AUTHORITATIVE CONTRACT RECONSTRUCTION
    print("\n3. Reconstructing Authoritative Contract from DB...")
    all_raw_videos = repo.get_all_videos()
    prod_videos = [v for v in all_raw_videos if not is_test_video(v)]
    prod_channels = set(str(v.get("channel_id")) for v in prod_videos if v.get("channel_id"))

    reconstructed_video_count = len(prod_videos)
    reconstructed_channel_count = len(prod_channels)
    reconstructed_dataset_hash1 = compute_canonical_dataset_hash(prod_videos)
    reconstructed_dataset_hash2 = compute_canonical_dataset_hash(prod_videos)

    print(f"  reconstructed_video_count = {reconstructed_video_count}")
    print(f"  reconstructed_channel_count = {reconstructed_channel_count}")
    print(f"  dataset_hash run1 = {reconstructed_dataset_hash1}")
    print(f"  dataset_hash run2 = {reconstructed_dataset_hash2}")

    assert reconstructed_video_count == EXPECTED_VIDEO_COUNT, f"Video count mismatch: {reconstructed_video_count} vs {EXPECTED_VIDEO_COUNT}"
    assert reconstructed_channel_count == EXPECTED_CHANNEL_COUNT, f"Channel count mismatch: {reconstructed_channel_count} vs {EXPECTED_CHANNEL_COUNT}"
    assert reconstructed_dataset_hash1 == EXPECTED_DATASET_HASH, f"Dataset hash mismatch: {reconstructed_dataset_hash1} vs {EXPECTED_DATASET_HASH}"
    assert reconstructed_dataset_hash1 == reconstructed_dataset_hash2, "Dataset hash self-reproducibility failed"
    print("  [PASS] Authoritative contract independently reproduced.")

    # 4. REPAIR RUN METADATA IF REQUIRED
    needs_repair = (
        run_meta_before.get("video_count") != EXPECTED_VIDEO_COUNT or
        run_meta_before.get("channel_count") != EXPECTED_CHANNEL_COUNT or
        run_meta_before.get("dataset_hash") != EXPECTED_DATASET_HASH or
        run_meta_before.get("status") != EXPECTED_STATUS
    )

    if needs_repair:
        print("\n4. Repairing run_metadata in InsForge...")
        repaired_payload = {
            "run_id": EXPECTED_RUN_ID,
            "run_type": EXPECTED_RUN_TYPE,
            "source_collection_run": EXPECTED_SOURCE_RUN,
            "video_count": EXPECTED_VIDEO_COUNT,
            "channel_count": EXPECTED_CHANNEL_COUNT,
            "dataset_hash": EXPECTED_DATASET_HASH,
            "methodology_version": EXPECTED_METHODOLOGY_VERSION,
            "status": EXPECTED_STATUS,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        repo.create_run_metadata(repaired_payload)
        print("  [PASS] run_metadata upserted/repaired.")
    else:
        print("\n4. run_metadata is already fully compliant with Gate 2 contract.")

    # 5. INSFORGE READ-BACK FOR METADATA
    print("\n5. InsForge Read-back Verification for run_metadata...")
    runs_after = repo._get_records("run_metadata", params={"run_id": f"eq.{EXPECTED_RUN_ID}"})
    assert len(runs_after) == 1, f"Expected 1 run_metadata record, got {len(runs_after)}"
    run_meta_after = runs_after[0]

    print("Run Metadata AFTER:")
    print("  run_id:", run_meta_after.get("run_id"))
    print("  video_count:", run_meta_after.get("video_count"))
    print("  channel_count:", run_meta_after.get("channel_count"))
    print("  dataset_hash:", run_meta_after.get("dataset_hash"))
    print("  status:", run_meta_after.get("status"))

    assert run_meta_after.get("video_count") == EXPECTED_VIDEO_COUNT
    assert run_meta_after.get("channel_count") == EXPECTED_CHANNEL_COUNT
    assert run_meta_after.get("dataset_hash") == EXPECTED_DATASET_HASH
    assert run_meta_after.get("status") == EXPECTED_STATUS
    print("  [PASS] Metadata read-back exact.")

    # 6. GATE 2 ANALYTICAL PROVENANCE CHECK
    print("\n6. Gate 2 Analytical Provenance Verification...")
    outlier_records = repo._get_records("video_outlier_analyses", params={"run_id": f"eq.{EXPECTED_RUN_ID}"})
    print(f"  Retrieved {len(outlier_records)} outlier analysis rows from InsForge.")

    assert len(outlier_records) == EXPECTED_VIDEO_COUNT, f"Expected {EXPECTED_VIDEO_COUNT} outlier rows, got {len(outlier_records)}"

    wrong_run_id = sum(1 for r in outlier_records if r.get("run_id") != EXPECTED_RUN_ID)
    wrong_dataset_hash = sum(1 for r in outlier_records if r.get("dataset_hash") != EXPECTED_DATASET_HASH)
    missing_provenance = sum(1 for r in outlier_records if not r.get("run_id") or not r.get("dataset_hash"))
    
    seen_ids = set()
    duplicates = 0
    for r in outlier_records:
        vid = r.get("video_id")
        if vid in seen_ids:
            duplicates += 1
        seen_ids.add(vid)

    actual_outliers = sum(1 for r in outlier_records if r.get("is_actual_outlier") is True)
    small_channel_outliers = sum(1 for r in outlier_records if r.get("is_actual_outlier") is True and r.get("small_channel_flag") is True)

    print(f"  Actual outliers: {actual_outliers} (expected {EXPECTED_ACTUAL_OUTLIERS})")
    print(f"  Small-channel actual outliers: {small_channel_outliers} (expected {EXPECTED_SMALL_CHANNEL_OUTLIERS})")
    print(f"  Wrong run_id: {wrong_run_id}")
    print(f"  Wrong dataset_hash: {wrong_dataset_hash}")
    print(f"  Missing provenance: {missing_provenance}")
    print(f"  Duplicates: {duplicates}")

    assert actual_outliers == EXPECTED_ACTUAL_OUTLIERS
    assert small_channel_outliers == EXPECTED_SMALL_CHANNEL_OUTLIERS
    assert wrong_run_id == 0
    assert wrong_dataset_hash == 0
    assert missing_provenance == 0
    assert duplicates == 0
    print("  [PASS] All Gate 2 analytical rows have valid, exact provenance.")

    # 7. OLD CONTRACT CONTAMINATION CHECK
    print("\n7. Stale Contract Audit...")
    stale_metadata = sum(1 for r in runs_after if r.get("dataset_hash") == "061de620aa852d3e33e163430bf3e8130af3081abd5b99d84cd081a503b83d4d" or r.get("video_count") == 7637)
    stale_outliers = sum(1 for r in outlier_records if r.get("dataset_hash") == "061de620aa852d3e33e163430bf3e8130af3081abd5b99d84cd081a503b83d4d")
    
    print(f"  Stale current metadata records: {stale_metadata}")
    print(f"  Stale Gate 2 outlier rows: {stale_outliers}")

    assert stale_metadata == 0
    assert stale_outliers == 0
    print("  [PASS] Zero stale contract contamination in active run provenance.")

    # 8. CANONICAL RUN MANIFEST
    print("\n8. Generating Canonical Run Manifest...")
    outlier_hash = compute_outlier_hash(outlier_records)
    
    manifest_data = {
        "run_id": EXPECTED_RUN_ID,
        "run_type": EXPECTED_RUN_TYPE,
        "source_collection_run": EXPECTED_SOURCE_RUN,
        "video_count": EXPECTED_VIDEO_COUNT,
        "channel_count": EXPECTED_CHANNEL_COUNT,
        "dataset_hash": EXPECTED_DATASET_HASH,
        "outlier_count": actual_outliers,
        "small_channel_outlier_count": small_channel_outliers,
        "outlier_hash": outlier_hash,
        "methodology_version": EXPECTED_METHODOLOGY_VERSION,
        "status": EXPECTED_STATUS,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"  [PASS] Manifest written to '{MANIFEST_PATH}'.")
    print(f"  Outlier SHA-256 Hash: {outlier_hash}")

    print("\n" + "=" * 60)
    print("ALL GATE 2A PROVENANCE INVARIANTS PASS PERFECTLY")
    print("=" * 60)

if __name__ == "__main__":
    run_provenance_finalization()
