"""
Sprint 13 Gate 2A Integration Tests.
Verifies economic score integrity, provenance, range coverage, and classification.
"""

import json
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
GATE2A_SCORE_INTEGRITY_JSON = ROOT_DIR / "data" / "processed" / "sprint13_gate2a_score_integrity.json"
GATE2A_RANK20_JSON = ROOT_DIR / "data" / "processed" / "sprint13_gate2a_rank20.json"
GATE2A_TOP5_RANKED_JSON = ROOT_DIR / "data" / "processed" / "sprint13_gate2a_top5_ranked.json"
GATE2A_MD_PATH = ROOT_DIR / "docs" / "sprint13_gate2a_economic_integrity.md"

def test_gate2a_artifacts_exist():
    assert GATE2A_SCORE_INTEGRITY_JSON.exists()
    assert GATE2A_RANK20_JSON.exists()
    assert GATE2A_TOP5_RANKED_JSON.exists()
    assert GATE2A_MD_PATH.exists()

def test_gate2a_rank20_structure():
    with open(GATE2A_RANK20_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_canonical_subniches"] == 20
    assert len(data["items"]) == 20

    for item in data["items"]:
        # Verify classification bounds
        prof_score = item["profitability_score"]
        cls = item["classification"]
        if prof_score >= 90.0:
            assert cls == "EXCEPTIONAL"
        elif prof_score >= 80.0:
            assert cls == "STRONG"
        elif prof_score >= 70.0:
            assert cls == "INTERESTING"
        elif prof_score >= 50.0:
            assert cls == "OBSERVE"
        else:
            assert cls == "DISCARD"

        # Verify monetary presence
            assert item["has_views"] is True

def test_gate2a_top5_ranked_structure():
    with open(GATE2A_TOP5_RANKED_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_selected_candidates"] == 5
    assert len(data["items"]) == 5

def test_gate2a_reconstruction_precision():
    with open(GATE2A_RANK20_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data["items"]:
        stored = item["profitability_score"]
        reconstructed = item["reconstructed_profitability_score"]
        assert abs(stored - reconstructed) < 0.001
