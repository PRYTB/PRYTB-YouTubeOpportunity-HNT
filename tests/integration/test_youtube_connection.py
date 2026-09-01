import pytest
from app.collectors.youtube_client import YouTubeClient, YouTubeAuthError
from app.utils.config import settings

@pytest.mark.integration
def test_youtube_connection():
    if not settings.YOUTUBE_API_KEY or not settings.YOUTUBE_API_KEY.get_secret_value().strip():
        pytest.skip("YOUTUBE_API_KEY not configured in .env; skipping live integration test.")

    client = YouTubeClient()
    try:
        results = client.search_videos(query="artificial intelligence", max_results=3)
        assert isinstance(results, list)
        assert len(results) > 0
        
        first = results[0]
        assert "video_id" in first and first["video_id"]
        assert "title" in first and first["title"]
        assert "channel_id" in first and first["channel_id"]
        assert "channel_title" in first
        assert "published_at" in first
    except YouTubeAuthError:
        pytest.fail("YouTube API authentication failed with provided key.")
