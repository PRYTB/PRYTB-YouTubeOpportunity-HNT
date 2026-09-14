"""Integration tests for Sprint 7 against approved production data."""

from unittest.mock import patch

import pytest

from scripts.analyze_market_structure import run_analysis
from scripts.sprint12_reproducibility_constants import (
    EXPECTED_ASSIGNMENTS_HASH,
    EXPECTED_CLUSTERS,
    EXPECTED_DATASET_HASH,
    EXPECTED_PROD_VIDEOS,
)


@pytest.mark.integration
def test_market_structure_analyzes_approved_postgres_data_without_writes():
    with patch("httpx.Client.post") as post:
        report = run_analysis()

    post.assert_not_called()
    assert report["dataset"]["videos"] == EXPECTED_PROD_VIDEOS
    assert report["dataset"]["clusters"] == EXPECTED_CLUSTERS
    assert report["dataset"]["dataset_hash"] == EXPECTED_DATASET_HASH
    assert report["dataset"]["assignments_hash"] == EXPECTED_ASSIGNMENTS_HASH
    assert report["functional_validation"]["status"] == "PASS"
    assert report["persistence"] == {
        "requested": False,
        "writes": 0,
        "read_back_verified": None,
    }
