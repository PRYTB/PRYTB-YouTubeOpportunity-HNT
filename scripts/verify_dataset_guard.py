"""
Dataset Guard verification script for Sprint 12 Gate 7.

Validates frozen dataset contract on PostgreSQL using canonical project helpers
and zero literal credentials.
"""

import sys
import hashlib
from pathlib import Path
from typing import Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from scripts.create_sprint12_dataset_contract import (
    clean_text_for_embedding,
    compute_dataset_hash,
    is_test_video,
)

EXPECTED_DATASET_HASH = "ecc6ad6d164e586bd718ff8c17be3801b5e3c0bbfa4e39cfc555b26f5c82c4ba"
EXPECTED_RAW_VIDEOS = 10613
EXPECTED_PROD_VIDEOS = 10585
EXPECTED_PROD_CHANNELS = 6487
EXPECTED_EXCLUDED_FIXTURES = 28


def verify_dataset_guard() -> None:
    client = PostgresClient()
    repo = YouTubeRepository(client)

    raw_videos = repo.get_all_videos()
    raw_cnt = len(raw_videos)

    prod_videos: List[Dict[str, Any]] = []
    excluded_fixtures: List[Dict[str, Any]] = []

    for v in raw_videos:
        if is_test_video(v):
            excluded_fixtures.append(v)
        else:
            prod_videos.append(v)

    prod_cnt = len(prod_videos)
    excluded_cnt = len(excluded_fixtures)
    prod_channels = len(set(v["channel_id"] for v in prod_videos if v.get("channel_id")))

    print(f"Dataset Guard: raw={raw_cnt}, excluded_fixtures={excluded_cnt}, prod={prod_cnt}, channels={prod_channels}")

    errors: List[str] = []
    if raw_cnt != EXPECTED_RAW_VIDEOS:
        errors.append(f"Raw video count mismatch: expected {EXPECTED_RAW_VIDEOS}, got {raw_cnt}")
    if excluded_cnt != EXPECTED_EXCLUDED_FIXTURES:
        errors.append(f"Excluded fixture count mismatch: expected {EXPECTED_EXCLUDED_FIXTURES}, got {excluded_cnt}")
    if prod_cnt != EXPECTED_PROD_VIDEOS:
        errors.append(f"Productive video count mismatch: expected {EXPECTED_PROD_VIDEOS}, got {prod_cnt}")
    if prod_channels != EXPECTED_PROD_CHANNELS:
        errors.append(f"Productive channel count mismatch: expected {EXPECTED_PROD_CHANNELS}, got {prod_channels}")

    # Reconstruct dataset rows twice independently
    prod_rows_1 = [
        {
            "video_id": v["video_id"],
            "semantic_text": clean_text_for_embedding(v.get("title") or "", v.get("description")),
        }
        for v in prod_videos
    ]
    hash1 = compute_dataset_hash(prod_rows_1)

    prod_rows_2 = [
        {
            "video_id": v["video_id"],
            "semantic_text": clean_text_for_embedding(v.get("title") or "", v.get("description")),
        }
        for v in prod_videos
    ]
    hash2 = compute_dataset_hash(prod_rows_2)

    print(f"Dataset Hash 1: {hash1}")
    print(f"Dataset Hash 2: {hash2}")
    print(f"Independent runs match: {hash1 == hash2}")

    if hash1 != EXPECTED_DATASET_HASH or hash2 != EXPECTED_DATASET_HASH:
        errors.append(f"Dataset hash mismatch: expected {EXPECTED_DATASET_HASH}, got hash1={hash1}, hash2={hash2}")

    if errors:
        print("\n[FAIL] Dataset Guard Verification Failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("\n[PASS] Dataset Guard Verification Passed completely.")


if __name__ == "__main__":
    verify_dataset_guard()
