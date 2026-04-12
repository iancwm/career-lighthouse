import numpy as np
import hashlib

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - lightweight fallback for test envs
    SentenceTransformer = None

from cfg import model_cfg

_MODEL_NAME = model_cfg["embedding"]["model"]


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
        """Deterministic 384-d fallback used when sentence-transformers is unavailable."""
        digest = hashlib.sha256(str(text).encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big", signed=False)
        rng = np.random.default_rng(seed)
        vec = rng.random(384, dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec.astype(np.float32)

    def encode(self, text: str) -> np.ndarray:
        if self._fallback:
            return self._fallback_vector(text)
        return self._model.encode(text, normalize_embeddings=True).astype(np.float32)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        if self._fallback:
            return np.stack([self._fallback_vector(text) for text in texts], axis=0)
        return self._model.encode(texts, normalize_embeddings=True).astype(np.float32)
