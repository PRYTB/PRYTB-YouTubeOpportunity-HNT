"""
Integration tests for Sprint 9 Profitability Engine and PostgreSQL persistence.
"""

import pytest
from app.analytics.profitability_engine import ProfitabilityEngine
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

    # Verify 10 production clusters
    assert len(result.clusters) == 10
    assert result.dataset_hash == "4d81c80e8da54b371c7eb969957ea347fc632d82abd737719141c866f4bfe9ad"
    assert result.assignments_hash == "6c0e7bb6aeec75985664becb05f7c61cbfec874c15a6ec7395d60c2996436288"

    # Verify exact PostgreSQL persistence and read-back
    assert persisted is not None
    assert persisted.records_written == 10

    assert readback is not None
    assert readback.verified is True
    assert readback.expected_records == 10
    assert readback.actual_records == 10
    assert readback.unique_clusters == 10
    assert readback.duplicate_records == 0
    assert readback.payload_mismatches == 0
    assert readback.provenance_mismatches == 0
