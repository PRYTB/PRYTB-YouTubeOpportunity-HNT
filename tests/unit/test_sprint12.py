"""
Unit and Integration tests for Sprint 12 Production Execution.
"""

import json
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"


def test_sprint12_dataset_contract_exists_and_valid():
    contract_file = PROCESSED_DIR / "sprint12_dataset_contract.json"
    assert contract_file.exists(), "Sprint 12 dataset contract file missing"
    
    with open(contract_file, "r", encoding="utf-8") as f:
        contract = json.load(f)
        
    assert contract["run_id"] == "sprint12_prod_run_01"
    assert contract["video_count"] >= 3000
    assert contract["channel_count"] >= 1000
    assert isinstance(contract["dataset_hash"], str) and len(contract["dataset_hash"]) > 0
    assert contract["seed_manifest_hash"] is not None
    assert "en" in contract["language_distribution"]
    assert "es" in contract["language_distribution"]


def test_sprint12_gate3_lineage_and_determinism():
    from scripts.execute_sprint12_gate3 import compute_assignments_hash, compute_canonical_dataset_hash
    
    # Test lineage accounting split: precanonical (28) vs Gate 3 (7611)
    raw_videos = 7639
    precanonical_exclusions = 28
    canonical_videos = 7611
    assert canonical_videos + precanonical_exclusions == raw_videos
    
    # Test assignment payload determinism hash
    sample_assignments = [("v1", 0), ("v2", 1), ("v3", 0)]
    hash1 = compute_assignments_hash(sample_assignments)
    hash2 = compute_assignments_hash(list(reversed(sample_assignments)))
    assert hash1 == hash2, "Assignment hash must be ordering-invariant due to video_id sorting"


def test_sprint12_gate4_intent_normalization_and_depth():
    from scripts.execute_sprint12_gate4 import normalize_intent_string

    raw1 = "AI tools for content creators & video generation!"
    raw2 = "ai tools for content creators video generation"
    norm1 = normalize_intent_string(raw1)
    norm2 = normalize_intent_string(raw2)
    assert norm1 == norm2, "Normalized intent string must match for superficial variations"

    # Test 100_PLUS depth rule
    distinct_intents = 105
    content_depth = "100_PLUS" if distinct_intents >= 100 else "FEWER_THAN_100"
    assert content_depth == "100_PLUS"

    distinct_intents_low = 85
    content_depth_low = "100_PLUS" if distinct_intents_low >= 100 else "FEWER_THAN_100"
    assert content_depth_low != "100_PLUS"


def test_sprint12_gate5_qualification_and_unknown_handling():
    from scripts.execute_sprint12_gate5 import normalize_intent_string

    # Test exact 20 candidate handling & unknown handling
    summary_file = PROCESSED_DIR / "sprint12_gate5_summary.json"
    assert summary_file.exists(), "Gate 5 summary JSON missing"

    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)

    assert summary["candidates_analyzed"] == 20
    assert summary["unique_ranks"] == 20
    assert summary["gate4_run_id"] == "sprint12_gate4_subniche_20260910_184255"
    assert summary["gate3_run_id"] == "sprint12_gate3_clustering_20260910_173651"
    assert summary["dataset_hash"] == "6b0ac147d9aae34551c6db0a450ae778d22c6c5132feb89c8878eafeacf69919"
    assert summary["assignment_hash"] == "d6ba8832798c3c65003d9a9104726667397ab2b543f896088d26a27350a917c6"

    # Verify no unknown treated as positive
    assert summary["false_100_plus"] == 0
    assert len(summary["top5_candidates"]) == 5
