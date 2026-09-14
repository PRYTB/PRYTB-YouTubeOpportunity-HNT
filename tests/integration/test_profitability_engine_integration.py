"""
Integration tests for Sprint 9 Profitability Engine and PostgreSQL persistence.
"""

import pytest
from scripts.sprint12_reproducibility_constants import (
    EXPECTED_ASSIGNMENTS_HASH,
    EXPECTED_CLUSTERS,
    EXPECTED_DATASET_HASH,
)
from app.database.repositories import YouTubeRepository
from scripts.analyze_profitability import run_analysis


@pytest.mark.integration
def test_profitability_pipeline_and_persistence():
    repo = YouTubeRepository()

    # Run full analysis pipeline with PostgreSQL persistence
    output = run_analysis(repository=repo, persist=True)

    result = output["result"]
    persisted = output["persisted"]
    readback = output["readback"]

    # Verify production clusters
    assert len(result.clusters) == EXPECTED_CLUSTERS
    assert result.dataset_hash == EXPECTED_DATASET_HASH
    assert result.assignments_hash == EXPECTED_ASSIGNMENTS_HASH

    # Verify exact PostgreSQL persistence and read-back
    assert persisted is not None
    assert persisted.records_written == EXPECTED_CLUSTERS

    assert readback is not None
    assert readback.verified is True
    assert readback.expected_records == EXPECTED_CLUSTERS
    assert readback.actual_records == EXPECTED_CLUSTERS
    assert readback.unique_clusters == EXPECTED_CLUSTERS
    assert readback.duplicate_records == 0
    assert readback.payload_mismatches == 0
    assert readback.provenance_mismatches == 0
