import pytest
from app.collectors.youtube_client import YouTubeClient, YouTubeAuthError
from app.utils.config import settings

@pytest.mark.integration
@pytest.mark.live_youtube
def test_youtube_connection():
    pytest.skip("YouTube API live call prohibited by Gate 7 reconciliation safety protocol.")
