"""Read-only integration test for Sprint 6 against approved production data."""

from unittest.mock import patch

import pytest

from scripts.analyze_revenue_geography import run_analysis
from scripts.sprint5_reproducibility_runner import (
    APPROVED_ASSIGNMENTS_HASH,
    APPROVED_CLUSTERS,
    APPROVED_DATASET_HASH,
    APPROVED_PRODUCTION_VIDEOS,
)


@pytest.mark.integration
def test_revenue_geography_engine_analyzes_approved_postgres_data_without_writes():
    with patch("httpx.Client.post") as post:
        report = run_analysis()

    post.assert_not_called()
    assert report["dataset"] == {
        "videos": APPROVED_PRODUCTION_VIDEOS,
        "clusters": APPROVED_CLUSTERS,
        "dataset_hash": APPROVED_DATASET_HASH,
        "assignments_hash": APPROVED_ASSIGNMENTS_HASH,
    }
    assert report["manual_validation"]["videos_checked"] == 10
    assert report["manual_validation"]["status"] == "PASS"
    assert len(report["top_clusters"]) == 5
    assert report["revenue_benchmarks"] == {
        "provider": "EmptyBenchmarkProvider",
        "benchmarks_available": 0,
        "coverage": 0.0,
        "benchmark_missing_rate": 100.0,
        "status": "unavailable",
        "fabricated_values": 0,
    }
    assert report["persistence"]["writes"] == 0
    assert report["persistence"]["read_back"] == "not applicable"
