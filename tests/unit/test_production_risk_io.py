"""Tests for Sprint 8 repository persistence, CLI helpers, and migration."""

from copy import deepcopy
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.database.insforge_client import InsForgeClient, InsForgeClientError
from app.database.postgres_client import PostgresClient, PostgresClientError
from app.database.repositories import YouTubeRepository
from app.models.production_risk import (
    ClusterProductionRisk,
    ProductionComplexity,
    RiskLevel,
    Sprint8AnalysisResult,
    Sprint8QualityMetrics,
)
from scripts.analyze_production_risk import _functional_validation
from scripts.migrate_sprint8_schema import (
    MIGRATION_NAME,
    MIGRATION_SQL,
    MIGRATION_VERSION,
    execute_migration,
    verify_tables,
)


@pytest.fixture
def client():
    c = MagicMock(spec=PostgresClient)
    c.host = "localhost"
    c.port = 5433
    c.dbname = "prytb"
    c.user = "prytb_app"
    return c


@pytest.fixture
def result():
    return Sprint8AnalysisResult(
        run_id="sprint8-test",
        source_market_structure_run_id="sprint7-test",
        source_cluster_run_id="sprint5-test",
        analyzed_at="2026-09-04T12:00:00+00:00",
        config={"threshold": 1},
        quality=Sprint8QualityMetrics(total_videos=2, total_clusters=2),
        clusters=[
            ClusterProductionRisk(
                cluster_id=0,
                microniche="Micro A",
                video_count=1,
                production_cost_score=20.0,
                estimated_hours_low=4.0,
                estimated_hours_high=8.0,
                research_complexity_score=10.0,
                footage_complexity_score=20.0,
                editing_complexity_score=30.0,
                production_complexity=ProductionComplexity.LOW,
                copyright_risk_score=10.0,
                reused_content_risk_score=5.0,
                regulatory_sensitive_risk_score=0.0,
                overall_risk_score=6.0,
                risk_level=RiskLevel.LOW,
                confidence=80.0,
            ),
            ClusterProductionRisk(
                cluster_id=1,
                microniche="Micro B",
                video_count=1,
                production_cost_score=75.0,
                estimated_hours_low=6.0,
                estimated_hours_high=12.0,
                research_complexity_score=80.0,
                footage_complexity_score=70.0,
                editing_complexity_score=75.0,
                production_complexity=ProductionComplexity.HIGH,
                copyright_risk_score=70.0,
                reused_content_risk_score=60.0,
                regulatory_sensitive_risk_score=50.0,
                overall_risk_score=62.0,
                risk_level=RiskLevel.MEDIUM,
                confidence=90.0,
            ),
        ],
    )


def test_repository_persists_one_record_per_cluster(client, result):
    mock_cursor = MagicMock()
    client.get_cursor.return_value.__enter__.return_value = mock_cursor

    repo = YouTubeRepository(client=client)
    repo.verify_production_risk_schema = MagicMock()

    written = repo.insert_production_risk_analysis(result)

    assert written.records_written == 2
    assert mock_cursor.execute.call_count == 2


def test_repository_rejects_empty_or_duplicate_clusters(client, result):
    repo = YouTubeRepository(client=client)
    empty = result.model_copy(update={"clusters": []})
    duplicate = result.model_copy(update={"clusters": [result.clusters[0], result.clusters[0]]})

    with pytest.raises(ValueError, match="no clusters"):
        repo.insert_production_risk_analysis(empty)
    with pytest.raises(ValueError, match="Duplicate cluster"):
        repo.insert_production_risk_analysis(duplicate)


def test_production_risk_readback_requires_exact_payload_and_normalizes_json(client, result):
    repo = YouTubeRepository(client=client)
    records = deepcopy(repo._build_production_risk_records(result))
    import json

    records[0]["config"] = json.dumps(records[0]["config"])
    records[0]["quality"] = json.dumps(records[0]["quality"])
    records[0]["metrics"] = json.dumps(records[0]["metrics"])
    client.execute.return_value = records

    readback = repo.verify_production_risk_readback(result)

    assert readback.verified is True
    assert readback.payload_mismatches == 0


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "altered"])
def test_production_risk_readback_rejects_integrity_differences(client, result, mutation):
    repo = YouTubeRepository(client=client)
    records = deepcopy(repo._build_production_risk_records(result))
    if mutation == "missing":
        records.pop()
    elif mutation == "extra":
        extra = deepcopy(records[0])
        extra["cluster_id"] = 99
        records.append(extra)
    elif mutation == "duplicate":
        records.append(deepcopy(records[0]))
    else:
        records[0]["metrics"]["production_cost_score"] = 99.0
    client.execute.return_value = records

    assert repo.verify_production_risk_readback(result).verified is False


@patch("scripts.migrate_sprint8_schema.httpx.post")
def test_sprint8_migration_uses_official_endpoint(mock_post):
    legacy_client = InsForgeClient(url="http://localhost", api_key="key")
    response = MagicMock(status_code=201)
    response.json.return_value = {
        "version": MIGRATION_VERSION,
        "name": MIGRATION_NAME,
        "statements": ["CREATE TABLE"],
        "message": "ok",
    }
    mock_post.return_value = response

    assert execute_migration(legacy_client)["version"] == MIGRATION_VERSION
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {
        "version": MIGRATION_VERSION,
        "name": MIGRATION_NAME,
        "sql": MIGRATION_SQL,
    }
    assert mock_post.call_args.args[0].endswith("/api/database/migrations")


@pytest.mark.parametrize("failure", ["http", "json", "semantic", "network"])
@patch("scripts.migrate_sprint8_schema.httpx.post")
def test_sprint8_migration_rejects_failures(mock_post, failure):
    legacy_client = InsForgeClient(url="http://localhost", api_key="key")
    if failure == "network":
        mock_post.side_effect = httpx.TimeoutException("timeout")
    else:
        response = MagicMock(status_code=400 if failure == "http" else 201, text="failure")
        if failure == "json":
            response.json.side_effect = ValueError("invalid")
        elif failure == "semantic":
            response.json.return_value = {"version": "wrong"}
        mock_post.return_value = response

    with pytest.raises(InsForgeClientError):
        execute_migration(legacy_client)


@patch("scripts.migrate_sprint8_schema.httpx.get")
def test_sprint8_migration_verifies_table_and_reports_missing(mock_get):
    legacy_client = InsForgeClient(url="http://localhost", api_key="key")
    mock_get.return_value = MagicMock(status_code=200)
    assert verify_tables(legacy_client) == ["production_risk_analyses"]

    mock_get.return_value = MagicMock(status_code=404, text="missing")
    with pytest.raises(InsForgeClientError, match="not accessible"):
        verify_tables(legacy_client)


def test_sprint8_migration_requires_url():
    missing_url_client = InsForgeClient(url="", api_key="key")
    with pytest.raises(InsForgeClientError, match="INSFORGE_URL"):
        execute_migration(missing_url_client)
    with pytest.raises(InsForgeClientError, match="INSFORGE_URL"):
        verify_tables(missing_url_client)


def test_functional_validation_accepts_unknowns_without_false_failures():
    result = Sprint8AnalysisResult(
        run_id="sprint8-unknown",
        analyzed_at="2026-09-04T12:00:00+00:00",
        quality=Sprint8QualityMetrics(total_videos=1, total_clusters=1),
        clusters=[
            ClusterProductionRisk(
                cluster_id=0,
                microniche="Unknown cluster",
                video_count=1,
                production_cost_score=0.0,
                estimated_hours_low=4.0,
                estimated_hours_high=8.0,
                production_complexity=ProductionComplexity.UNKNOWN,
                overall_risk_score=None,
                risk_level=RiskLevel.UNKNOWN,
                confidence=50.0,
            )
        ],
    )

    validation = _functional_validation(result)

    assert validation == {"status": "PASS", "errors": []}
