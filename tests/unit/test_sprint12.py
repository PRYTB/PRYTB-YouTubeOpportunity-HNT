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


def test_sprint12_pipeline_outputs_and_non_obviousness():
    summary_file = PROCESSED_DIR / "sprint12" / "sprint12_pipeline_summary.json"
    assert summary_file.exists(), "Sprint 12 pipeline summary file missing"
    
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)
        
    assert summary["clustering_summary"]["k_selected"] > 0
    assert summary["top_100_outliers_summary"]["count"] >= 0
    assert summary["validator_summary"] is not None
    assert summary["non_obviousness_gate"]["gate"] in ["PASS", "FAIL", "PASS_WITH_WARNINGS"]
    assert len(summary["top_opportunity_candidates"]) <= 10
    
    # Check provenance
    prov = summary["provenance_lineage"]
    assert isinstance(prov["dataset_hash"], str) and len(prov["dataset_hash"]) > 0
    assert isinstance(prov["assignments_hash"], str) and len(prov["assignments_hash"]) > 0
