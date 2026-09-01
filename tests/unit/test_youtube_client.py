import pytest
from unittest.mock import patch, MagicMock
import httpx

from app.collectors.quota_tracker import QuotaTracker
from app.collectors.youtube_client import (
    YouTubeClient,
    YouTubeClientError,
    YouTubeAuthError,
    YouTubeQuotaExceededError,
    YouTubeRateLimitError,
    YouTubeAPIError,
    InvalidResponseError,
    parse_iso8601_duration,
    parse_int_or_none,
    chunked
)
from app.collectors.youtube_collector import YouTubeCollector
from app.models.youtube import YouTubeVideo, YouTubeChannel, CollectionResult, CollectionStats


# 1. Utility Tests
def test_parse_iso8601_duration():
    assert parse_iso8601_duration("PT45S") == 45
    assert parse_iso8601_duration("PT8M30S") == 510
    assert parse_iso8601_duration("PT1H2M5S") == 3725
    assert parse_iso8601_duration("P1DT2H3M4S") == 86400 + 7200 + 180 + 4
    assert parse_iso8601_duration(None) is None
    assert parse_iso8601_duration("") is None
    assert parse_iso8601_duration("INVALID") is None


def test_parse_int_or_none():
    assert parse_int_or_none("12543") == 12543
    assert parse_int_or_none(45) == 45
    assert parse_int_or_none(None) is None
    assert parse_int_or_none("") is None
    assert parse_int_or_none("abc") is None
    assert parse_int_or_none([]) is None


def test_chunked():
    assert chunked([], 50) == []
    assert chunked([1], 50) == [[1]]
    assert chunked(list(range(50)), 50) == [list(range(50))]
    assert chunked(list(range(51)), 50) == [list(range(50)), [50]]
    assert chunked(list(range(100)), 50) == [list(range(50)), list(range(50, 100))]
    with pytest.raises(ValueError):
        chunked([1, 2], 0)


# 2. Quota Tracker Tests
def test_quota_tracker():
    tracker = QuotaTracker()
    assert tracker.total_estimated_units == 0

    tracker.track("search.list", 1)  # 100
    tracker.track("videos.list", 2)  # 2
    tracker.track("channels.list", 1)  # 1

    summary = tracker.summary()
    assert summary["total_estimated_units"] == 103
    assert summary["total_requests"] == 4
    assert len(summary["operations"]) == 3

    tracker.reset()
    assert tracker.total_estimated_units == 0
    assert len(tracker.history) == 0


# 3. YouTubeClient Unit Tests
def test_youtube_client_init():
    client = YouTubeClient(api_key="test_key", timeout=10)
    assert client.api_key == "test_key"
    assert client.timeout == 10


def test_youtube_client_no_key():
    client = YouTubeClient(api_key="")
    with pytest.raises(YouTubeAuthError, match="YOUTUBE_API_KEY is not configured"):
        client.search_videos("ai")


@patch("httpx.Client.get")
def test_search_videos_single_page(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [
            {
                "id": {"videoId": "v1"},
                "snippet": {"title": "V1", "channelId": "c1", "channelTitle": "C1"}
            }
        ]
    }
    mock_get.return_value = mock_resp

    client = YouTubeClient(api_key="key")
    items, page_count = client.search_videos("ai", max_results=10)

    assert len(items) == 1
    assert page_count == 1
    assert items[0]["video_id"] == "v1"


@patch("httpx.Client.get")
def test_search_videos_multi_page(mock_get):
    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.json.return_value = {
        "nextPageToken": "token2",
        "items": [{"id": {"videoId": f"v{i}"}, "snippet": {"title": f"V{i}"}} for i in range(50)]
    }

    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.json.return_value = {
        "items": [{"id": {"videoId": f"v{i}"}, "snippet": {"title": f"V{i}"}} for i in range(50, 60)]
    }

    mock_get.side_effect = [resp1, resp2]

    client = YouTubeClient(api_key="key")
    items, page_count = client.search_videos("ai", max_results=55)

    assert len(items) == 55
    assert page_count == 2


@patch("httpx.Client.get")
def test_get_videos_batching(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [{"id": f"v{i}"} for i in range(50)]
    }
    mock_get.return_value = mock_resp

    client = YouTubeClient(api_key="key")
    vids = [f"v{i}" for i in range(55)]
    items, batch_count = client.get_videos(vids)

    assert batch_count == 2
    assert mock_get.call_count == 2


@patch("httpx.Client.get")
def test_get_channels_batching(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [{"id": f"c{i}"} for i in range(10)]
    }
    mock_get.return_value = mock_resp

    client = YouTubeClient(api_key="key")
    items, batch_count = client.get_channels(["c1", "c2"])

    assert batch_count == 1
    assert len(items) == 10


# Error and Retry Mocks
@patch("httpx.Client.get")
def test_client_quota_exceeded_no_retry(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.json.return_value = {"error": {"errors": [{"reason": "quotaExceeded"}]}}
    mock_get.return_value = mock_resp

    client = YouTubeClient(api_key="key")
    with pytest.raises(YouTubeQuotaExceededError):
        client.search_videos("ai")
    assert mock_get.call_count == 1


@patch("httpx.Client.get")
def test_client_auth_error_no_retry(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.json.return_value = {"error": {"message": "Invalid credentials"}}
    mock_get.return_value = mock_resp

    client = YouTubeClient(api_key="key")
    with pytest.raises(YouTubeAuthError):
        client.search_videos("ai")
    assert mock_get.call_count == 1


@patch("httpx.Client.get")
def test_client_retry_server_error(mock_get):
    mock_500 = MagicMock()
    mock_500.status_code = 500
    mock_500.json.return_value = {"error": {"message": "Internal error"}}

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.json.return_value = {"items": [{"id": {"videoId": "v1"}, "snippet": {}}]}

    mock_get.side_effect = [mock_500, mock_200]

    client = YouTubeClient(api_key="key")
    items, pages = client.search_videos("ai", max_results=1)
    assert len(items) == 1
    assert mock_get.call_count == 2


# 4. Collector Unit Tests
@patch.object(YouTubeClient, "search_videos")
@patch.object(YouTubeClient, "get_videos")
@patch.object(YouTubeClient, "get_channels")
def test_collector_orchestration(mock_get_channels, mock_get_videos, mock_search):
    mock_search.return_value = (
        [
            {"video_id": "v1", "title": "V1", "channel_id": "c1"},
            {"video_id": "v2", "title": "V2", "channel_id": "c1"},
            {"video_id": "v3", "title": "V3", "channel_id": "c2"}
        ],
        1
    )
    mock_get_videos.return_value = (
        [
            {
                "id": "v1",
                "snippet": {"title": "V1", "channelId": "c1", "publishedAt": "2026-01-01T00:00:00Z"},
                "statistics": {"viewCount": "1000", "likeCount": "50"},
                "contentDetails": {"duration": "PT5M"}
            },
            {
                "id": "v2",
                "snippet": {"title": "V2", "channelId": "c1"},
                "statistics": {"viewCount": "2000"},
                "contentDetails": {"duration": "PT1H"}
            }
        ],
        1
    )
    mock_get_channels.return_value = (
        [
            {
                "id": "c1",
                "snippet": {"title": "Channel 1", "country": "US"},
                "statistics": {"subscriberCount": "50000", "hiddenSubscriberCount": False}
            },
            {
                "id": "c2",
                "snippet": {"title": "Channel 2"},
                "statistics": {"hiddenSubscriberCount": True, "subscriberCount": "999"}
            }
        ],
        1
    )

    collector = YouTubeCollector(client=YouTubeClient(api_key="key"))
    res = collector.collect_keyword("ai", max_videos=3)

    assert len(res.videos) == 2  # v3 was missing in videos.list
    assert len(res.channels) == 1  # c2 was associated only with v3, so only c1 is collected
    assert res.stats.videos_resolved == 2
    assert res.stats.videos_missing == 1
    assert len(res.warnings) == 1
    assert res.channels[0].subscriber_count == 50000
