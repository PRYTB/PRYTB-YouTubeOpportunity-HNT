import pytest
from datetime import datetime, timezone

from app.database.insforge_client import InsForgeClient, InsForgeClientError
from app.database.repositories import YouTubeRepository
from app.models.youtube import YouTubeChannel, YouTubeVideo, CollectionResult, CollectionStats
from app.utils.config import settings


@pytest.mark.integration
def test_insforge_live_repository_persistence():
    if not settings.INSFORGE_URL or not settings.INSFORGE_URL.strip():
        pytest.skip("INSFORGE_URL not configured in .env; skipping live integration test.")

    client = InsForgeClient()
    repo = YouTubeRepository(client=client)

    ts = datetime.now(timezone.utc).isoformat()
    test_channel_id = "UC_TEST_INTEGRATION_99"
    test_video_id = "VID_TEST_INTEGRATION_99"

    test_channel = YouTubeChannel(
        channel_id=test_channel_id,
        channel_title="Integration Test Channel",
        channel_description="Created during automated integration test",
        published_at="2026-01-01T00:00:00Z",
        country="US",
        subscriber_count=999,
        video_count=10,
        view_count=50000
    )

    test_video = YouTubeVideo(
        video_id=test_video_id,
        channel_id=test_channel_id,
        title="Integration Test Video",
        description="Created during automated integration test",
        published_at="2026-01-01T00:00:00Z",
        duration_iso="PT5M",
        duration_seconds=300,
        view_count=100,
        like_count=10,
        comment_count=2,
        caption="false",
        definition="hd",
        licensed_content=False,
        default_language="en",
        default_audio_language="en"
    )

    collection = CollectionResult(
        query="integration_test",
        stats=CollectionStats(search_queries=1, total_video_ids_found=1, videos_fetched=1, channels_fetched=1),
        videos=[test_video],
        channels=[test_channel]
    )

    # Persist data to live InsForge DB
    p_result = repo.persist_collection(collection, checked_at=ts)

    assert p_result.channels_upserted == 1
    assert p_result.videos_upserted == 1
    assert p_result.channel_metrics_inserted == 1
    assert p_result.video_metrics_inserted == 1
    assert p_result.db_operations == 4

    # Re-run for idempotency verification against real DB
    p_result_retry = repo.persist_collection(collection, checked_at=ts)
    assert p_result_retry.channels_upserted == 1
    assert p_result_retry.videos_upserted == 1
