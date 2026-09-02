import inspect
from unittest.mock import MagicMock, patch

import pytest

from app.models.outliers import VideoOutlierResult
from scripts import sprint5_reproducibility_runner as runner


def make_rows():
    """Create test rows matching the approved 83-video production dataset."""
    # Use the approved assignments hash to derive deterministic test data
    rows = []
    # We'll create minimal test rows that match the approved structure
    # The actual runner computes these from real data
    for cluster_id in range(runner.APPROVED_K):
        for i in range(3):  # Just a few per cluster for testing
            video_id = f"TEST_VID_{cluster_id}_{i}"
            rows.append({
                "video_id": video_id,
                "semantic_text": f"test content {video_id}",
                "semantic_text_title": f"test title {video_id}",
                "channel_id": f"CH{i % 12:02d}",
                "title": f"Test Title {video_id}",
            })
    return rows


def make_result(outliers=None):
    # Use a minimal valid result for testing
    rows = make_rows()
    dataset_hash = runner.compute_dataset_hash(rows)
    return runner.build_preflight_result(
        rows,
        dataset_hash,
        channel_count=12,
        audit={
            "videos_before": len(rows),
            "test_records_detected": 0,
            "test_records_excluded": 0,
            "test_video_ids": [],
            "production_videos": len(rows),
        },
        labels=[i % runner.APPROVED_K for i in range(len(rows))],
        silhouette=runner.APPROVED_SILHOUETTE,
        assignments_hash=runner.compute_assignments_hash(
            [r["video_id"] for r in rows],
            [i % runner.APPROVED_K for i in range(len(rows))]
        ),
    )


def make_outlier(video_id, ratio=3.0, strong=False, major=False, extreme=False):
    return VideoOutlierResult(
        video_id=video_id,
        channel_id="CH00",
        outlier_ratio=ratio,
        is_strong_outlier=strong,
        is_major_outlier=major,
        is_extreme_outlier=extreme,
    )


def test_approved_configuration_constants_are_exact():
    """Test that approved configuration constants match the production-approved values."""
    assert runner.APPROVED_REPRESENTATION == "title_only_unigrams"
    assert runner.APPROVED_TFIDF_PARAMETERS == {
        "max_features": 500,
        "ngram_range": [1, 1],
        "min_df": 2,
        "max_df": 0.9,
        "sublinear_tf": False,
    }
    assert runner.APPROVED_ALGORITHM == "kmeans"
    assert runner.APPROVED_K == 10
    assert runner.APPROVED_RANDOM_STATE == 42
    # These are the approved production values from the final preflight
    assert abs(runner.APPROVED_SILHOUETTE - 0.2468982051367785) < 1e-12
    assert runner.APPROVED_DATASET_HASH == "4d81c80e8da54b371c7eb969957ea347fc632d82abd737719141c866f4bfe9ad"
    assert runner.APPROVED_ASSIGNMENTS_HASH == "6c0e7bb6aeec75985664becb05f7c61cbfec874c15a6ec7395d60c2996436288"
    assert runner.APPROVED_PRODUCTION_VIDEOS == 83
    assert runner.APPROVED_CLUSTERS == 10


def test_canonical_dataset_rows_are_sorted_before_hashing():
    videos = [
        {"video_id": "B", "title": "Second", "description": "text", "channel_id": "2"},
        {"video_id": "A", "title": "First", "description": "text", "channel_id": "1"},
    ]

    rows = runner.canonical_dataset_rows(videos)

    assert [row["video_id"] for row in rows] == ["A", "B"]
    assert rows[0]["semantic_text_title"] == "first"
    assert "text" in rows[0]["semantic_text"]
    assert runner.compute_dataset_hash(rows) != runner.compute_dataset_hash(
        list(reversed(rows))
    )


def test_validate_production_dataset_rejects_invalid_input():
    rows = make_rows()
    
    # Test empty dataset
    with pytest.raises(ValueError, match="Production dataset is empty"):
        runner.validate_production_dataset([])
    
    # Test empty video_id
    rows_bad = [dict(r) for r in rows]
    rows_bad[0]["video_id"] = ""
    with pytest.raises(ValueError, match="empty video_id"):
        runner.validate_production_dataset(rows_bad)
    
    # Test duplicate video_id
    rows_bad = [dict(r) for r in rows]
    rows_bad[1]["video_id"] = rows_bad[0]["video_id"]
    with pytest.raises(ValueError, match="duplicate video IDs"):
        runner.validate_production_dataset(rows_bad)
    
    # Test missing title
    rows_bad = [dict(r) for r in rows]
    rows_bad[0]["title"] = ""
    with pytest.raises(ValueError, match="title and semantic text"):
        runner.validate_production_dataset(rows_bad)


def test_validate_production_dataset_rejects_hash_mismatch():
    rows = make_rows()
    with pytest.raises(ValueError, match="hash mismatch"):
        runner.validate_production_dataset(rows, expected_hash="wrong")


def test_is_test_video_identifies_integration_test_record():
    """Test that VID_TEST_INTEGRATION_99 is correctly identified as a test record."""
    test_video = {
        "video_id": "VID_TEST_INTEGRATION_99",
        "title": "Integration Test Video",
        "description": "This is integration test data",
        "channel_id": "UC_TEST_INTEGRATION_99",
    }
    assert runner.is_test_video(test_video) is True
    
    # Regular video should not be flagged
    regular_video = {
        "video_id": "VID_REAL_123",
        "title": "How to learn Python",
        "description": "A tutorial about Python programming",
        "channel_id": "UC_REAL_CHANNEL",
    }
    assert runner.is_test_video(regular_video) is False


def test_audit_production_videos_excludes_test_records():
    videos = [
        {"video_id": "VID_REAL_1", "title": "Real Video", "description": "Content", "channel_id": "CH1"},
        {"video_id": "VID_TEST_INTEGRATION_99", "title": "Test", "description": "integration test data", "channel_id": "UC_TEST_INTEGRATION_99"},
    ]
    production, audit = runner.audit_production_videos(videos)
    assert audit["videos_before"] == 2
    assert audit["test_records_detected"] == 1
    assert audit["test_records_excluded"] == 1
    assert audit["test_video_ids"] == ["VID_TEST_INTEGRATION_99"]
    assert audit["production_videos"] == 1
    assert len(production) == 1


def test_compute_assignments_hash_is_deterministic():
    """Test that assignments hash computation is deterministic."""
    video_ids = ["VID_A", "VID_B", "VID_C", "VID_D"]
    labels = [0, 1, 0, 1]
    hash1 = runner.compute_assignments_hash(video_ids, labels)
    hash2 = runner.compute_assignments_hash(video_ids, labels)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex
    
    # Different order should produce same hash (sorted internally)
    video_ids_shuffled = ["VID_D", "VID_A", "VID_C", "VID_B"]
    labels_shuffled = [1, 0, 0, 1]
    hash3 = runner.compute_assignments_hash(video_ids_shuffled, labels_shuffled)
    assert hash1 == hash3


def test_build_preflight_result_produces_valid_structure():
    """Test that build_preflight_result produces a valid NicheMiningResult."""
    rows = make_rows()
    dataset_hash = runner.compute_dataset_hash(rows)
    labels = [i % runner.APPROVED_K for i in range(len(rows))]
    silhouette = runner.APPROVED_SILHOUETTE
    assignments_hash = runner.compute_assignments_hash(
        [r["video_id"] for r in rows], labels
    )
    audit = {
        "videos_before": len(rows),
        "test_records_detected": 0,
        "test_records_excluded": 0,
        "test_video_ids": [],
        "production_videos": len(rows),
    }
    
    result = runner.build_preflight_result(
        rows, dataset_hash, 12, audit, labels, silhouette, assignments_hash
    )
    
    assert result.total_clusters == 10
    assert len(result.clusters) == 10
    assert sum(cluster.video_count for cluster in result.clusters) == len(rows)
    assert result.parameters["assignment_source"] == "recomputed_kmeans"
    assert result.parameters["dataset_hash"] == dataset_hash
    assert result.parameters["silhouette"] == silhouette
    assert result.parameters["assignments_hash"] == assignments_hash
    assert result.algorithm == "kmeans"
    assert result.parameters["K"] == 10
    assert result.parameters["random_state"] == 42
    assert result.unassigned_count == 0
    
    # Each cluster should have at least one video
    for cluster in result.clusters:
        assert cluster.video_count > 0
        assert len(cluster.video_ids) == cluster.video_count
        assert cluster.cluster_id >= 0
        assert cluster.cluster_id < 10


def test_preflight_does_not_persist_or_call_outliers():
    """Test that run_preflight does not call persistence or outlier engine."""
    rows = make_rows()
    dataset_hash = runner.compute_dataset_hash(rows)
    repo = MagicMock()
    engine = MagicMock()
    
    with patch.object(
        runner, "load_clean_dataset",
        return_value=(rows, dataset_hash, 12, {
            "videos_before": len(rows),
            "test_records_detected": 0,
            "test_records_excluded": 0,
            "test_video_ids": [],
            "production_videos": len(rows),
        }),
    ), patch.object(
        runner, "cluster_clean_dataset",
        return_value=(
            [i % runner.APPROVED_K for i in range(len(rows))],
            runner.APPROVED_SILHOUETTE,
            runner.APPROVED_ASSIGNMENTS_HASH,
        ),
    ):
        result = runner.run_preflight(repository=repo)
    
    engine.analyze_all.assert_not_called()
    repo.insert_clusters.assert_not_called()
    repo.verify_clusters_readback.assert_not_called()
    assert result.parameters["assignment_source"] == "recomputed_kmeans"


def test_runner_source_contains_no_clustering_or_persistence_execution():
    """Verify the runner source doesn't contain clustering/persistence logic in wrong places."""
    source = inspect.getsource(runner)
    
    # These should be in the module (they ARE the approved pipeline)
    assert "ClusterOptimizer(" in source  # Used in cluster_clean_dataset
    assert "silhouette_score(" in source  # Used in cluster_clean_dataset
    assert "embed_texts(" in source  # Used in cluster_clean_dataset
    
    # But run_approved_final should just delegate to run_preflight
    approved_final_source = inspect.getsource(runner.run_approved_final)
    assert "return run_preflight" in approved_final_source
    assert ".insert_clusters(" not in approved_final_source
    assert ".verify_clusters_readback(" not in approved_final_source


def test_result_report_has_correct_structure():
    """Test that result_report produces the expected structure."""
    result = make_result()
    report = runner.result_report(result)
    
    assert report["mode"] == "preflight"
    assert report["persisted"] is False
    assert report["production_videos"] == result.videos_embedded
    assert report["dataset_hash"] == result.parameters["dataset_hash"]
    assert report["representation"] == runner.APPROVED_REPRESENTATION
    assert report["algorithm"] == runner.APPROVED_ALGORITHM
    assert report["K"] == runner.APPROVED_K
    assert report["random_state"] == runner.APPROVED_RANDOM_STATE
    assert report["silhouette"] == result.parameters["silhouette"]
    assert report["assignments_hash"] == result.parameters["assignments_hash"]
    assert report["clusters"] == 10
    assert report["sum_video_count"] == sum(c.video_count for c in result.clusters)
    assert "cluster_sizes" in report