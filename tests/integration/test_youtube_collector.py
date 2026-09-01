import pytest
from app.collectors.youtube_collector import YouTubeCollector

@pytest.mark.integration
def test_youtube_collector_real_api():
    collector = YouTubeCollector()
    res = collector.collect_keyword(query="artificial intelligence", max_videos=3)

    assert res.query == "artificial intelligence"
    assert len(res.videos) > 0
    assert len(res.channels) > 0
    
    first_video = res.videos[0]
    assert first_video.video_id is not None and len(first_video.video_id) > 0
    assert first_video.title is not None and len(first_video.title) > 0
    assert first_video.channel_id is not None and len(first_video.channel_id) > 0

    first_channel = res.channels[0]
    assert first_channel.channel_id is not None and len(first_channel.channel_id) > 0
    assert first_channel.channel_title is not None and len(first_channel.channel_title) > 0
