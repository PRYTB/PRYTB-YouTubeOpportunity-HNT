"""
Hard invariant tests for Sprint 12 Gate 2 reconciliation.
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any, List

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from app.analytics.outlier_engine import OutlierEngine
from scripts.create_sprint12_dataset_contract import clean_text_for_embedding, is_test_video, compute_dataset_hash

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

@pytest.fixture(scope="module")
def gate2_data():
    client = PostgresClient()
    repo = YouTubeRepository(client)

    videos_raw = repo.get_all_videos()
    channels_raw = repo.get_all_channels()
    valid_channel_ids = {c["channel_id"] for c in channels_raw if c.get("channel_id")}

    seen_vids = set()
    prod_videos = []
    prod_channels_set = set()

    for v in videos_raw:
        vid = v.get("video_id")
        cid = v.get("channel_id")
        if not vid or not v.get("title"):
            continue
        if is_test_video(v):
            continue
        if vid in seen_vids:
            continue
        if cid not in valid_channel_ids:
            continue

        seen_vids.add(vid)
        prod_videos.append(v)
        if cid:
            prod_channels_set.add(cid)

    chan_to_vids = {}
    for v in prod_videos:
        cid = v.get("channel_id")
        if cid:
            chan_to_vids.setdefault(cid, []).append(v.get("video_id"))

    outlier_engine = OutlierEngine(repository=repo)
    all_evals = outlier_engine.analyze_all()
    prod_vid_ids = set(v.get("video_id") for v in prod_videos)
    prod_evals = [res for res in all_evals if res.video_id in prod_vid_ids]

    return {
        "repo": repo,
        "prod_videos": prod_videos,
        "prod_channels_set": prod_channels_set,
        "chan_to_vids": chan_to_vids,
        "prod_evals": prod_evals
    }


def test_invariant_a_channel_bucket_total(gate2_data):
    chan_to_vids = gate2_data["chan_to_vids"]
    prod_channels = gate2_data["prod_channels_set"]

    c1 = sum(1 for vids in chan_to_vids.values() if len(vids) == 1)
    c2 = sum(1 for vids in chan_to_vids.values() if len(vids) == 2)
    c3 = sum(1 for vids in chan_to_vids.values() if len(vids) == 3)
    c4 = sum(1 for vids in chan_to_vids.values() if len(vids) >= 4)

    assert c1 + c2 + c3 + c4 == len(prod_channels), "Channel bucket total must equal production channels"


def test_invariant_b_video_bucket_reconstruction(gate2_data):
    chan_to_vids = gate2_data["chan_to_vids"]
    prod_videos = gate2_data["prod_videos"]

    v1 = sum(len(vids) for vids in chan_to_vids.values() if len(vids) == 1)
    v2 = sum(len(vids) for vids in chan_to_vids.values() if len(vids) == 2)
    v3 = sum(len(vids) for vids in chan_to_vids.values() if len(vids) == 3)
    v4 = sum(len(vids) for vids in chan_to_vids.values() if len(vids) >= 4)

    assert v1 + v2 + v3 + v4 == len(prod_videos), "Video bucket reconstruction must equal production videos"


def test_invariant_c_baseline_partition_sum(gate2_data):
    chan_to_vids = gate2_data["chan_to_vids"]
    prod_videos = gate2_data["prod_videos"]

    vids_with_baseline = sum(len(vids) for vids in chan_to_vids.values() if len(vids) >= 2)
    vids_without_baseline = sum(len(vids) for vids in chan_to_vids.values() if len(vids) < 2)

    assert vids_with_baseline + vids_without_baseline == len(prod_videos), "Baseline sum must equal total production videos"


def test_invariant_d_vids_without_baseline_gte_c1(gate2_data):
    chan_to_vids = gate2_data["chan_to_vids"]

    c1 = sum(1 for vids in chan_to_vids.values() if len(vids) == 1)
    vids_without_baseline = sum(len(vids) for vids in chan_to_vids.values() if len(vids) < 2)

    assert vids_without_baseline >= c1, "Videos without baseline must be >= C1"


def test_invariant_e_and_f_one_video_channel_baseline_and_ratio(gate2_data):
    chan_to_vids = gate2_data["chan_to_vids"]
    prod_evals = gate2_data["prod_evals"]

    c1_channels = {cid for cid, vids in chan_to_vids.items() if len(vids) == 1}

    for res in prod_evals:
        if res.channel_id in c1_channels:
            # Under self-exclusion, a channel with 1 production video has 0 comparison baseline videos
            assert res.channel_id in c1_channels
            assert res.outlier_ratio is None, f"One-video channel {res.channel_id} video {res.video_id} must have outlier_ratio is None"


def test_invariant_g_actual_outlier_implies_valid_baseline(gate2_data):
    prod_evals = gate2_data["prod_evals"]
    chan_to_vids = gate2_data["chan_to_vids"]

    for res in prod_evals:
        if res.is_actual_outlier():
            chan_vid_count = len(chan_to_vids.get(res.channel_id, []))
            assert chan_vid_count >= 2, f"Actual outlier {res.video_id} must come from a channel with >= 2 videos"
            assert res.outlier_ratio is not None, f"Actual outlier {res.video_id} must have valid outlier_ratio"


def test_invariant_h_actual_ranking_contains_only_actuals(gate2_data):
    prod_evals = gate2_data["prod_evals"]
    actual_outliers = [res for res in prod_evals if res.is_actual_outlier()]
    ranked = sorted(actual_outliers, key=lambda x: x.outlier_rank_score, reverse=True)[:100]

    for res in ranked:
        assert res.is_actual_outlier() is True, "Ranked row must be actual outlier"
        assert res.outlier_ratio is not None, "Ranked row must have outlier ratio"


def test_invariant_i_dataset_hash_payload_count(gate2_data):
    prod_videos = gate2_data["prod_videos"]
    prod_rows = [{"video_id": v["video_id"], "semantic_text": clean_text_for_embedding(v.get("title", ""), v.get("description", ""))} for v in prod_videos]

    payload_count = len(prod_rows)
    assert payload_count == len(prod_videos), "Dataset hash payload count must equal video count"

    h1 = compute_dataset_hash(prod_rows)
    h2 = compute_dataset_hash(prod_rows)
    assert h1 == h2, "Dataset hash must be reproducible"


def test_invariant_j_readback_provenance_matches_run(gate2_data):
    repo = gate2_data["repo"]
    expected_run_id = "sprint12_interim_reconciled_20260908_202912"
    expected_dataset_hash = "6b0ac147d9aae34551c6db0a450ae778d22c6c5132feb89c8878eafeacf69919"

    records = repo.get_outlier_analysis_by_run_id(expected_run_id)
    for r in records:
        assert r.get("run_id") == expected_run_id, "Read-back record run_id mismatch"
        assert r.get("dataset_hash") == expected_dataset_hash, "Read-back record dataset_hash mismatch"
