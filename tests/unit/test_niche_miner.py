"""
Unit tests for Sprint 5 - Niche Miner.
"""
import pytest
import numpy as np

from app.analytics.text_normalizer import clean_text_for_embedding, normalize_single_text
from app.analytics.semantic_provider import TFIDFLocalSemanticProvider, OmniRouteEmbeddingProvider
from app.analytics.clustering_engine import ClusterOptimizer
from app.analytics.cluster_analyzer import (
    analyze_channel_diversity,
    cross_reference_outliers,
    select_representative_titles,
    calculate_cluster_confidence,
    calculate_cluster_signal_score
)
from app.analytics.labeler import ClusterLabeler
from app.models.outliers import VideoOutlierResult
from app.models.niche import ClusterHierarchy


def test_text_normalization():
    # Empty & None
    assert clean_text_for_embedding(None, None) == "untitled"
    assert clean_text_for_embedding("", "") == "untitled"

    # Unicode & emojis & URLs
    raw = "🔥 Check out https://example.com/test Python & GPT-5 tutorial!   "
    clean = clean_text_for_embedding(raw)
    assert "https" not in clean
    assert "Python" in clean
    assert "GPT-5" in clean


def test_semantic_provider():
    provider = TFIDFLocalSemanticProvider(max_features=50)
    texts = [
        "Artificial Intelligence and Machine Learning tutorial",
        "Deep Learning neural networks with Python",
        "Cybersecurity network defense and ethical hacking"
    ]
    embeddings = provider.embed_texts(texts)
    assert isinstance(embeddings, np.ndarray)
    assert embeddings.shape[0] == 3
    assert embeddings.shape[1] <= 50
    assert provider.provider_name.startswith("LocalSemanticProvider")


def test_clustering_reproducibility():
    optimizer = ClusterOptimizer(min_k=2, max_k=4, random_state=42)
    # Generate 2 clear clusters
    c1 = np.random.normal(loc=0.0, scale=0.1, size=(10, 20))
    c2 = np.random.normal(loc=10.0, scale=0.1, size=(10, 20))
    data = np.vstack([c1, c2])

    labels1, algo1, params1, score1 = optimizer.fit_optimal_clusters(data, algorithm="kmeans")
    labels2, algo2, params2, score2 = optimizer.fit_optimal_clusters(data, algorithm="kmeans")

    assert np.array_equal(labels1, labels2)
    assert score1 > 0.5


def test_channel_diversity():
    # Dominant channel case (LOW_DIVERSITY)
    ch_dom = ["ch_A", "ch_A", "ch_A", "ch_A", "ch_B"]
    u_ch, dom_share, cat, warnings = analyze_channel_diversity(ch_dom)
    assert u_ch == 2
    assert dom_share == 0.8
    assert cat == "LOW_DIVERSITY"
    assert len(warnings) > 0

    # Diverse channels case (HIGH_DIVERSITY)
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
        "Python Cybersecurity Automation Tutorial",
        "Python Hacking Scripts for Beginners",
        "Automating Security Scans with Python"
    ]
    hierarchy = labeler.label_cluster(titles)
    assert isinstance(hierarchy, ClusterHierarchy)
    assert "Python" in hierarchy.niche or "Security" in hierarchy.niche or "Cybersecurity" in hierarchy.niche
    assert hierarchy.confidence == 60.0


def test_confidence_and_signal_score():
    conf = calculate_cluster_confidence(
        semantic_quality=0.8,
        video_count=10,
        unique_channels=5,
        dominant_channel_share=0.2,
        outlier_count=3
    )
    assert conf >= 80.0

    score = calculate_cluster_signal_score(
        semantic_quality=0.8,
        outlier_count=3,
        video_count=10,
        dominant_channel_share=0.2,
        confidence=conf
    )
    assert score > 0.0
