from unittest.mock import patch, MagicMock
import pytest
import httpx

from app.collectors.youtube_client import (
    YouTubeClient,
    YouTubeClientError,
    YouTubeAuthError,
    YouTubeQuotaExceededError,
)

def test_youtube_client_init():
    client = YouTubeClient(api_key="test_key", timeout=10)
    assert client.api_key == "test_key"
    assert client.timeout == 10

def test_youtube_client_no_key():
    client = YouTubeClient(api_key="")
    with pytest.raises(YouTubeAuthError, match="YOUTUBE_API_KEY is not configured"):
        client.search_videos("ai")

@patch("httpx.Client.get")
def test_youtube_search_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "id": {"videoId": "vid123"},
                "snippet": {
                    "title": "AI Video",
                    "channelId": "chan123",
                    "channelTitle": "AI Channel",
                    "publishedAt": "2026-01-01T00:00:00Z"
                }
            }
        ]
    }
    mock_get.return_value = mock_response

    client = YouTubeClient(api_key="valid_key")
    results = client.search_videos("ai", max_results=1)

    assert len(results) == 1
    assert results[0]["video_id"] == "vid123"
    assert results[0]["title"] == "AI Video"

@patch("httpx.Client.get")
def test_youtube_search_quota_exceeded(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {
        "error": {
            "errors": [{"reason": "quotaExceeded"}]
        }
    }
    mock_get.return_value = mock_response

    client = YouTubeClient(api_key="valid_key")
    with pytest.raises(YouTubeQuotaExceededError):
        client.search_videos("ai")

@patch("httpx.Client.get")
def test_youtube_search_auth_error(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {
        "error": {
            "message": "Key invalid",
            "errors": [{"reason": "keyInvalid"}]
        }
    }
    mock_get.return_value = mock_response

    client = YouTubeClient(api_key="invalid_key")
    with pytest.raises(YouTubeAuthError):
        client.search_videos("ai")

@patch("httpx.Client.get")
def test_youtube_search_timeout(mock_get):
    mock_get.side_effect = httpx.RequestError("Connection timeout")

    client = YouTubeClient(api_key="valid_key")
    with pytest.raises(YouTubeClientError, match="Network error connecting to YouTube API"):
        client.search_videos("ai")

@patch("httpx.Client.get")
def test_youtube_search_invalid_json(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_get.return_value = mock_response

    client = YouTubeClient(api_key="valid_key")
    with pytest.raises(YouTubeClientError, match="Invalid JSON response"):
        client.search_videos("ai")
