"""Integration tests for Sprint 8 against approved production data."""

from unittest.mock import patch

import pytest

from scripts.analyze_production_risk import run_analysis
from scripts.sprint5_reproducibility_runner import (
    APPROVED_ASSIGNMENTS_HASH,
    APPROVED_CLUSTERS,
    APPROVED_DATASET_HASH,
    APPROVED_PRODUCTION_VIDEOS,
)


@pytest.mark.integration
def test_production_risk_analyzes_approved_insforge_data_without_writes():
    with patch("httpx.Client.post") as post:
        report = run_analysis()

    post.assert_not_called()
    assert report["dataset"]["videos"] == APPROVED_PRODUCTION_VIDEOS
    assert report["dataset"]["clusters"] == APPROVED_CLUSTERS
    assert report["dataset"]["dataset_hash"] == APPROVED_DATASET_HASH
    assert report["dataset"]["assignments_hash"] == APPROVED_ASSIGNMENTS_HASH
    assert report["functional_validation"]["status"] == "PASS"
    assert report["persistence"] == {
        "requested": False,
        "writes": 0,
        "read_back_verified": None,
    }
