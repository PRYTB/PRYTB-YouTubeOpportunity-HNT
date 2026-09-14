import pytest
from app.collectors.youtube_collector import YouTubeCollector

@pytest.mark.integration
@pytest.mark.live_youtube
def test_youtube_collector_real_api():
    pytest.skip("YouTube API live call prohibited by Gate 7 reconciliation safety protocol.")
