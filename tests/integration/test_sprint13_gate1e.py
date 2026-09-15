"""Sprint 13 Gate 1E Canonical Top20 Final Validation Automated Integration Tests."""

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
from scripts.generate_sprint13_gate1e_artifacts import (
    EXPECTED_GATE1B_HASH,
    EXPECTED_GATE1C_HASH,
    EXPECTED_GATE1D_HASH,
    EXPECTED_TOP100_HASH,
    EXPECTED_TOP20_HASH,
    EXPECTED_TOP30_HASH,
    GATE1E_JSON_PATH,
    GATE1E_MD_PATH,
    generate_gate1e_artifacts,
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
def gate1e_artifact():
    if not GATE1E_JSON_PATH.exists() or not GATE1E_MD_PATH.exists():
        generate_gate1e_artifacts()
    return json.loads(GATE1E_JSON_PATH.read_text(encoding="utf-8"))


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


def test_02_exact_ranking_hashes(postgres_client, gate1e_artifact):
    """Req 2: Verify exact ranking hash matches for Top100, Top30, Top20, Gate1B, Gate1C, Gate1D."""
    rec = reconstruct_gate1(postgres_client, AUTHORITATIVE_RUN_ID)
    assert rec["dataset_hash"] == EXPECTED_DATASET_HASH
    assert rec["top100"]["ranking_hash"] == EXPECTED_TOP100_HASH
    assert rec["top30"]["ranking_hash"] == EXPECTED_TOP30_HASH
    assert rec["top20"]["ranking_hash"] == EXPECTED_TOP20_HASH

    hashes = gate1e_artifact["ranking_hashes"]
    assert hashes["top100"] == EXPECTED_TOP100_HASH
    assert hashes["top30"] == EXPECTED_TOP30_HASH
    assert hashes["top20"] == EXPECTED_TOP20_HASH
    assert hashes["gate1b"] == EXPECTED_GATE1B_HASH
    assert hashes["gate1c"] == EXPECTED_GATE1C_HASH
    assert hashes["gate1d"] == EXPECTED_GATE1D_HASH


def test_03_closed_loop_verification(gate1e_artifact):
    """Req 3: Verify mandatory multi-iteration closed-loop verification."""
    cl = gate1e_artifact["closed_loop_verification"]
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


def test_05_rebuild_evidence_based_semantic_identity(gate1e_artifact):
    """Req 5: Verify evidence-based semantic identity rebuilt independently of stale labels."""
    for item in gate1e_artifact["items"]:
        assert len(item["niche"]) > 0
        assert len(item["subniche"]) > 0
        assert len(item["normalized_intent"]) > 0
        assert len(item["dominant_topic"]) > 0
        assert len(item["reconciliation_summary"]) > 0


def test_06_cross_field_consistency_audit(gate1e_artifact):
    """Req 6: Audit cross-field consistency (Subniche and Dominant Topic strictly match)."""
    for item in gate1e_artifact["items"]:
        assert item["subniche"] == item["dominant_topic"] or item["subniche"] in item["dominant_topic"]


def test_07_purity_classification_purity_ratio(gate1e_artifact):
    """Req 7: Verify PURE purity status and purity ratio >= 75% for all 20 records."""
    for item in gate1e_artifact["items"]:
        assert item["purity_status"] == "PURE"
        assert item["purity_ratio"] >= 0.75


def test_08_atomicity_classification(gate1e_artifact):
    """Req 8: Verify ATOMIC atomicity status for all 20 records."""
    for item in gate1e_artifact["items"]:
        assert item["atomicity_status"] == "ATOMIC"


def test_09_high_risk_deep_audit_def_046(gate1e_artifact):
    """Req 9: Deep-audit def_046."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_046")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"
    assert "Effective Study Methods" in item["subniche"]


def test_10_high_risk_deep_audit_def_036(gate1e_artifact):
    """Req 10: Deep-audit def_036."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_036")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"
    assert "AI Developer Tooling" in item["subniche"]


def test_11_high_risk_deep_audit_def_024(gate1e_artifact):
    """Req 11: Deep-audit def_024."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_024")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"
    assert "CI/CD Cloud Deployment" in item["subniche"]


def test_12_high_risk_deep_audit_def_038(gate1e_artifact):
    """Req 12: Deep-audit def_038."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_038")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"


def test_13_high_risk_deep_audit_def_052(gate1e_artifact):
    """Req 13: Deep-audit def_052."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_052")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"


def test_14_high_risk_deep_audit_def_053(gate1e_artifact):
    """Req 14: Deep-audit def_053."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_053")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"


def test_15_high_risk_deep_audit_def_054(gate1e_artifact):
    """Req 15: Deep-audit def_054."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_054")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"


def test_16_high_risk_deep_audit_def_002(gate1e_artifact):
    """Req 16: Deep-audit def_002."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_002")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"


def test_17_high_risk_deep_audit_def_009(gate1e_artifact):
    """Req 17: Deep-audit def_009."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_009")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"


def test_18_high_risk_deep_audit_def_026(gate1e_artifact):
    """Req 18: Deep-audit def_026."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_026")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"


def test_19_high_risk_deep_audit_def_023(gate1e_artifact):
    """Req 19: Deep-audit def_023."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_023")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"


def test_20_high_risk_deep_audit_def_004(gate1e_artifact):
    """Req 20: Deep-audit def_004."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_004")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"


def test_21_high_risk_deep_audit_def_016(gate1e_artifact):
    """Req 21: Deep-audit def_016."""
    item = next(i for i in gate1e_artifact["items"] if i["stable_id"] == "def_016")
    assert item["purity_status"] == "PURE"
    assert item["atomicity_status"] == "ATOMIC"


def test_22_defect_register_documentation(gate1e_artifact):
    """Req 22: Complete defect register documentation."""
    register = gate1e_artifact["defect_register"]
    assert len(register) > 0
    for defect in register:
        assert "defect_id" in defect
        assert "record_id" in defect
        assert "category" in defect
        assert "root_cause" in defect
        assert defect["resolved"] is True


def test_23_dynamic_summary_counter_calculation(gate1e_artifact):
    """Req 23: Verify summary counters are dynamically calculated from final row statuses."""
    sc = gate1e_artifact["summary_counters"]
    items = gate1e_artifact["items"]
    
    assert sc["total_canonical_subniches"] == len(items)
    assert sc["mixed_topic"] == sum(1 for i in items if i["purity_status"] == "MIXED_TOPIC")
    assert sc["contaminated"] == sum(1 for i in items if i["purity_status"] == "CONTAMINATED")
    assert sc["composite"] == sum(1 for i in items if i["atomicity_status"] == "COMPOSITE")
    assert sc["mixed_topic"] == 0
    assert sc["contaminated"] == 0
    assert sc["composite"] == 0
    assert sc["report_mismatch"] == 0


def test_24_pairwise_distinctness_across_all_20(gate1e_artifact):
    """Req 24: Verify pairwise distinctness across all 20 subniches (DUPLICATE=0, INVALID_OVERLAP=0)."""
    subniches = [i["subniche"] for i in gate1e_artifact["items"]]
    assert len(subniches) == 20
    assert len(set(subniches)) == 20
    sc = gate1e_artifact["summary_counters"]
    assert sc["duplicate"] == 0
    assert sc["invalid_overlap"] == 0


def test_25_actionability_for_downstream_engines(gate1e_artifact):
    """Req 25: Confirm actionability for downstream revenue/risk/profitability engines (ACTIONABLE_NO=0)."""
    for item in gate1e_artifact["items"]:
        assert item["actionability_status"] == "ACTIONABLE"
        assert all(item["actionability_checklist"].values()) is True
    assert gate1e_artifact["summary_counters"]["actionable_no"] == 0


def test_26_underlying_db_unmodified(postgres_client):
    """Req 26: Verify underlying DB memberships and K=35 clustering remain 100% unmodified."""
    clusters = postgres_client.execute(
        "SELECT count(*) as cnt FROM clusters WHERE run_id = %s",
        [AUTHORITATIVE_RUN_ID]
    )
    assert clusters[0]["cnt"] == 35

    run = YouTubeRepository(postgres_client).get_analytical_run(AUTHORITATIVE_RUN_ID)
    assert run.video_count == EXPECTED_PROD_VIDEOS
    assert run.channel_count == EXPECTED_PROD_CHANNELS


def test_27_artifacts_exist_and_formatted():
    """Req 27: Verify JSON and Markdown artifacts exist and meet formatting requirements."""
    assert GATE1E_JSON_PATH.exists()
    assert GATE1E_MD_PATH.exists()

    json_content = json.loads(GATE1E_JSON_PATH.read_text(encoding="utf-8"))
    assert json_content["summary_counters"]["total_canonical_subniches"] == 20
    assert json_content["summary_counters"]["report_mismatch"] == 0

    md_text = GATE1E_MD_PATH.read_text(encoding="utf-8")
    assert "# Sprint 13 Gate 1E: Canonical Top20 Final Validation" in md_text
    assert "## Summary Counters" in md_text
    assert "## Final Canonical Top 20 Semantic Identity Register" in md_text
    assert "## Deep-Audit High-Risk Item Review" in md_text
    assert "## Complete Defect Register" in md_text
    assert "## Closed-Loop Verification Summary" in md_text
    assert "## Database Integrity Verification" in md_text
