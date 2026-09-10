"""
Integration test for NicheMiner with the real PostgreSQL database.
"""
import pytest
from app.analytics.niche_miner import NicheMiner
from app.database.repositories import YouTubeRepository
from app.models.niche import NicheMiningResult


@pytest.mark.integration
def test_niche_miner_integration():
    repository = YouTubeRepository()
    miner = NicheMiner(repository=repository)

    # Execute full pipeline with limit
    result = miner.mine(limit=20, min_cluster_size=2)

    assert isinstance(result, NicheMiningResult)
    assert result.videos_considered > 0
    assert result.videos_embedded <= result.videos_considered
    assert len(result.clusters) > 0
    assert result.run_id is not None
    assert result.semantic_provider in ["OmniRouteEmbeddingProvider", "LocalSemanticProvider (TF-IDF)"]

    # Verify cluster structure
    first_cluster = result.clusters[0]
    assert first_cluster.cluster_id >= 0
    assert first_cluster.video_count > 0
    assert len(first_cluster.video_ids) == first_cluster.video_count
    assert 0.0 <= first_cluster.dominant_channel_share <= 1.0
    assert 0.0 <= first_cluster.confidence <= 100.0
    assert first_cluster.niche != ""
    assert first_cluster.subniche != ""
    assert first_cluster.microniche != ""

    # Verify schema, exact writes, and real read-back.
    repo = YouTubeRepository()
    repo.verify_niche_schema()
    written = repo.insert_clusters(result)
    expected_videos = sum(len(cluster.video_ids) for cluster in result.clusters)

    assert written.clusters_written == len(result.clusters)
    assert written.subniches_written == len(result.clusters)
    assert written.cluster_videos_written == expected_videos

    try:
        readback = repo.verify_clusters_readback(result)
        assert readback.actual_clusters == len(result.clusters)
        assert readback.actual_subniches == len(result.clusters)
        assert readback.actual_cluster_videos == expected_videos
        assert readback.unique_videos == expected_videos
        assert readback.unique_cluster_ids == len(result.clusters)
        assert readback.duplicate_clusters == 0
        assert readback.duplicate_videos == 0
        assert readback.orphan_cluster_videos == 0
        assert readback.orphan_subniches == 0
        assert readback.missing_videos == 0
        assert readback.verified is True
    finally:
        # Guaranteed cleanup of test execution artifacts from target database
        with repo.client.get_connection() as conn:
            with conn.cursor() as cur:
                # Delete cluster_videos only for this run_id
                cur.execute("DELETE FROM cluster_videos WHERE run_id = %s", (result.run_id,))
                cur.execute("DELETE FROM subniches WHERE run_id = %s", (result.run_id,))
                cur.execute("DELETE FROM clusters WHERE run_id = %s", (result.run_id,))
                conn.commit()

