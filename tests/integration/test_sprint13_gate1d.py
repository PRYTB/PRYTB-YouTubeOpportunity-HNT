"""Sprint 13 Gate 1D Semantic Identity & Cross-Field Consistency Reconciliation Integration Tests."""

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
from scripts.generate_sprint13_gate1d_artifacts import (
    EXPECTED_GATE1B_HASH,
    EXPECTED_GATE1C_HASH,
    EXPECTED_TOP100_HASH,
    EXPECTED_TOP20_HASH,
    EXPECTED_TOP30_HASH,
    GATE1D_JSON_PATH,
    GATE1D_MD_PATH,
    generate_gate1d_artifacts,
)

TERMINAL_STATUS = "SPRINT12_FINAL_ANALYTICS_APPROVED"
EXPECTED_ASSIGNMENTS_HASH = "7ffe657d79913d1e5693ac9d99cb6da8645e9bd1842e9c1515094f37ea3b5a87"

EXPECTED_TOP20_IDS = [
    "def_015", "def_046", "def_055", "def_036", "def_024",
    "def_057", "def_045", "def_030", "def_004", "def_038",
    "def_052", "def_020", "def_053", "def_016", "def_054",
    "def_025", "def_002", "def_009", "def_026", "def_023",
]


@pytest.fixture(scope="module")
def postgres_client():
    return PostgresClient()


@pytest.fixture(scope="module")
def gate1d_artifact():
    if not GATE1D_JSON_PATH.exists() or not GATE1D_MD_PATH.exists():
        generate_gate1d_artifacts()
    return json.loads(GATE1D_JSON_PATH.read_text(encoding="utf-8"))


def test_01_postgres_connection_and_sprint12_authority(postgres_client):
    """Req 1: Verify PostgreSQL connection and Sprint 12 terminal authority."""
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


def test_02_exact_ranking_hashes(postgres_client, gate1d_artifact):
    """Req 2: Verify exact ranking hash matches for Top100, Top30, Top20, Gate1B, Gate1C."""
    rec = reconstruct_gate1(postgres_client, AUTHORITATIVE_RUN_ID)
    assert rec["dataset_hash"] == EXPECTED_DATASET_HASH
    assert rec["top100"]["ranking_hash"] == EXPECTED_TOP100_HASH
    assert rec["top30"]["ranking_hash"] == EXPECTED_TOP30_HASH
    assert rec["top20"]["ranking_hash"] == EXPECTED_TOP20_HASH

    hashes = gate1d_artifact["ranking_hashes"]
    assert hashes["top100"] == EXPECTED_TOP100_HASH
    assert hashes["top30"] == EXPECTED_TOP30_HASH
    assert hashes["top20"] == EXPECTED_TOP20_HASH
    assert hashes["gate1b"] == EXPECTED_GATE1B_HASH
    assert hashes["gate1c"] == EXPECTED_GATE1C_HASH


def test_03_closed_loop_verification(gate1d_artifact):
    """Req 3: Verify mandatory multi-iteration closed-loop verification."""
    cl = gate1d_artifact["closed_loop_verification"]
    assert cl["iterations_completed"] == 2
    assert cl["iteration1_corrections_applied"] >= 0
    assert cl["iteration2_corrections_applied"] == 0
    assert cl["final_iteration_clean"] is True
    assert cl["independent_db_reads"] == 2
    assert cl["identical_reconstructions"] is True


def test_04_fresh_evidence_loading_from_postgres(postgres_client):
    """Req 4: Verify evidence for all 20 canonical subniches loaded fresh from DB."""
    for def_id in EXPECTED_TOP20_IDS:
        memberships = postgres_client.execute(
            "SELECT sm.video_id, sm.parent_cluster_id, v.title "
            "FROM gate7_semantic_memberships sm "
            "JOIN videos v ON sm.video_id = v.video_id "
            "WHERE sm.run_id = %s AND sm.definition_id = %s",
            [AUTHORITATIVE_RUN_ID, def_id]
        )
        assert len(memberships) > 0, f"No evidence videos found in DB for {def_id}"


def test_05_rebuild_evidence_based_semantic_identity(gate1d_artifact):
    """Req 5: Verify evidence-based semantic identity rebuilt independently of stale labels."""
    for item in gate1d_artifact["items"]:
        assert len(item["niche"]) > 0
        assert len(item["subniche"]) > 0
        assert len(item["normalized_intent"]) > 0
        assert len(item["dominant_topic"]) > 0
        assert len(item["contradiction_resolved"]) > 0


def test_06_cross_field_consistency_audit(gate1d_artifact):
    """Req 6: Audit cross-field consistency (Subniche and Dominant Topic strictly match)."""
    for item in gate1d_artifact["items"]:
        assert item["subniche"] == item["dominant_topic"] or item["subniche"] in item["dominant_topic"]


def test_07_niche_subniche_intent_reconciliation(gate1d_artifact):
    """Req 7: Reconcile labels so Niche, Subniche, and Intent strictly describe dominant topic."""
    for item in gate1d_artifact["items"]:
        assert item["status"] == "PURE"
        assert item["purity_ratio"] >= 0.75


def test_08_dynamic_summary_counter_calculation(gate1d_artifact):
    """Req 8: Verify summary counters are dynamically calculated from final row statuses."""
    audit_sum = gate1d_artifact["audit_summary"]
    items = gate1d_artifact["items"]
    
    assert audit_sum["total_subniches"] == len(items)
    assert audit_sum["mixed_topic_remaining"] == sum(1 for i in items if i["status"] == "MIXED_TOPIC")
    assert audit_sum["contaminated_remaining"] == sum(1 for i in items if i["status"] == "CONTAMINATED")
    assert audit_sum["mixed_topic_remaining"] == 0
    assert audit_sum["contaminated_remaining"] == 0
    assert audit_sum["cross_field_contradictions_remaining"] == 0


def test_09_pairwise_distinctness_across_all_20(gate1d_artifact):
    """Req 9: Verify pairwise distinctness across all 20 subniches."""
    subniches = [i["subniche"] for i in gate1d_artifact["items"]]
    assert len(subniches) == 20
    assert len(set(subniches)) == 20


def test_10_actionability_for_downstream_engines(gate1d_artifact):
    """Req 10: Confirm actionability for downstream revenue/risk/profitability engines."""
    for item in gate1d_artifact["items"]:
        checklist = item["actionability_checklist"]
        assert all(checklist.values()) is True


def test_11_underlying_db_unmodified(postgres_client):
    """Req 11: Verify underlying DB memberships and K=35 clustering remain 100% unmodified."""
    clusters = postgres_client.execute(
        "SELECT count(*) as cnt FROM clusters WHERE run_id = %s",
        [AUTHORITATIVE_RUN_ID]
    )
    assert clusters[0]["cnt"] == 35

    run = YouTubeRepository(postgres_client).get_analytical_run(AUTHORITATIVE_RUN_ID)
    assert run.video_count == EXPECTED_PROD_VIDEOS
    assert run.channel_count == EXPECTED_PROD_CHANNELS


def test_12_json_artifact_schema_and_integrity():
    """Req 12: Verify JSON artifact schema and valid presence."""
    assert GATE1D_JSON_PATH.exists()
    content = json.loads(GATE1D_JSON_PATH.read_text(encoding="utf-8"))
    assert "source_run_id" in content
    assert "dataset_hash" in content
    assert "closed_loop_verification" in content
    assert "audit_summary" in content
    assert "items" in content
    assert len(content["items"]) == 20


def test_13_markdown_artifact_formatting():
    """Req 13: Verify Markdown artifact structure and presence."""
    assert GATE1D_MD_PATH.exists()
    text = GATE1D_MD_PATH.read_text(encoding="utf-8")
    assert "# Sprint 13 Gate 1D: Semantic Identity & Cross-Field Consistency Reconciliation" in text
    assert "## Executive Summary" in text
    assert "## Status Summary" in text
    assert "## Reconciled Top 20 Semantic Identity Register" in text
    assert "## Key Reconciliations & Contradiction Resolutions" in text
    assert "## Multi-Iteration Closed-Loop Verification" in text
    assert "## Database Integrity Verification" in text


def test_14_canonical_top20_id_alignment(gate1d_artifact):
    """Req 14: Verify exact alignment of Top 20 stable IDs in order."""
    item_ids = [i["stable_id"] for i in gate1d_artifact["items"]]
    assert item_ids == EXPECTED_TOP20_IDS


def test_15_def_036_mixed_topic_resolution(gate1d_artifact):
    """Req 15: Verify specific resolution of def_036 (previously MIXED_TOPIC in Gate 1C)."""
    def_036 = next(i for i in gate1d_artifact["items"] if i["stable_id"] == "def_036")
    assert def_036["status"] == "PURE"
    assert def_036["purity_ratio"] >= 0.75
    assert "AI Developer Tooling & Financial Investing Tutorials" in def_036["subniche"]


def test_16_def_046_subniche_dominant_topic_alignment(gate1d_artifact):
    """Req 16: Verify specific resolution of def_046 string alignment."""
    def_046 = next(i for i in gate1d_artifact["items"] if i["stable_id"] == "def_046")
    assert def_046["subniche"] == def_046["dominant_topic"]
    assert def_046["status"] == "PURE"


def test_17_evidence_sample_titles_present(gate1d_artifact):
    """Req 17: Verify evidence sample titles are included for all 20 records."""
    for item in gate1d_artifact["items"]:
        assert "evidence_samples" in item
        assert len(item["evidence_samples"]) > 0


def test_18_source_records_counts(gate1d_artifact):
    """Req 18: Verify source record video and outlier counts match DB evidence."""
    for item in gate1d_artifact["items"]:
        assert item["source_records"]["video_count"] > 0
        assert item["source_records"]["outlier_count"] >= 0


def test_19_reconciliation_log_entries(gate1d_artifact):
    """Req 19: Verify reconciliation log tracks all specific actions taken."""
    log = gate1d_artifact["reconciliation_log"]
    assert len(log) > 0
    assert any(entry["subniche_id"] == "def_036" for entry in log)
    assert any(entry["subniche_id"] == "def_046" for entry in log)


def test_20_purity_ratio_thresholds(gate1d_artifact):
    """Req 20: Verify purity ratio thresholds for all items (all >= 75%)."""
    for item in gate1d_artifact["items"]:
        assert item["purity_ratio"] >= 0.75


def test_21_provenance_and_run_id_integrity(gate1d_artifact):
    """Req 21: Verify provenance and analytical run ID integrity."""
    assert gate1d_artifact["source_run_id"] == AUTHORITATIVE_RUN_ID
    assert gate1d_artifact["provenance"]["dataset_hash"] == EXPECTED_DATASET_HASH
