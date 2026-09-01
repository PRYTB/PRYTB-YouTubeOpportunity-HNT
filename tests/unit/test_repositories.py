from unittest.mock import patch, MagicMock
import pytest
import httpx
from datetime import datetime, timezone

from app.database.insforge_client import InsForgeClient, InsForgeClientError
from app.database.repositories import YouTubeRepository, PersistenceResult
from app.models.youtube import YouTubeChannel, YouTubeVideo, CollectionResult, CollectionStats


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
    assert kwargs["headers"]["Prefer"] == "resolution=merge-duplicates"
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
