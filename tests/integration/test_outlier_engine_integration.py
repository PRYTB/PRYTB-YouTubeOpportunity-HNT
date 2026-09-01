"""
Integration test for OutlierEngine with real InsForge database.
"""
import pytest
from app.analytics.outlier_engine import OutlierEngine
from app.database.repositories import YouTubeRepository


@pytest.mark.integration
def test_outlier_engine_integration():
    repository = YouTubeRepository()
    engine = OutlierEngine(repository=repository)

    # 1. Fetch real video IDs
    video_ids = repository.get_all_video_ids()
    assert len(video_ids) > 0, "No videos found in InsForge database."

    # 2. Analyze first video
    first_v_id = video_ids[0]
    result = engine.analyze_video(first_v_id)

    assert result.video_id == first_v_id
    assert isinstance(result.warnings, list)
    assert 0.0 <= result.confidence <= 100.0

    # 3. Analyze all videos
    all_results = engine.analyze_all()
    assert len(all_results) >= len(video_ids)

    # 4. Rank outliers (Top 5)
    top_5 = engine.rank_outliers(limit=5)
    assert len(top_5) <= 5
    if len(top_5) > 1:
        assert top_5[0].outlier_rank_score >= top_5[1].outlier_rank_score
