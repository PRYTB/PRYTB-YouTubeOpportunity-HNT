import pytest
import numpy as np
from app.analytics.semantic_provider import TFIDFLocalSemanticProvider

def test_tfidf_semantic_provider_valid():
    provider = TFIDFLocalSemanticProvider(max_features=100)
    texts = ["python data science analysis", "machine learning deep neural network", "software engineering backend API"]
    embeddings = provider.embed_texts(texts)
    assert embeddings.shape == (3, 100) or embeddings.shape[0] == 3
    norms = np.linalg.norm(embeddings, axis=1)
    np.testing.assert_allclose(norms, 1.0, rtol=1e-5)

def test_tfidf_semantic_provider_invalid_input():
    provider = TFIDFLocalSemanticProvider(max_features=100)
    with pytest.raises(ValueError, match="is not a string"):
        provider.embed_texts(["valid text", 12345])

    with pytest.raises(ValueError, match="is empty or blank"):
        provider.embed_texts(["valid text", "   "])

def test_tfidf_semantic_provider_zero_norm_error():
    provider = TFIDFLocalSemanticProvider(max_features=100)
    # If text consists only of stopwords, TF-IDF result matrix will be all zeros.
    with pytest.raises(ValueError, match="contains zero norm rows"):
        provider.embed_texts(["the a an is are", "valid python text"])


def test_tfidf_tokenless_rejection_does_not_fit_provider():
    provider = TFIDFLocalSemanticProvider(max_features=100)
    with pytest.raises(ValueError, match="contains zero norm rows"):
        provider.embed_texts(["the and", "of or"])
    assert provider._fitted is False
    provider.embed_texts(["python backend", "notion calendar"])
    with pytest.raises(ValueError, match="contains zero norm rows"):
        provider.embed_texts(["the and"])


def test_tfidf_preserves_approved_vocabulary_pruning_fallback():
    provider = TFIDFLocalSemanticProvider(max_features=100)
    provider.embed_texts(["python backend", "notion calendar"])
    embedding = provider.embed_texts(["unseen vocabulary"])
    np.testing.assert_allclose(
        embedding, np.full_like(embedding, 1.0 / np.sqrt(embedding.shape[1]))
    )
