"""
Integration test for NicheMiner with real InsForge database.
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

    # Verify cluster persistence and readback if DB connected
    repo = YouTubeRepository()
    inserted = repo.insert_clusters(result)
    assert inserted >= 0

    readback = repo.verify_clusters_readback(result.run_id)
    assert "clusters_exist" in readback

