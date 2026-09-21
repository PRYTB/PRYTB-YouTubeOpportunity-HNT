"""Integration and deterministic validation tests for Sprint 13 Gate 3 Qualified Pool Expansion."""

import json
from pathlib import Path
import pytest

from scripts.sprint13_gate3_runner import Sprint13Gate3Runner, execute_gate3, GATE3_RUN_ID, AUTHORITATIVE_RUN_ID
from app.database.postgres_client import PostgresClient

pytestmark = pytest.mark.integration

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SUMMARY_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate3_expansion_summary.json"


def test_gate3_summary_artifact_exists_and_valid():
    """Verify that the Gate 3 expansion summary artifact exists and contains valid required fields."""
    assert SUMMARY_PATH.exists(), f"Artifact not found at {SUMMARY_PATH}"
    data = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    assert data["run_id"] == GATE3_RUN_ID
    assert data["authoritative_run_id"] == AUTHORITATIVE_RUN_ID
    assert data["governance"]["sprint"] == 13
    assert data["governance"]["gate"] == "GATE3 QUALIFIED POOL EXPANSION"
    assert data["governance"]["top3_selected"] == "NO"

    # Universe counts validation
    ub = data["universe_breakdown"]
    assert ub["total_definitions"] == 58
    assert ub["top20_canonical"] == 20
    assert ub["expansion_definitions"] == 38
    assert ub["excluded_artifacts"] == 8
    assert ub["eligible_expansion"] == 30

    # Baseline preservation validation
    bp = data["baseline_preservation"]
    assert bp["baseline_qualified_count"] == 2
    assert "def_045" in bp["baseline_qualified_ids"] or "def_052" in bp["baseline_qualified_ids"]
    assert bp["def_045_score"] in (50.0641, 50.0564)

    # Expansion results validation
    exp = data["expansion_results"]
    assert exp["expansion_qualified_count"] == 1
    assert len(exp["expansion_qualified_candidates"]) == 1
    exp_q = exp["expansion_qualified_candidates"][0]
    assert exp_q["definition_id"] == "def_039"
    assert exp_q["profitability_score"] == 50.0564

    # Total qualified pool validation
    qp = data["qualified_pool_summary"]
    assert qp["total_qualified_count"] == 3
    assert set(qp["total_qualified_ids"]) == {"def_045", "def_052", "def_039"}

    # Governance conditions
    assert data["governance"]["at_least_three_condition"] == "MET"
    assert data["governance"]["top3_review_readiness"] == "YES"


def test_gate3_runner_determinism_and_exclusion_audit():
    """Test runner execution, candidate universe classification, and exclusion audit."""
    runner = Sprint13Gate3Runner()
    all_defs, top20_defs, expansion_defs, excluded_defs, eligible_expansion_defs = runner.load_universe_and_definitions()

    assert len(all_defs) == 58
    assert len(top20_defs) == 20
    assert len(expansion_defs) == 38
    assert len(excluded_defs) == 8
    assert len(eligible_expansion_defs) == 30

    # Ensure all excluded candidates have zero outliers or single channel
    for ex in excluded_defs:
        assert ex.get("channel_count", 0) <= 1 or ex.get("outlier_count", 0) == 0 or ex.get("video_count", 0) < 1

    # Run scoring
    res = runner.run_expansion_scoring()
    assert res["total_qualified_pool_count"] == 3
    assert res["at_least_three_condition"] == "MET"
    assert res["top3_review_readiness"] == "YES"
    assert res["top3_selected"] == "NO"


def test_gate3_postgresql_persistence_and_readback():
    """Verify Gate 3 run record persistence and dual-read verification in PostgreSQL."""
    client = PostgresClient()
    rows = client.execute("SELECT * FROM public.analytical_runs WHERE run_id = %s", [GATE3_RUN_ID])
    assert len(rows) == 1, f"Expected 1 record in analytical_runs for {GATE3_RUN_ID}, got {len(rows)}"

    row = rows[0]
    assert row["run_type"] == "GATE3_QUALIFIED_POOL_EXPANSION"
    assert row["status"] == "APPROVED_GATE3_EXPANDED"

    notes = row["notes"]
    if isinstance(notes, str):
        notes = json.loads(notes)

    assert notes["authoritative_run_id"] == AUTHORITATIVE_RUN_ID
    assert notes["total_qualified_pool_count"] == 3
    assert notes["at_least_three_condition"] == "MET"
    assert notes["top3_review_readiness"] == "YES"
    assert notes["top3_selected"] == "NO"
