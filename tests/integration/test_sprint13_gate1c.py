"""Sprint 13 Gate 1C Semantic Purity & Membership Reconciliation Integration Tests."""

import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from scripts.sprint12_reproducibility_constants import (
    EXPECTED_DATASET_HASH,
    EXPECTED_PROD_CHANNELS,
    EXPECTED_PROD_VIDEOS,
)
from scripts.sprint13_gate1_reconstruction import (
    AUTHORITATIVE_RUN_ID,
    reconstruct_gate1,
)
from scripts.generate_sprint13_gate1c_artifacts import (
    EXPECTED_GATE1B_HASH,
    EXPECTED_TOP100_HASH,
    EXPECTED_TOP20_HASH,
    EXPECTED_TOP30_HASH,
    GATE1C_JSON_PATH,
    GATE1C_MD_PATH,
    generate_gate1c_artifacts,
)

TERMINAL_STATUS = "SPRINT12_FINAL_ANALYTICS_APPROVED"
EXPECTED_ASSIGNMENTS_HASH = "7ffe657d79913d1e5693ac9d99cb6da8645e9bd1842e9c1515094f37ea3b5a87"

EXPECTED_TOP20_IDS = [
    "def_015", "def_046", "def_055", "def_036", "def_024",
    "def_057", "def_045", "def_030", "def_004", "def_038",
    "def_052", "def_020", "def_053", "def_016", "def_054",
    "def_025", "def_002", "def_009", "def_026", "def_023",
]

VALID_PURITY_CLASSIFICATIONS = {
    "PURE", "MINOR_NOISE", "MIXED_TOPIC", "CONTAMINATED", "AMBIGUOUS"
}


@pytest.fixture(scope="module")
def postgres_client():
    return PostgresClient()


@pytest.fixture(scope="module")
def gate1c_artifact():
    if not GATE1C_JSON_PATH.exists() or not GATE1C_MD_PATH.exists():
        generate_gate1c_artifacts()
    return json.loads(GATE1C_JSON_PATH.read_text(encoding="utf-8"))


def test_01_postgres_connection_and_sprint12_authority(postgres_client):
    """Requirement 1: Verify PostgreSQL connection and Sprint 12 terminal authority."""
    rows = postgres_client.execute("SELECT current_database(), current_user;")
    assert rows == [{"current_database": "prytb", "current_user": "prytb_app"}]

    run = YouTubeRepository(postgres_client).get_analytical_run(AUTHORITATIVE_RUN_ID)
    assert run is not None
    assert run.status == TERMINAL_STATUS
    assert run.dataset_hash == EXPECTED_DATASET_HASH
    assert run.video_count == EXPECTED_PROD_VIDEOS
    assert run.channel_count == EXPECTED_PROD_CHANNELS
    
    notes = json.loads(run.notes)
    assert notes["assignments_hash"] == EXPECTED_ASSIGNMENTS_HASH
    assert notes["selected_k"] == 35


def test_02_exact_ranking_hashes(postgres_client, gate1c_artifact):
    """Requirement 2: Verify exact ranking hash matches for Top100, Top30, Top20, and Gate1B."""
    rec = reconstruct_gate1(postgres_client, AUTHORITATIVE_RUN_ID)
    assert rec["dataset_hash"] == EXPECTED_DATASET_HASH
    assert rec["top100"]["ranking_hash"] == EXPECTED_TOP100_HASH
    assert rec["top30"]["ranking_hash"] == EXPECTED_TOP30_HASH
    assert rec["top20"]["ranking_hash"] == EXPECTED_TOP20_HASH
    
    hashes = gate1c_artifact["ranking_hashes"]
    assert hashes["top100"] == EXPECTED_TOP100_HASH
    assert hashes["top30"] == EXPECTED_TOP30_HASH
    assert hashes["top20"] == EXPECTED_TOP20_HASH
    assert hashes["gate1b"] == EXPECTED_GATE1B_HASH


def test_03_closed_loop_dual_read_verification(gate1c_artifact):
    """Requirement 3: Verify mandatory closed-loop dual read verification."""
    closed_loop = gate1c_artifact["closed_loop"]
    assert closed_loop["read_count"] == 2
    assert closed_loop["independent_clients"] is True
    assert closed_loop["identical_reconstructions"] is True
    assert closed_loop["ranking_hashes_equal"] is True
    assert closed_loop["first_read_hash"] == closed_loop["second_read_hash"]
    assert closed_loop["gate1b_hash_matches"] is True
    assert closed_loop["final_iteration_defects_remaining"] == 0


def test_04_top20_item_count_and_ordering(gate1c_artifact):
    """Requirement 4: Verify exactly 20 records in exact rank order matching Gate 1 canonical IDs."""
    items = gate1c_artifact["items"]
    assert len(items) == 20
    ranks = [item["rank"] for item in items]
    assert ranks == list(range(1, 21))

    ids = [item["stable_id"] for item in items]
    assert ids == EXPECTED_TOP20_IDS


def test_05_complete_evidence_loaded(postgres_client, gate1c_artifact):
    """Requirement 5: Verify all 20 subniches have complete evidence loaded from DB."""
    for item in gate1c_artifact["items"]:
        def_id = item["stable_id"]
        memberships = postgres_client.execute(
            "SELECT video_id FROM gate7_semantic_memberships WHERE run_id = %s AND definition_id = %s",
            [AUTHORITATIVE_RUN_ID, def_id]
        )
        assert len(memberships) > 0
        assert len(memberships) == item["total_videos"]
        assert len(item["evidence_samples"]) > 0
        assert item["source_records"]["supporting_cluster_ids"] is not None


def test_06_deterministic_purity_ratio_calculation(gate1c_artifact):
    """Requirement 6: Verify purity ratio calculation for all 20 subniches."""
    for item in gate1c_artifact["items"]:
        expected_ratio = round(item["dominant_evidence_count"] / item["total_videos"], 4)
        assert item["purity_ratio"] == expected_ratio
        assert item["dominant_evidence_count"] + item["off_topic_count"] == item["total_videos"]


def test_07_valid_purity_classifications(gate1c_artifact):
    """Requirement 7: Verify all 20 subniches have valid purity classifications."""
    for item in gate1c_artifact["items"]:
        assert item["purity_classification"] in VALID_PURITY_CLASSIFICATIONS


def test_08_purity_ratio_threshold_invariants(gate1c_artifact):
    """Requirement 8: Verify purity ratio threshold invariants for classifications."""
    for item in gate1c_artifact["items"]:
        ratio = item["purity_ratio"]
        cls = item["purity_classification"]
        if cls == "PURE":
            assert ratio >= 0.90
        elif cls == "MINOR_NOISE":
            assert 0.75 <= ratio < 0.90
        elif cls == "MIXED_TOPIC":
            assert 0.60 <= ratio < 0.75


def test_09_specific_purity_audit_def_036(gate1c_artifact):
    """Requirement 9: Specific purity audit for def_036 (MIXED_TOPIC)."""
    item = next(i for i in gate1c_artifact["items"] if i["stable_id"] == "def_036")
    assert item["purity_classification"] == "MIXED_TOPIC"
    assert item["purity_ratio"] == 0.7259
    assert item["total_videos"] == 602
    assert item["dominant_evidence_count"] == 437
    assert item["off_topic_count"] == 165
    
    defect = next(d for d in gate1c_artifact["defect_register"] if d["subniche_id"] == "def_036")
    assert defect["resolved"] is True
    assert defect["status"] == "RESOLVED_SAFE_RECONCILIATION"


def test_10_specific_purity_audit_def_046(gate1c_artifact):
    """Requirement 10: Specific purity audit for def_046 (MINOR_NOISE)."""
    item = next(i for i in gate1c_artifact["items"] if i["stable_id"] == "def_046")
    assert item["purity_classification"] == "MINOR_NOISE"
    assert item["purity_ratio"] == 0.7887
    assert item["total_videos"] == 672
    
    defect = next(d for d in gate1c_artifact["defect_register"] if d["subniche_id"] == "def_046")
    assert defect["resolved"] is True


def test_11_specific_purity_audit_def_024(gate1c_artifact):
    """Requirement 11: Specific purity audit for def_024 (MINOR_NOISE)."""
    item = next(i for i in gate1c_artifact["items"] if i["stable_id"] == "def_024")
    assert item["purity_classification"] == "MINOR_NOISE"
    assert item["purity_ratio"] == 0.7932
    assert item["total_videos"] == 324
    
    defect = next(d for d in gate1c_artifact["defect_register"] if d["subniche_id"] == "def_024")
    assert defect["resolved"] is True


def test_12_specific_purity_audit_def_004(gate1c_artifact):
    """Requirement 12: Specific purity audit for def_004 (MINOR_NOISE)."""
    item = next(i for i in gate1c_artifact["items"] if i["stable_id"] == "def_004")
    assert item["purity_classification"] == "MINOR_NOISE"
    assert item["purity_ratio"] == 0.8714
    assert item["total_videos"] == 280
    
    defect = next(d for d in gate1c_artifact["defect_register"] if d["subniche_id"] == "def_004")
    assert defect["resolved"] is True


def test_13_specific_purity_audit_def_016(gate1c_artifact):
    """Requirement 13: Specific purity audit for def_016 (MINOR_NOISE)."""
    item = next(i for i in gate1c_artifact["items"] if i["stable_id"] == "def_016")
    assert item["purity_classification"] == "MINOR_NOISE"
    assert item["purity_ratio"] == 0.8187
    assert item["total_videos"] == 171
    
    defect = next(d for d in gate1c_artifact["defect_register"] if d["subniche_id"] == "def_016")
    assert defect["resolved"] is True


def test_14_defect_register_completeness(gate1c_artifact):
    """Requirement 14: Defect register completeness and schema validation."""
    defects = gate1c_artifact["defect_register"]
    assert len(defects) >= 6
    required_fields = {
        "defect_id", "subniche_id", "status", "problem",
        "root_cause", "affected_clusters", "evidence",
        "severity", "safe_fix", "iteration", "resolved"
    }
    for d in defects:
        assert required_fields.issubset(set(d.keys()))
        assert d["resolved"] is True


def test_15_zero_unresolved_defects(gate1c_artifact):
    """Requirement 15: Zero remaining unresolved defects in the final iteration."""
    purity_summary = gate1c_artifact["purity_summary"]
    assert purity_summary["total_unresolved_defects"] == 0
    assert gate1c_artifact["closed_loop"]["final_iteration_defects_remaining"] == 0


def test_16_zero_invalid_duplicates_or_overlaps(gate1c_artifact):
    """Requirement 16: Zero invalid duplicates or invalid semantic overlaps across all 20 subniches."""
    items = gate1c_artifact["items"]
    subniche_titles = [item["reconciled_subniche"] for item in items]
    assert len(subniche_titles) == len(set(subniche_titles))
    
    intents = [item["reconciled_intent"] for item in items]
    assert len(intents) == len(set(intents))


def test_17_actionability_all_pass(gate1c_artifact):
    """Requirement 17: All 20 subniches answer YES to all 6 actionability questions."""
    for item in gate1c_artifact["items"]:
        checklist = item["actionability_checklist"]
        assert all(checklist.values()) is True
    assert gate1c_artifact["purity_summary"]["actionability_all_pass"] is True


def test_18_underlying_db_unmodified(postgres_client):
    """Requirement 18: Underlying Sprint12 K=35 clustering and DB records are 100% unmodified."""
    clusters = postgres_client.execute(
        "SELECT count(*) as cnt FROM clusters WHERE run_id = %s",
        [AUTHORITATIVE_RUN_ID]
    )
    assert clusters[0]["cnt"] == 35

    run = YouTubeRepository(postgres_client).get_analytical_run(AUTHORITATIVE_RUN_ID)
    assert run.video_count == EXPECTED_PROD_VIDEOS
    assert run.channel_count == EXPECTED_PROD_CHANNELS


def test_19_artifact_files_exist_and_non_empty():
    """Requirement 19: Verify both Gate 1C artifact files exist and are non-empty."""
    assert GATE1C_JSON_PATH.exists()
    assert GATE1C_JSON_PATH.stat().st_size > 1000
    assert GATE1C_MD_PATH.exists()
    assert GATE1C_MD_PATH.stat().st_size > 1000


def test_20_schema_validation_json(gate1c_artifact):
    """Requirement 20: Schema validation for sprint13_gate1c_semantic_purity.json."""
    required_top_keys = {
        "source_run_id", "dataset_hash", "provenance", "closed_loop",
        "ranking_hashes", "purity_summary", "defect_register", "items"
    }
    assert required_top_keys.issubset(set(gate1c_artifact.keys()))
    assert gate1c_artifact["source_run_id"] == AUTHORITATIVE_RUN_ID
    assert gate1c_artifact["dataset_hash"] == EXPECTED_DATASET_HASH


def test_21_markdown_documentation_contents():
    """Requirement 21: Verify markdown documentation contains all required sections and tables."""
    content = GATE1C_MD_PATH.read_text(encoding="utf-8")
    assert "# Sprint 13 Gate 1C: Semantic Purity & Membership Reconciliation" in content
    assert "## Executive Summary" in content
    assert "## Purity Classification Summary" in content
    assert "## Complete Top 20 Semantic Purity Register" in content
    assert "## High-Risk Subniche Purity Analysis" in content
    assert "## Defect Register Summary" in content
    assert "## Closed-Loop Verification" in content
    assert EXPECTED_DATASET_HASH in content
    assert EXPECTED_TOP20_HASH in content
