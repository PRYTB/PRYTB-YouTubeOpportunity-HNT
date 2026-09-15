"""
Sprint 13 Gate 2 Integration Tests.
Verifies all mandatory Gate 2 requirements and invariants.
"""

import json
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
GATE2_TOP20_JSON_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2_top20_opportunities.json"
GATE2_TOP5_JSON_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2_top5_opportunities.json"
GATE2_MD_PATH = ROOT_DIR / "docs" / "sprint13_gate2_top5_opportunities.md"

def test_gate2_artifacts_exist():
    assert GATE2_TOP20_JSON_PATH.exists()
    assert GATE2_TOP5_JSON_PATH.exists()
    assert GATE2_MD_PATH.exists()

def test_gate2_top20_structure():
    with open(GATE2_TOP20_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_canonical_subniches"] == 20
    assert len(data["items"]) == 20
    
    # Ranks 1 to 20
    ranks = [item["rank"] for item in data["items"]]
    assert ranks == list(range(1, 21))

def test_gate2_top5_structure():
    with open(GATE2_TOP5_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_selected_opportunities"] == 5
    assert len(data["items"]) == 5
    
    # Check top5 unique subniches
    subniches = [item["subniche"] for item in data["items"]]
    assert len(set(subniches)) == 5

def test_gate2_hash_consistency():
    with open(GATE2_TOP20_JSON_PATH, "r", encoding="utf-8") as f:
        top20_data = json.load(f)
    with open(GATE2_TOP5_JSON_PATH, "r", encoding="utf-8") as f:
        top5_data = json.load(f)
    
    assert top20_data["top5_hash"] == top5_data["top5_hash"]
    assert top20_data["gate1e_hash"] == top5_data["gate1e_hash"]
