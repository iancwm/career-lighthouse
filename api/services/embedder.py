"""Embedding service — loads a sentence transformer and provides encode/batch encode methods.

The Embedder is a singleton that lazily loads the configured embedding model.
If the sentence_transformers library is unavailable (e.g., in lightweight test envs),
a deterministic fallback vector is generated using SHA256 + numpy.

Usage:
    embedder = Embedder()
    vec = embedder.encode("sample text")  # returns 384-d normalized float32 array
    batch = embedder.encode_batch(["text1", "text2"])  # returns Nx384 array
"""
import numpy as np
import hashlib

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - lightweight fallback for test envs
    SentenceTransformer = None

from cfg import model_cfg

_MODEL_NAME = model_cfg["embedding"]["model"]
_EMBEDDING_DIM = model_cfg["embedding"]["dim"]


class Embedder:
    _instance = None

    def __new__(cls):
        # Singleton — model loads once per process
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            if SentenceTransformer is not None:
                cls._instance._model = SentenceTransformer(_MODEL_NAME)
                cls._instance._fallback = False
            else:
                cls._instance._model = None
                cls._instance._fallback = True
        return cls._instance

    def _fallback_vector(self, text: str) -> np.ndarray:
        """Generate a deterministic normalized vector from text hash when sentence-transformers is unavailable.

        Uses SHA256 to seed a numpy RNG; produces consistent vectors for the same input.
        Returns a normalized float32 vector of length embedding_dim (384 for all-MiniLM-L6-v2).
        """
        digest = hashlib.sha256(str(text).encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big", signed=False)
        rng = np.random.default_rng(seed)
        vec = rng.random(_EMBEDDING_DIM, dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec.astype(np.float32)

    def encode(self, text: str) -> np.ndarray:
        """Encode a single text string to a normalized embedding vector.

        Returns a 1-d float32 array of length embedding_dim (384 by default).
        Uses the configured sentence transformer or fallback deterministic vector.
        """
        if self._fallback:
            return self._fallback_vector(text)
        return self._model.encode(text, normalize_embeddings=True).astype(np.float32)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """Encode multiple texts to a batch of embedding vectors.

        Returns a 2-d float32 array of shape (len(texts), embedding_dim).
        Uses the configured sentence transformer or fallback deterministic vectors.
        """
        if self._fallback:
            return np.stack([self._fallback_vector(text) for text in texts], axis=0)
        return self._model.encode(texts, normalize_embeddings=True).astype(np.float32)
