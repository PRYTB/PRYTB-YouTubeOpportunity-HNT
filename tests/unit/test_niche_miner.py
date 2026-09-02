"""
Unit tests for Sprint 5 - Niche Miner.
"""
import pytest
import numpy as np

from app.analytics.text_normalizer import clean_text_for_embedding, normalize_single_text, GENERIC_STOP_WORDS
from app.analytics.semantic_provider import TFIDFLocalSemanticProvider, OmniRouteEmbeddingProvider
from app.analytics.clustering_engine import ClusterOptimizer, detect_near_duplicates
from app.analytics.cluster_analyzer import (
    analyze_channel_diversity,
    cross_reference_outliers,
    select_representative_titles,
    calculate_cluster_confidence,
    calculate_cluster_signal_score
)
from app.analytics.labeler import ClusterLabeler, validate_label_quality
from app.models.outliers import VideoOutlierResult
from app.models.niche import ClusterHierarchy


def test_text_normalization():
    # Empty & None
    assert clean_text_for_embedding(None, None) == "untitled"
    assert clean_text_for_embedding("", "") == "untitled"

    # Unicode & emojis & URLs
    raw = "🔥 Check out https://example.com/test Python & Artificial Intelligence tutorial!   "
    clean = clean_text_for_embedding(raw)
    assert "https" not in clean
    assert "Python" in clean
    assert "Artificial Intelligence" in clean


def test_near_duplicates_detection():
    titles = [
        "What is Artificial Intelligence?",
        "What Exactly Is Artificial Intelligence?",
        "What Is Artificial Intelligence Explained",
        "Cybersecurity Hacking Tutorial 2025"
    ]
    groups = detect_near_duplicates(titles, similarity_threshold=0.6)
    assert len(groups) >= 1
    assert 0 in groups[0] and 1 in groups[0]


def test_stopwords_and_bigrams():
    provider = TFIDFLocalSemanticProvider(max_features=50, ngram_range=(1, 2))
    texts = [
        "Artificial Intelligence Safety and Risk Analysis",
        "Artificial Intelligence Ethics and Future Predictions",
        "Cybersecurity Network Security Fundamentals"
    ]
    embeddings = provider.embed_texts(texts)
    assert embeddings.shape[0] == 3
    assert provider.embedding_dimension <= 50


def test_label_quality_validation():
    score, warnings = validate_label_quality(
        niche="What Domain",
        subniche="Artificial Domain",
        microniche="Warns Domain",
        representative_titles=["What is AI Explained"]
    )
    assert score < 50.0
    assert len(warnings) > 0

    score2, warnings2 = validate_label_quality(
        niche="Artificial Intelligence",
        subniche="AI Safety & Risks",
        microniche="Warnings and predictions about advanced AI",
        representative_titles=["AI Safety and Warnings for Future AI"]
    )
    assert score2 >= 80.0
    assert len(warnings2) == 0


def test_clustering_reproducibility():
    optimizer = ClusterOptimizer(min_k=2, max_k=4, random_state=42)
    np.random.seed(42)
    c1 = np.random.normal(loc=0.0, scale=0.1, size=(10, 20))
    c2 = np.random.normal(loc=10.0, scale=0.1, size=(10, 20))
    data = np.vstack([c1, c2])

    labels1, algo1, params1, score1 = optimizer.fit_optimal_clusters(data, algorithm="kmeans")
    labels2, algo2, params2, score2 = optimizer.fit_optimal_clusters(data, algorithm="kmeans")

    assert np.array_equal(labels1, labels2)
    assert score1 > 0.3


def test_channel_diversity():
    ch_dom = ["ch_A", "ch_A", "ch_A", "ch_A", "ch_B"]
    u_ch, dom_share, cat, warnings = analyze_channel_diversity(ch_dom)
    assert u_ch == 2
    assert dom_share == 0.8
    assert cat == "LOW_DIVERSITY"
    assert len(warnings) > 0

    ch_div = ["ch_A", "ch_B", "ch_C", "ch_D"]
    u_ch2, dom_share2, cat2, warnings2 = analyze_channel_diversity(ch_div)
    assert u_ch2 == 4
    assert dom_share2 == 0.25
    assert cat2 == "HIGH_DIVERSITY"
    assert len(warnings2) == 0


def test_outlier_crossover():
    v1 = VideoOutlierResult(video_id="v1", channel_id="c1", is_strong_outlier=True, outlier_ratio=5.0)
    v2 = VideoOutlierResult(video_id="v2", channel_id="c1", is_major_outlier=True, outlier_ratio=12.0)
    outliers_map = {"v1": v1, "v2": v2}

    stats = cross_reference_outliers(["v1", "v2", "v3"], outliers_map)
    assert stats["outlier_count"] == 2
    assert stats["strong_outlier_count"] == 1
    assert stats["major_outlier_count"] == 1
    assert stats["median_outlier_ratio"] == 8.5
    assert stats["max_outlier_ratio"] == 12.0


def test_labeler_fallback():
    labeler = ClusterLabeler(api_key=None)
    titles = [
        "Cybersecurity Network Defense Training Tutorial",
        "Ethical Hacking and Firewall Configuration",
        "Beginner Cybersecurity Certification Guide"
    ]
    hierarchy = labeler.label_cluster(titles)
    assert isinstance(hierarchy, ClusterHierarchy)
    assert hierarchy.niche == "Cybersecurity"
    assert hierarchy.subniche != "Cybersecurity Domain"

