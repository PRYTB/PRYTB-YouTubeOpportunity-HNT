"""Tests for Sprint 7 snapshots, repository persistence, and migration."""

from copy import deepcopy
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.database.insforge_client import InsForgeClient, InsForgeClientError
from app.database.postgres_client import PostgresClient, PostgresClientError
from app.database.repositories import YouTubeRepository
from app.models.market_structure import (
    ClusterMarketStructure,
    Sprint7AnalysisResult,
    Sprint7QualityMetrics,
)
from scripts.analyze_market_structure import enrich_with_latest_metrics, latest_snapshots
from scripts.migrate_sprint7_schema import (
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
    return Sprint7AnalysisResult(
        run_id="sprint7-test",
        source_cluster_run_id="sprint5-test",
        analyzed_at="2026-09-03T12:00:00+00:00",
        config={"threshold": 1},
        quality=Sprint7QualityMetrics(total_videos=2, total_clusters=2),
        clusters=[
            ClusterMarketStructure(cluster_id=0, video_count=1, distinct_title_count=1, competition_score=20),
            ClusterMarketStructure(cluster_id=1, video_count=1, distinct_title_count=1, competition_score=30),
        ],
    )


def test_latest_snapshots_orders_iso_timestamps_chronologically_and_skips_empty_ids():
    records = [
        {"video_id": "v", "collected_at": "2026-09-03T12:00:00+02:00", "view_count": 1},
        {"video_id": "v", "collected_at": "2026-09-03T10:30:00Z", "view_count": 2},
        {"video_id": "", "collected_at": "2099-01-01T00:00:00Z", "view_count": 99},
        {"video_id": "bad", "collected_at": "invalid", "view_count": 3},
    ]

    latest = latest_snapshots(reversed(records), "video_id")

    assert latest["v"]["view_count"] == 2
    assert latest["bad"]["view_count"] == 3
    assert "" not in latest


def test_enrichment_uses_latest_metrics_without_mutating_static_records():
    videos = [{"video_id": "v", "view_count": 1, "title": "title"}]
    channels = [{"channel_id": "c", "subscriber_count": 1}]

    enriched_videos, enriched_channels = enrich_with_latest_metrics(
        videos,
        channels,
        [{"video_id": "v", "collected_at": "2026-01-01Z", "view_count": 10}],
        [{"channel_id": "c", "collected_at": "2026-01-01Z", "subscriber_count": 20}],
    )

    assert enriched_videos[0]["view_count"] == 10
    assert enriched_channels[0]["subscriber_count"] == 20
    assert videos[0]["view_count"] == 1
    assert channels[0]["subscriber_count"] == 1


def test_repository_persists_one_record_per_cluster(client, result):
    mock_cursor = MagicMock()
    client.get_cursor.return_value.__enter__.return_value = mock_cursor

    repo = YouTubeRepository(client=client)
    repo.verify_market_structure_schema = MagicMock()

    written = repo.insert_market_structure_analysis(result)

    assert written.records_written == 2
    assert mock_cursor.execute.call_count == 2


def test_repository_rejects_empty_or_duplicate_clusters(client, result):
    repo = YouTubeRepository(client=client)
    empty = result.model_copy(update={"clusters": []})
    duplicate = result.model_copy(update={"clusters": [result.clusters[0], result.clusters[0]]})

    with pytest.raises(ValueError, match="no clusters"):
        repo.insert_market_structure_analysis(empty)
    with pytest.raises(ValueError, match="Duplicate cluster"):
        repo.insert_market_structure_analysis(duplicate)


def test_market_structure_readback_requires_exact_payload_and_normalizes_json(client, result):
    repo = YouTubeRepository(client=client)
    records = deepcopy(repo._build_market_structure_records(result))
    import json
    records[0]["config"] = json.dumps(records[0]["config"])
    records[0]["quality"] = json.dumps(records[0]["quality"])
    records[0]["metrics"] = json.dumps(records[0]["metrics"])
    client.execute.return_value = records

    readback = repo.verify_market_structure_readback(result)

    assert readback.verified is True
    assert readback.payload_mismatches == 0


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "altered"])
def test_market_structure_readback_rejects_integrity_differences(client, result, mutation):
    repo = YouTubeRepository(client=client)
    records = deepcopy(repo._build_market_structure_records(result))
    if mutation == "missing":
        records.pop()
    elif mutation == "extra":
        extra = deepcopy(records[0])
        extra["cluster_id"] = 99
        records.append(extra)
    elif mutation == "duplicate":
        records.append(deepcopy(records[0]))
    else:
        records[0]["competition_score"] = 99
    client.execute.return_value = records

    assert repo.verify_market_structure_readback(result).verified is False


@patch("scripts.migrate_sprint7_schema.httpx.post")
def test_sprint7_migration_uses_official_endpoint(mock_post):
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
    assert kwargs["json"] == {"version": MIGRATION_VERSION, "name": MIGRATION_NAME, "sql": MIGRATION_SQL}
    assert mock_post.call_args.args[0].endswith("/api/database/migrations")


@pytest.mark.parametrize("failure", ["http", "json", "semantic", "network"])
@patch("scripts.migrate_sprint7_schema.httpx.post")
def test_sprint7_migration_rejects_failures(mock_post, failure):
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


@patch("scripts.migrate_sprint7_schema.httpx.get")
def test_sprint7_migration_verifies_table_and_reports_missing(mock_get):
    legacy_client = InsForgeClient(url="http://localhost", api_key="key")
    mock_get.return_value = MagicMock(status_code=200)
    assert verify_tables(legacy_client) == ["market_structure_analyses"]

    mock_get.return_value = MagicMock(status_code=404, text="missing")
    with pytest.raises(InsForgeClientError, match="not accessible"):
        verify_tables(legacy_client)


def test_sprint7_migration_requires_url():
    client = InsForgeClient(url="", api_key="key")
    with pytest.raises(InsForgeClientError, match="INSFORGE_URL"):
        execute_migration(client)
    with pytest.raises(InsForgeClientError, match="INSFORGE_URL"):
        verify_tables(client)
