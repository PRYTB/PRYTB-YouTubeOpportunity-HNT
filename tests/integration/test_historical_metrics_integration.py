import pytest
from app.database.repositories import YouTubeRepository
from app.analytics.historical_metrics import HistoricalMetricsAnalyzer


@pytest.mark.integration
def test_postgres_historical_metrics_integration():
    repo = YouTubeRepository()

    # Get all video IDs in DB
    video_ids = repo.get_all_video_ids()
    if not video_ids:
        pytest.skip("No videos found in PostgreSQL for the historical integration test.")

    analyzer = HistoricalMetricsAnalyzer(repository=repo)

    tested_count = 0
    for vid in video_ids:
        history = repo.get_video_metrics_history(vid)
        if len(history) >= 2:
            metrics = analyzer.analyze_video(vid, snapshots=history)
            assert metrics.video_id == vid
            assert metrics.snapshot_count == len(history)
            assert len(metrics.intervals) == len(history) - 1
            for interval in metrics.intervals:
                assert interval.elapsed_hours > 0
            tested_count += 1
            if tested_count >= 3:
                break

    if tested_count == 0:
        # Test basic analyzer execution even if only 1 snapshot exists per video
        vid = video_ids[0]
        metrics = analyzer.analyze_video(vid)
        assert metrics.video_id == vid
        assert metrics.snapshot_count >= 1
