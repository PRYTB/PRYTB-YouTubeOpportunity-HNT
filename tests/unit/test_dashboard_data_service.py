"""
Unit tests for Dashboard Data Service (Sprint 11).
"""

import pytest
from unittest.mock import MagicMock

from dashboard.data_service import (
    DashboardDataService,
    CANONICAL_DATASET_HASH,
    CANONICAL_ASSIGNMENTS_HASH,
    CANONICAL_VIDEOS,
    CANONICAL_CLUSTERS,
    ProvenanceInfo,
)


def test_dashboard_import_portability():
    """Verify app.py modifies sys.path properly so dashboard can be imported when running from project root."""
    import sys
    from pathlib import Path
    project_root = str(Path(__file__).resolve().parent.parent.parent)
    assert project_root in sys.path


def test_dashboard_data_service_initialization():
    service = DashboardDataService()
    assert service.repository is not None


@pytest.mark.integration
def test_dashboard_data_loading_and_joining():
    service = DashboardDataService()
    dataset = service.get_dashboard_data()

    # Provenance assertions
    assert dataset.provenance is not None
    assert dataset.provenance.dataset_hash == CANONICAL_DATASET_HASH
    assert dataset.provenance.assignments_hash == CANONICAL_ASSIGNMENTS_HASH
    assert dataset.provenance.is_compatible is True

    # Portfolio counts
    assert dataset.total_videos == CANONICAL_VIDEOS
    assert dataset.total_clusters == CANONICAL_CLUSTERS
    assert len(dataset.candidates) == CANONICAL_CLUSTERS
    assert len(dataset.videos) == CANONICAL_VIDEOS
    assert len(dataset.channels) > 0

    # Candidate view model fields
    first_cand = dataset.candidates[0]
    assert first_cand.cluster_id >= 0
    assert first_cand.validation_score >= 0.0
    assert first_cand.profitability_score >= 0.0
    assert first_cand.rpm_available is False
    assert first_cand.revenue_available is False
    assert first_cand.cost_available is False
    assert first_cand.profit_available is False
    assert first_cand.content_depth_band.value == "UNDETERMINED"

    # Truthful missing values rendering check
    assert isinstance(first_cand.positive_evidence, list)
    assert isinstance(first_cand.negative_evidence, list)
    assert isinstance(first_cand.missing_evidence, list)


def test_provenance_mismatch_detection():
    service = DashboardDataService()
    
    # Mock run_validation response with corrupted hash
    mock_val_output = {
        "result": MagicMock(
            dataset_hash="wrong_hash",
            assignments_hash=CANONICAL_ASSIGNMENTS_HASH,
            source_profitability_run_id="run_1",
            run_id="val_1",
            source_market_run_id="mkt_1",
            source_production_run_id="prod_1",
            source_revenue_run_id="rev_1",
            source_cluster_run_id="cls_1",
            clusters=[],
        ),
        "sprint9_result": MagicMock(run_id="run_1", clusters=[]),
        "sprint5_clusters": [],
        "sprint6_result": None,
        "sprint7_result": None,
        "sprint8_result": None,
        "outlier_results": [],
        "ordered_videos": [],
        "enriched_channels": [],
    }

    with pytest.MonkeyPatch().context() as m:
        m.setattr("dashboard.data_service.run_validation", lambda repository, persist: mock_val_output)
        dataset = service.get_dashboard_data()
        assert dataset.provenance.is_compatible is False
        assert "Canonical hash mismatch" in dataset.provenance.error_message
