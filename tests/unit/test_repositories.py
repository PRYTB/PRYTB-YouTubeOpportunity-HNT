from copy import deepcopy
import json
from unittest.mock import patch, MagicMock
import pytest
import httpx
from datetime import datetime, timezone

from app.database.insforge_client import InsForgeClient, InsForgeClientError
from app.database.repositories import YouTubeRepository, PersistenceResult
from app.models.niche import NicheCluster, NicheMiningResult
from app.models.youtube import YouTubeChannel, YouTubeVideo, CollectionResult, CollectionStats
from scripts.migrate_sprint5_schema import (
    MIGRATION_NAME,
    MIGRATION_SQL,
    MIGRATION_VERSION,
    execute_migration,
    verify_tables,
)


@pytest.fixture
def mock_client():
    return InsForgeClient(url="https://test.insforge.app", api_key="test_key")


@pytest.fixture
def sample_channel():
    return YouTubeChannel(
        channel_id="UC12345",
        channel_title="Test Channel",
        channel_description="Test Description",
        published_at="2020-01-01T00:00:00Z",
        country="US",
        subscriber_count=1000,
        video_count=50,
        view_count=50000
    )


@pytest.fixture
def sample_niche_result():
    return NicheMiningResult(
        run_id="sprint5-test-run",
        algorithm="kmeans",
        parameters={"k": 2},
        semantic_provider="LocalSemanticProvider (TF-IDF)",
        total_clusters=2,
        created_at="2026-09-02T12:00:00Z",
        clusters=[
            NicheCluster(
                cluster_id=0,
                video_ids=["VID1", "VID2"],
                video_count=2,
                unique_channels=2,
                niche="Technology",
                subniche="Python",
                microniche="Python tutorials"
            ),
            NicheCluster(
                cluster_id=1,
                video_ids=["VID3"],
                video_count=1,
                unique_channels=1,
                niche="Business",
                subniche="Marketing",
                microniche="Video marketing"
            )
        ]
    )


@pytest.fixture
def sample_video():
    return YouTubeVideo(
        video_id="VID123",
        channel_id="UC12345",
        title="Test Video Title",
        description="Test Video Description",
        published_at="2023-01-01T00:00:00Z",
        duration_iso="PT10M",
        duration_seconds=600,
        view_count=1500,
        like_count=100,
        comment_count=10,
        caption="false",
        definition="hd",
        licensed_content=True,
        default_language="en",
        default_audio_language="en"
    )


@patch("httpx.Client.post")
def test_upsert_channels_success(mock_post, mock_client, sample_channel):
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_post.return_value = mock_resp

    repo = YouTubeRepository(client=mock_client)
    count = repo.upsert_channels([sample_channel])

    assert count == 1
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "Prefer" in kwargs["headers"]
    assert "resolution=merge-duplicates" in kwargs["headers"]["Prefer"]
    assert kwargs["json"][0]["channel_id"] == "UC12345"


@patch("httpx.Client.post")
def test_upsert_videos_success(mock_post, mock_client, sample_video):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    repo = YouTubeRepository(client=mock_client)
    count = repo.upsert_videos([sample_video])

    assert count == 1
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["json"][0]["video_id"] == "VID123"
    assert kwargs["json"][0]["channel_id"] == "UC12345"


@patch("httpx.Client.post")
def test_insert_metrics_success(mock_post, mock_client, sample_channel, sample_video):
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_post.return_value = mock_resp

    repo = YouTubeRepository(client=mock_client)
    ch_count = repo.insert_channel_metrics([sample_channel], checked_at="2026-09-01T00:00:00Z")
    v_count = repo.insert_video_metrics([sample_video], checked_at="2026-09-01T00:00:00Z")

    assert ch_count == 1
    assert v_count == 1
    assert mock_post.call_count == 2


@patch("httpx.Client.post")
def test_null_handling(mock_post, mock_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    channel_nulls = YouTubeChannel(
        channel_id="UC_NULL",
        channel_title="Null Channel",
        channel_description=None,
        published_at=None,
        country=None,
        subscriber_count=None,
        video_count=None,
        view_count=None
    )

    video_nulls = YouTubeVideo(
        video_id="VID_NULL",
        channel_id="UC_NULL",
        title="Null Video",
        description=None,
        published_at=None,
        duration_iso=None,
        duration_seconds=None,
        view_count=None,
        like_count=None,
        comment_count=None,
        caption=None,
        definition=None,
        licensed_content=None,
        default_language=None,
        default_audio_language=None
    )

    repo = YouTubeRepository(client=mock_client)
    repo.upsert_channels([channel_nulls])
    repo.upsert_videos([video_nulls])
    repo.insert_channel_metrics([channel_nulls])
    repo.insert_video_metrics([video_nulls])

    assert mock_post.call_count == 4


@patch("httpx.Client.post")
def test_persist_collection_flow(mock_post, mock_client, sample_channel, sample_video):
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_post.return_value = mock_resp

    result = CollectionResult(
        query="test",
        stats=CollectionStats(search_queries=1, total_video_ids_found=1, videos_fetched=1, channels_fetched=1),
        videos=[sample_video],
        channels=[sample_channel]
    )

    repo = YouTubeRepository(client=mock_client)
    p_res = repo.persist_collection(result, checked_at="2026-09-01T12:00:00Z")

    assert isinstance(p_res, PersistenceResult)
    assert p_res.channels_received == 1
    assert p_res.channels_upserted == 1
    assert p_res.videos_received == 1
    assert p_res.videos_upserted == 1
    assert p_res.channel_metrics_inserted == 1
    assert p_res.video_metrics_inserted == 1
    assert p_res.db_operations == 4
    assert len(p_res.warnings) == 0


@patch("httpx.Client.post")
def test_idempotency_behavior(mock_post, mock_client, sample_channel, sample_video):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    result = CollectionResult(
        query="test",
        stats=CollectionStats(search_queries=1, total_video_ids_found=1, videos_fetched=1, channels_fetched=1),
        videos=[sample_video],
        channels=[sample_channel]
    )

    repo = YouTubeRepository(client=mock_client)
    # Perform persistence twice with same run_id/checked_at timestamp
    run_timestamp = "2026-09-01T15:00:00Z"
    p_res1 = repo.persist_collection(result, checked_at=run_timestamp)
    p_res2 = repo.persist_collection(result, checked_at=run_timestamp)

    assert p_res1.videos_upserted == p_res2.videos_upserted == 1
    assert p_res1.channels_upserted == p_res2.channels_upserted == 1
    assert mock_post.call_count == 8


@patch("httpx.Client.post")
def test_repository_timeout_error(mock_post, mock_client, sample_video):
    mock_post.side_effect = httpx.TimeoutException("Connection timed out")

    repo = YouTubeRepository(client=mock_client)
    with pytest.raises(InsForgeClientError, match="Network error sending batch to InsForge"):
        repo.upsert_videos([sample_video])


@patch("httpx.Client.post")
def test_repository_auth_failure(mock_post, mock_client, sample_video):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_post.return_value = mock_resp

    repo = YouTubeRepository(client=mock_client)
    with pytest.raises(InsForgeClientError, match="InsForge authentication failure"):
        repo.upsert_videos([sample_video])


@patch("httpx.Client.post")
def test_repository_constraint_error(mock_post, mock_client, sample_video):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "foreign key constraint violation"
    mock_post.return_value = mock_resp

    repo = YouTubeRepository(client=mock_client)
    with pytest.raises(InsForgeClientError, match="InsForge request to videos failed"):
        repo.upsert_videos([sample_video])


@patch("scripts.migrate_sprint5_schema.httpx.post")
def test_sprint5_migration_uses_official_endpoint(
    mock_post,
    mock_client
):
    response = MagicMock()
    response.status_code = 201
    response.json.return_value = {
        "version": MIGRATION_VERSION,
        "name": MIGRATION_NAME,
        "statements": ["CREATE TABLE clusters"],
        "message": "Migration executed successfully"
    }
    mock_post.return_value = response

    result = execute_migration(mock_client)

    assert result["version"] == MIGRATION_VERSION
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {
        "version": MIGRATION_VERSION,
        "name": MIGRATION_NAME,
        "sql": MIGRATION_SQL
    }
    assert mock_post.call_args.args[0].endswith(
        "/api/database/migrations"
    )


@patch("scripts.migrate_sprint5_schema.httpx.get")
def test_sprint5_migration_verifies_all_tables(
    mock_get,
    mock_client
):
    response = MagicMock()
    response.status_code = 200
    mock_get.return_value = response

    assert verify_tables(mock_client) == [
        "clusters",
        "subniches",
        "cluster_videos"
    ]
    assert mock_get.call_count == 3


@patch("scripts.migrate_sprint5_schema.httpx.get")
def test_sprint5_migration_fails_when_table_missing(
    mock_get,
    mock_client
):
    response = MagicMock()
    response.status_code = 404
    response.text = "relation does not exist"
    mock_get.return_value = response

    with pytest.raises(
        InsForgeClientError,
        match="is not accessible"
    ):
        verify_tables(mock_client)


def test_verify_niche_schema_raises_for_missing_table(
    mock_client
):
    repo = YouTubeRepository(client=mock_client)
    repo._get_records = MagicMock(
        side_effect=InsForgeClientError("relation does not exist")
    )

    with pytest.raises(
        InsForgeClientError,
        match="relation does not exist"
    ):
        repo.verify_niche_schema()


def test_insert_clusters_writes_all_tables(
    mock_client,
    sample_niche_result
):
    repo = YouTubeRepository(client=mock_client)
    repo.verify_niche_schema = MagicMock()
    repo._post_records = MagicMock(return_value=True)

    written = repo.insert_clusters(sample_niche_result)

    assert written.clusters_written == 2
    assert written.subniches_written == 2
    assert written.cluster_videos_written == 3
    assert repo._post_records.call_count == 3

    cluster_payload = repo._post_records.call_args_list[0].args[1]
    video_payload = repo._post_records.call_args_list[2].args[1]
    assert cluster_payload[0]["parameters"] == {"k": 2}
    assert video_payload[0]["distance_to_centroid"] is None


def test_insert_clusters_propagates_child_table_error(
    mock_client,
    sample_niche_result
):
    repo = YouTubeRepository(client=mock_client)
    repo.verify_niche_schema = MagicMock()
    repo._post_records = MagicMock(
        side_effect=[True, InsForgeClientError("subniches failed")]
    )

    with pytest.raises(
        InsForgeClientError,
        match="subniches failed"
    ):
        repo.insert_clusters(sample_niche_result)


def make_readback_records(result):
    clusters, subniches, cluster_videos = YouTubeRepository._build_cluster_records(
        result
    )
    records = {
        "clusters": deepcopy(clusters),
        "subniches": deepcopy(subniches),
        "cluster_videos": deepcopy(cluster_videos),
    }
    for values in records.values():
        for record in values:
            record["database_generated_id"] = 123
    return records


def configure_readback(repo, records):
    def get_records(table, params=None):
        if table == "videos":
            return [{"video_id": params["video_id"][3:]}]
        return records[table]

    repo._get_records = MagicMock(side_effect=get_records)


def test_verify_clusters_readback_requires_exact_integrity(
    mock_client,
    sample_niche_result
):
    records = make_readback_records(sample_niche_result)
    records["clusters"][0]["parameters"] = json.dumps(
        records["clusters"][0]["parameters"]
    )
    repo = YouTubeRepository(client=mock_client)
    configure_readback(repo, records)

    readback = repo.verify_clusters_readback(sample_niche_result)

    assert readback.actual_clusters == 2
    assert readback.actual_subniches == 2
    assert readback.actual_cluster_videos == 3
    assert readback.unique_videos == 3
    assert readback.unique_cluster_ids == 2
    assert readback.duplicate_clusters == 0
    assert readback.duplicate_videos == 0
    assert readback.orphan_cluster_videos == 0
    assert readback.orphan_subniches == 0
    assert readback.missing_videos == 0
    assert readback.cluster_payload_mismatches == 0
    assert readback.subniche_payload_mismatches == 0
    assert readback.cluster_video_payload_mismatches == 0
    assert readback.verified is True


@pytest.mark.parametrize(
    ("table", "field", "value", "mismatch_field"),
    [
        ("clusters", "parameters", {"k": 99}, "cluster_payload_mismatches"),
        ("clusters", "semantic_quality", 0.25, "cluster_payload_mismatches"),
        ("subniches", "summary", "altered", "subniche_payload_mismatches"),
        (
            "cluster_videos",
            "distance_to_centroid",
            0.1,
            "cluster_video_payload_mismatches",
        ),
    ],
)
def test_verify_clusters_readback_rejects_payload_difference(
    mock_client,
    sample_niche_result,
    table,
    field,
    value,
    mismatch_field,
):
    records = make_readback_records(sample_niche_result)
    records[table][0][field] = value
    repo = YouTubeRepository(client=mock_client)
    configure_readback(repo, records)

    readback = repo.verify_clusters_readback(sample_niche_result)

    assert getattr(readback, mismatch_field) == 1
    assert readback.verified is False


def test_verify_clusters_readback_propagates_get_error(
    mock_client,
    sample_niche_result
):
    repo = YouTubeRepository(client=mock_client)
    repo._get_records = MagicMock(
        side_effect=InsForgeClientError("clusters missing")
    )

    with pytest.raises(
        InsForgeClientError,
        match="clusters missing"
    ):
        repo.verify_clusters_readback(sample_niche_result)


def test_insert_outlier_analysis_and_readback(mock_client):
    repo = YouTubeRepository(client=mock_client)
    repo.verify_outlier_schema = MagicMock()
    repo._post_records = MagicMock(return_value=True)

    records = [
        {
            "run_id": "test_run_123",
            "video_id": f"v_{i}",
            "channel_id": "c_1",
            "outlier_ratio": 5.5,
            "outlier_rank_score": 10.2,
            "small_channel_outlier": False,
        }
        for i in range(1200)
    ]

    success = repo.insert_outlier_analysis(records, batch_size=500)
    assert success is True
    # Should call batch insert 3 times (500 + 500 + 200)
    assert repo._post_records.call_count == 3

    repo._get_records = MagicMock(return_value=records)
    fetched = repo.get_outlier_analysis_by_run_id("test_run_123")
    assert len(fetched) == 1200
    repo._get_records.assert_called_once_with(
        "video_outlier_analyses", params={"run_id": "eq.test_run_123"}
    )
