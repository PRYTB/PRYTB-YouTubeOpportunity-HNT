from copy import deepcopy
import json
from unittest.mock import patch, MagicMock
import pytest
from datetime import datetime, timezone

from app.database.postgres_client import PostgresClient, PostgresClientError
from app.database.repositories import YouTubeRepository, PersistenceResult
from app.models.niche import NicheCluster, NicheMiningResult
from app.models.youtube import YouTubeChannel, YouTubeVideo, CollectionResult, CollectionStats


@pytest.fixture
def mock_client():
    client = MagicMock(spec=PostgresClient)
    client.host = "localhost"
    client.port = 5433
    client.dbname = "prytb"
    client.user = "prytb_app"
    return client


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


def test_upsert_channels_success(mock_client, sample_channel):
    mock_cursor = MagicMock()
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    repo = YouTubeRepository(client=mock_client)
    count = repo.upsert_channels([sample_channel])

    assert count == 1
    mock_cursor.execute.assert_called_once()


def test_upsert_videos_success(mock_client, sample_video):
    mock_cursor = MagicMock()
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    repo = YouTubeRepository(client=mock_client)
    count = repo.upsert_videos([sample_video])

    assert count == 1
    mock_cursor.execute.assert_called_once()


def test_insert_metrics_success(mock_client, sample_channel, sample_video):
    mock_cursor = MagicMock()
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    repo = YouTubeRepository(client=mock_client)
    ch_count = repo.insert_channel_metrics([sample_channel], checked_at="2026-09-01T00:00:00Z")
    v_count = repo.insert_video_metrics([sample_video], checked_at="2026-09-01T00:00:00Z")

    assert ch_count == 1
    assert v_count == 1


def test_null_handling(mock_client):
    mock_cursor = MagicMock()
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

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

    assert mock_cursor.execute.call_count == 4


def test_persist_collection_flow(mock_client, sample_channel, sample_video):
    mock_cursor = MagicMock()
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

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


def test_idempotency_behavior(mock_client, sample_channel, sample_video):
    mock_cursor = MagicMock()
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    result = CollectionResult(
        query="test",
        stats=CollectionStats(search_queries=1, total_video_ids_found=1, videos_fetched=1, channels_fetched=1),
        videos=[sample_video],
        channels=[sample_channel]
    )

    repo = YouTubeRepository(client=mock_client)
    run_timestamp = "2026-09-01T15:00:00Z"
    p_res1 = repo.persist_collection(result, checked_at=run_timestamp)
    p_res2 = repo.persist_collection(result, checked_at=run_timestamp)

    assert p_res1.videos_upserted == p_res2.videos_upserted == 1
    assert p_res1.channels_upserted == p_res2.channels_upserted == 1


def test_verify_niche_schema_raises_for_missing_table(mock_client):
    mock_client.execute.side_effect = PostgresClientError("relation does not exist")
    repo = YouTubeRepository(client=mock_client)

    with pytest.raises(PostgresClientError, match="relation does not exist"):
        repo.verify_niche_schema()


def test_insert_clusters_writes_all_tables(mock_client, sample_niche_result):
    mock_cursor = MagicMock()
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    repo = YouTubeRepository(client=mock_client)
    repo.verify_niche_schema = MagicMock()

    written = repo.insert_clusters(sample_niche_result)

    assert written.clusters_written == 2
    assert written.subniches_written == 2
    assert written.cluster_videos_written == 3


def test_insert_clusters_propagates_child_table_error(mock_client, sample_niche_result):
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = [None, PostgresClientError("subniches failed")]
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    repo = YouTubeRepository(client=mock_client)
    repo.verify_niche_schema = MagicMock()

    with pytest.raises(PostgresClientError, match="subniches failed"):
        repo.insert_clusters(sample_niche_result)


def make_readback_records(result):
    clusters, subniches, cluster_videos = YouTubeRepository._build_cluster_records(result)
    records = {
        "clusters": deepcopy(clusters),
        "subniches": deepcopy(subniches),
        "cluster_videos": deepcopy(cluster_videos),
    }
    return records


def configure_readback(repo, records):
    def fake_execute(query, params=None):
        if "FROM public.clusters" in query:
            return records["clusters"]
        elif "FROM public.subniches" in query:
            return records["subniches"]
        elif "FROM public.cluster_videos" in query:
            return records["cluster_videos"]
        elif "FROM public.videos" in query:
            return [{"video_id": params[0]}]
        return []

    repo.client.execute = MagicMock(side_effect=fake_execute)


def test_verify_clusters_readback_requires_exact_integrity(mock_client, sample_niche_result):
    records = make_readback_records(sample_niche_result)
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


def test_verify_clusters_readback_propagates_get_error(mock_client, sample_niche_result):
    mock_client.execute.side_effect = PostgresClientError("clusters missing")
    repo = YouTubeRepository(client=mock_client)

    with pytest.raises(PostgresClientError, match="clusters missing"):
        repo.verify_clusters_readback(sample_niche_result)


def test_insert_outlier_analysis_and_readback(mock_client):
    mock_cursor = MagicMock()
    mock_client.get_cursor.return_value.__enter__.return_value = mock_cursor

    repo = YouTubeRepository(client=mock_client)
    repo.verify_outlier_schema = MagicMock()

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

    mock_client.execute.return_value = records
    fetched = repo.get_outlier_analysis_by_run_id("test_run_123")
    assert len(fetched) == 1200
