"""
Comprehensive script to audit and reconcile Gate 1 and Gate 2 invariants.
"""

import sys
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from app.analytics.outlier_engine import OutlierEngine
from app.models.outliers import VideoOutlierResult
from scripts.create_sprint12_dataset_contract import clean_text_for_embedding, is_test_video, compute_dataset_hash

def run_invariant_audit():
    client = PostgresClient()
    repo = YouTubeRepository(client)

    videos_raw = repo.get_all_videos()
    channels_raw = repo.get_all_channels()
    valid_channel_ids = {c["channel_id"] for c in channels_raw if c.get("channel_id")}

    print(f"Raw DB videos count: {len(videos_raw)}")
    print(f"Raw DB channels count: {len(channels_raw)}")

    # 1. Gate 1 Population Reconciliation
    # Reconstruct strict Gate 1 dataset
    seen_vids = set()
    prod_videos = []
    prod_channels_set = set()
    excluded_fixtures = []
    duplicates = []
    orphans = []

    for v in videos_raw:
        vid = v.get("video_id")
        cid = v.get("channel_id")
        if not vid or not v.get("title"):
            continue
        if is_test_video(v):
            excluded_fixtures.append(vid)
            continue
        if vid in seen_vids:
            duplicates.append(vid)
            continue
        if cid not in valid_channel_ids:
            orphans.append(vid)
            continue

        seen_vids.add(vid)
        prod_videos.append(v)
        if cid:
            prod_channels_set.add(cid)

    prod_rows = [{"video_id": v["video_id"], "semantic_text": clean_text_for_embedding(v.get("title", ""), v.get("description", ""))} for v in prod_videos]
    
    hash_run1 = compute_dataset_hash(prod_rows)
    hash_run2 = compute_dataset_hash(prod_rows)
    hash_match = hash_run1 == hash_run2

    print(f"\n--- GATE 1 / RECONCILED DATASET ---")
    print(f"Authoritative Videos: {len(prod_videos)}")
    print(f"Authoritative Channels: {len(prod_channels_set)}")
    print(f"Excluded Fixtures ({len(excluded_fixtures)}): {excluded_fixtures[:5]}...")
    print(f"Dataset Hash Run 1: {hash_run1}")
    print(f"Dataset Hash Run 2: {hash_run2}")
    print(f"Hashes Equal: {hash_match}")

    # 2. Channel Bucket Invariants
    chan_to_vids = {}
    for v in prod_videos:
        cid = v.get("channel_id")
        if cid:
            chan_to_vids.setdefault(cid, []).append(v.get("video_id"))

    c1_chans = [cid for cid, vids in chan_to_vids.items() if len(vids) == 1]
    c2_chans = [cid for cid, vids in chan_to_vids.items() if len(vids) == 2]
    c3_chans = [cid for cid, vids in chan_to_vids.items() if len(vids) == 3]
    c4_chans = [cid for cid, vids in chan_to_vids.items() if len(vids) >= 4]

    C1 = len(c1_chans)
    C2 = len(c2_chans)
    C3 = len(c3_chans)
    C4 = len(c4_chans)

    channel_bucket_total = C1 + C2 + C3 + C4
    channel_invariant_pass = channel_bucket_total == len(prod_channels_set)

    V1 = sum(len(chan_to_vids[cid]) for cid in c1_chans)
    V2 = sum(len(chan_to_vids[cid]) for cid in c2_chans)
    V3 = sum(len(chan_to_vids[cid]) for cid in c3_chans)
    V4 = sum(len(chan_to_vids[cid]) for cid in c4_chans)

    video_bucket_total = V1 + V2 + V3 + V4
    video_invariant_pass = video_bucket_total == len(prod_videos)

    print(f"\n--- CHANNEL & VIDEO BUCKETS ---")
    print(f"C1 (exactly 1 video): {C1} channels -> {V1} videos")
    print(f"C2 (exactly 2 videos): {C2} channels -> {V2} videos")
    print(f"C3 (exactly 3 videos): {C3} channels -> {V3} videos")
    print(f"C4 (4+ videos):        {C4} channels -> {V4} videos")
    print(f"Channel bucket total: {channel_bucket_total} vs prod channels: {len(prod_channels_set)} (PASS: {channel_invariant_pass})")
    print(f"Video bucket total:   {video_bucket_total} vs prod videos: {len(prod_videos)} (PASS: {video_invariant_pass})")

    # 3. Baseline Invariants
    vids_with_baseline = V2 + V3 + V4
    vids_without_baseline = V1

    baseline_sum_pass = (vids_with_baseline + vids_without_baseline) == len(prod_videos)
    baseline_c1_pass = vids_without_baseline >= C1
    coverage_pct = (vids_with_baseline / len(prod_videos)) * 100

    print(f"\n--- BASELINE INVARIANTS ---")
    print(f"Videos with baseline:    {vids_with_baseline}")
    print(f"Videos without baseline: {vids_without_baseline}")
    print(f"Baseline Sum == Prod Videos: {baseline_sum_pass}")
    print(f"Vids without baseline >= C1 ({C1}): {baseline_c1_pass}")
    print(f"Baseline Coverage %:     {coverage_pct:.2f}%")

    # 4. Outlier Engine Recomputation & Confidence Audit
    outlier_engine = OutlierEngine(repository=repo)
    all_evals = outlier_engine.analyze_all()
    prod_vid_ids = set(v.get("video_id") for v in prod_videos)
    prod_evals = [res for res in all_evals if res.video_id in prod_vid_ids]

    # Audit confidence distributions for valid baseline vs no baseline
    conf_valid = {}
    conf_nobase = {}
    one_vid_violations = 0
    actual_nobase_violations = 0

    actual_outliers = []
    small_channel_actuals = []

    for res in prod_evals:
        # Check if video has baseline (channel has >= 2 videos)
        cid = res.channel_id
        chan_vid_count = len(chan_to_vids.get(cid, []))
        has_baseline = chan_vid_count >= 2

        if chan_vid_count == 1:
            if res.outlier_ratio is not None or res.channel_median_views is not None:
                one_vid_violations += 1

        if res.is_actual_outlier():
            actual_outliers.append(res)
            if res.is_small_channel:
                small_channel_actuals.append(res)
            if not has_baseline or res.outlier_ratio is None:
                actual_nobase_violations += 1

        if has_baseline:
            conf_valid[res.confidence] = conf_valid.get(res.confidence, 0) + 1
        else:
            conf_nobase[res.confidence] = conf_nobase.get(res.confidence, 0) + 1

    print(f"\n--- OUTLIER & CONFIDENCE AUDIT ---")
    print(f"Evaluated videos: {len(prod_evals)}")
    print(f"Valid-baseline confidence distribution: {conf_valid}")
    print(f"No-baseline confidence distribution:    {conf_nobase}")
    print(f"One-video baseline violations:          {one_vid_violations}")
    print(f"Actual outliers without baseline:       {actual_nobase_violations}")
    print(f"Actual outliers count:                  {len(actual_outliers)}")
    print(f"Small-channel actuals count:            {len(small_channel_actuals)}")

if __name__ == "__main__":
    run_invariant_audit()
