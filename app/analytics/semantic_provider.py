import re
from typing import List, Tuple
import numpy as np


class SemanticProvider:
    """
    Abstract interface for semantic embedding providers.
    """
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError

    @property
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    def embedding_dimension(self) -> int:
        raise NotImplementedError


class TFIDFLocalSemanticProvider(SemanticProvider):
    """
    Deterministic local semantic embedding provider based on TF-IDF representation.
    Supports unigrams & bigrams, stopword filtering, min_df/max_df tuning, sublinear TF scaling, and L2 normalization.
    """
    def __init__(
        self,
        max_features: int = 500,
        ngram_range: Tuple[int, int] = (1, 2),
        min_df: int = 1,
        max_df: float = 0.95,
        sublinear_tf: bool = True
    ):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from app.analytics.text_normalizer import GENERIC_STOP_WORDS

        self._max_features = max_features
        self._ngram_range = ngram_range
        
        # Combine standard english stopwords + domain noisy structural terms
        custom_stopwords = list(GENERIC_STOP_WORDS) + [
            "the", "a", "an", "is", "are", "and", "or", "in", "on", "at", "to", "for", "with",
            "by", "about", "against", "between", "into", "through", "during", "before", "after",
            "above", "below", "from", "up", "down", "in", "out", "on", "off", "over", "under",
            "again", "further", "then", "once", "here", "there", "when", "where", "why", "how",
            "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no",
            "nor", "not", "only", "own", "same", "so", "than", "too", "very", "can", "will",
            "just", "should", "now"
        ]

        self._vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            min_df=min_df,
            max_df=max_df,
            sublinear_tf=sublinear_tf,
            stop_words=custom_stopwords
        )
        self._fitted = False
        self._dim = max_features

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dim))

        # Standardize strings
        clean_texts = [t if isinstance(t, str) and t.strip() else "empty_text" for t in texts]

        # Fit or transform
        try:
            if not self._fitted:
                matrix = self._vectorizer.fit_transform(clean_texts).toarray()
                self._fitted = True
                self._dim = matrix.shape[1]
            else:
                matrix = self._vectorizer.transform(clean_texts).toarray()
            
            # Normalize vectors to unit length (L2 norm) for cosine distance compatibility
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            return matrix / norms
        except Exception:
            # Fallback for unexpected vectorizer failures
            n = len(texts)
            return np.zeros((n, self._dim))

    @property
    def provider_name(self) -> str:
        return "LocalSemanticProvider (TF-IDF)"

    @property
    def embedding_dimension(self) -> int:
        return self._dim



class OmniRouteEmbeddingProvider(SemanticProvider):
    """
    OmniRoute embedding provider if supported/configured via HTTP/OpenAI client.
    Fallback to TF-IDF if unavailable.
    """
    def __init__(self, api_key: str = "", model_name: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model_name = model_name
        self._fallback_provider = TFIDFLocalSemanticProvider()

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        if not self.api_key:
            return self._fallback_provider.embed_texts(texts)
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            res = client.embeddings.create(input=texts, model=self.model_name)
            embeddings = [item.embedding for item in res.data]
            return np.array(embeddings)
        except Exception:
            return self._fallback_provider.embed_texts(texts)

    @property
    def provider_name(self) -> str:
        if self.api_key:
            return f"OmniRouteEmbeddingProvider ({self.model_name})"
        return f"{self._fallback_provider.provider_name} [OmniRoute Fallback]"

    @property
    def embedding_dimension(self) -> int:
        return self._fallback_provider.embedding_dimension
