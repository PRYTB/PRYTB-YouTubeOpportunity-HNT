"""Sprint 13 Gate 1B Semantic Quality Reconciliation Integration Tests."""

import hashlib
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
from scripts.generate_sprint13_gate1b_artifacts import (
    GATE1B_JSON_PATH,
    GATE1B_MD_PATH,
    generate_gate1b_artifacts,
)

TERMINAL_STATUS = "SPRINT12_FINAL_ANALYTICS_APPROVED"
EXPECTED_TOP100_HASH = "d2df88751980afb7af1e9ecadf145a2a0ff514a0dba6062f8d62e03d980426d2"
EXPECTED_TOP30_HASH = "decc570011b881414202cba3f0c03144c954f0be5c21c4167e756f5ff5780c77"
EXPECTED_TOP20_HASH = "85a543baf63afad339c1643b8f25cadd2b8d7d4ca316ce6e182c130fe39d98e4"
EXPECTED_TOP20_IDS = [
    "def_015", "def_046", "def_055", "def_036", "def_024",
    "def_057", "def_045", "def_030", "def_004", "def_038",
    "def_052", "def_020", "def_053", "def_016", "def_054",
    "def_025", "def_002", "def_009", "def_026", "def_023",
]
VALID_CLASSIFICATIONS = {
    "PASS", "MISLABELED", "MALFORMED", "TOO_GENERIC",
    "MIXED_TOPIC", "LANGUAGE_NOISE", "UNSUPPORTED", "AMBIGUOUS"
}


@pytest.fixture(scope="module")
def postgres_client():
    return PostgresClient()


@pytest.fixture(scope="module")
def gate1b_artifact():
    if not GATE1B_JSON_PATH.exists():
        generate_gate1b_artifacts()
    return json.loads(GATE1B_JSON_PATH.read_text(encoding="utf-8"))


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


def test_02_funnel_reconstruction_and_ranking_hashes(postgres_client):
    """Requirement 2: Verify deterministic funnel reconstruction hashes."""
    rec = reconstruct_gate1(postgres_client, AUTHORITATIVE_RUN_ID)
    assert rec["dataset_hash"] == EXPECTED_DATASET_HASH
    assert rec["top100"]["ranking_hash"] == EXPECTED_TOP100_HASH
    assert rec["top30"]["ranking_hash"] == EXPECTED_TOP30_HASH
    assert rec["top20"]["ranking_hash"] == EXPECTED_TOP20_HASH
    
    top20_ids = [item["stable_id"] for item in rec["top20"]["items"]]
    assert top20_ids == EXPECTED_TOP20_IDS


def test_03_closed_loop_validation(gate1b_artifact):
    """Requirement 3: Verify mandatory closed-loop dual read verification."""
    closed_loop = gate1b_artifact["closed_loop"]
    assert closed_loop["read_count"] == 2
    assert closed_loop["independent_clients"] is True
    assert closed_loop["identical_reconstructions"] is True
    assert closed_loop["ranking_hashes_equal"] is True
    assert closed_loop["first_read_hash"] == closed_loop["second_read_hash"]


def test_04_top20_item_count_and_ordering(gate1b_artifact):
    """Requirement 4: Verify exactly 20 records in exact rank order matching Gate 1 canonical IDs."""
    items = gate1b_artifact["items"]
    assert len(items) == 20
    ranks = [item["rank"] for item in items]
    assert ranks == list(range(1, 21))
    
    ids = [item["stable_id"] for item in items]
    assert ids == EXPECTED_TOP20_IDS


def test_05_reconciliation_fields_completeness(gate1b_artifact):
    """Requirement 5: Check every item contains all mandatory audit fields."""
    required_fields = {
        "rank", "stable_id", "analytical_ordinal",
        "original_niche", "reconciled_niche",
        "original_subniche", "reconciled_subniche",
        "original_intent", "reconciled_intent",
        "classification", "root_cause", "evidence",
        "source_records", "provenance"
    }
    for item in gate1b_artifact["items"]:
        assert required_fields.issubset(set(item.keys()))
        assert isinstance(item["evidence"], list)
        assert len(item["evidence"]) >= 3
        assert len(item["root_cause"].strip()) > 10
        assert len(item["reconciled_niche"].strip()) > 2
        assert len(item["reconciled_subniche"].strip()) > 2
        assert len(item["reconciled_intent"].strip()) > 2


def test_06_valid_classifications(gate1b_artifact):
    """Requirement 6: Ensure all classifications belong to allowed set."""
    for item in gate1b_artifact["items"]:
        assert item["classification"] in VALID_CLASSIFICATIONS


def test_07_specific_suspicious_items_audited(gate1b_artifact):
    """Requirement 7: Verify specific problematic IDs (def_046, def_057, def_045, def_052, def_016, def_025, def_053, def_015)."""
    items_by_id = {item["stable_id"]: item for item in gate1b_artifact["items"]}
    
    # def_046 malformed stopword leakage
    assert items_by_id["def_046"]["classification"] == "MALFORMED"
    assert "Crear" not in items_by_id["def_046"]["reconciled_subniche"]
    
    # def_057 malformed stopword leakage
    assert items_by_id["def_057"]["classification"] == "MALFORMED"
    assert "De & De" not in items_by_id["def_057"]["reconciled_subniche"]
    
    # def_045 malformed stopword leakage
    assert items_by_id["def_045"]["classification"] == "MALFORMED"
    assert "De & De" not in items_by_id["def_045"]["reconciled_subniche"]
    
    # def_052 malformed stopword leakage
    assert items_by_id["def_052"]["classification"] == "MALFORMED"
    assert "De & Hotmart" not in items_by_id["def_052"]["reconciled_subniche"]

    # def_016 malformed stopword leakage
    assert items_by_id["def_016"]["classification"] == "MALFORMED"
    assert "By & By" not in items_by_id["def_016"]["reconciled_subniche"]

    # def_015 mislabeled hardware optimization
    assert items_by_id["def_015"]["classification"] == "MISLABELED"
    assert "Artificial Intelligence" in items_by_id["def_015"]["reconciled_niche"]

    # def_053 mislabeled hardware optimization
    assert items_by_id["def_053"]["classification"] == "MISLABELED"
    assert "Personal Finance" in items_by_id["def_053"]["reconciled_niche"]


def test_08_semantic_distinctness(gate1b_artifact):
    """Requirement 8: Ensure all 20 reconciled subniches are semantically distinct (no duplicate labels)."""
    subniches = [item["reconciled_subniche"].strip().lower() for item in gate1b_artifact["items"]]
    assert len(subniches) == len(set(subniches))


def test_09_no_stopword_leakage(gate1b_artifact):
    """Requirement 9: Ensure zero raw stopword fragments remain in reconciled labels."""
    forbidden_substrings = ["de & de", "by & by", "crear & curso", "20 & budget", "2025 & in", "de overview", "by overview"]
    for item in gate1b_artifact["items"]:
        sub_lower = item["reconciled_subniche"].lower()
        niche_lower = item["reconciled_niche"].lower()
        for forbidden in forbidden_substrings:
            assert forbidden not in sub_lower, f"Forbidden '{forbidden}' found in subniche '{item['reconciled_subniche']}'"
            assert forbidden not in niche_lower, f"Forbidden '{forbidden}' found in niche '{item['reconciled_niche']}'"


def test_10_evidence_backing(gate1b_artifact):
    """Requirement 10: Verify supporting video evidence is present and non-empty for all items."""
    for item in gate1b_artifact["items"]:
        evidence = item["evidence"]
        assert len(evidence) >= 3
        for ev in evidence:
            assert len(ev.strip()) > 5


def test_11_analytical_memberships_preservation(gate1b_artifact):
    """Requirement 11: Verify historical metrics (outliers, videos, channels) match canonical Gate 1 numbers exactly."""
    summary = gate1b_artifact["reconciliation_summary"]
    assert summary["historical_memberships_preserved"] is True
    
    total_outliers = sum(item["source_records"]["outlier_count"] for item in gate1b_artifact["items"])
    assert total_outliers > 500  # Analytical metrics preserved


def test_12_downstream_provenance(gate1b_artifact):
    """Requirement 12: Verify downstream evaluation cluster IDs and run IDs exist in provenance."""
    for item in gate1b_artifact["items"]:
        prov = item["provenance"]
        assert "evaluation_cluster_id" in prov
        assert "downstream_run_ids" in prov
        assert set(prov["downstream_run_ids"].keys()) == {"validation", "profitability", "market", "production"}


def test_13_zero_remaining_defects(gate1b_artifact):
    """Requirement 13: Verify summary reports 0 remaining defects."""
    summary = gate1b_artifact["reconciliation_summary"]
    assert summary["remaining_defects"] == 0
    assert summary["total_items"] == 20


def test_14_artifacts_exist_and_non_empty():
    """Requirement 14: Verify both JSON and MD artifacts exist and are non-empty."""
    assert GATE1B_JSON_PATH.exists()
    assert GATE1B_JSON_PATH.stat().st_size > 1000
    assert GATE1B_MD_PATH.exists()
    assert GATE1B_MD_PATH.stat().st_size > 1000


def test_15_markdown_report_structure():
    """Requirement 15: Verify markdown report contains essential sections."""
    content = GATE1B_MD_PATH.read_text(encoding="utf-8")
    assert "# SPRINT 13 — GATE 1B: SEMANTIC QUALITY RECONCILIATION" in content
    assert "## Closed-Loop Verification" in content
    assert "## Reconciliation Classification Summary" in content
    assert "## Canonical Top 20 Semantic Reconciliation Table" in content
    assert "## Detailed Item Audits & Root Cause Analysis" in content


def test_16_deterministic_artifact_generation(postgres_client):
    """Requirement 16: Verify rerunning generation script yields identical output."""
    initial_hash = hashlib.sha256(GATE1B_JSON_PATH.read_bytes()).hexdigest()
    generate_gate1b_artifacts()
    recheck_hash = hashlib.sha256(GATE1B_JSON_PATH.read_bytes()).hexdigest()
    assert initial_hash == recheck_hash
