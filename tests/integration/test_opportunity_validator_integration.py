"""
Integration tests for Sprint 10 Adversarial Opportunity Validator and PostgreSQL persistence.
"""

import pytest
from app.database.repositories import YouTubeRepository
from scripts.validate_opportunities import run_validation
from scripts.sprint12_reproducibility_constants import (
    EXPECTED_DATASET_HASH,
    EXPECTED_ASSIGNMENTS_HASH,
    EXPECTED_CLUSTERS,
)


@pytest.mark.integration
def test_opportunity_validator_pipeline_and_persistence(request, monkeypatch):
    repo = YouTubeRepository()
    insert = repo.insert_validation_analysis

    def insert_with_cleanup(result):
        params = [result.run_id]
        assert not repo.client.execute(
            "SELECT 1 FROM cluster_validation_analyses WHERE run_id = %s", params
        )
        request.addfinalizer(lambda: repo.client.execute(
            "DELETE FROM cluster_validation_analyses WHERE run_id = %s", params
        ))
        return insert(result)

    monkeypatch.setattr(repo, "insert_validation_analysis", insert_with_cleanup)

    # Run full validation pipeline with PostgreSQL persistence
    output = run_validation(repository=repo, persist=True)

    result = output["result"]
    persisted = output["persisted"]
    readback = output["readback"]

    # Verify production clusters validated
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
