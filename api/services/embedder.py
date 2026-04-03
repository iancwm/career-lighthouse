import numpy as np
from sentence_transformers import SentenceTransformer

from cfg import model_cfg

_MODEL_NAME = model_cfg["embedding"]["model"]


class Embedder:
    _instance = None

    def __new__(cls):
        # Singleton — model loads once per process
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = SentenceTransformer(_MODEL_NAME)
        return cls._instance

    def encode(self, text: str) -> np.ndarray:
        return self._model.encode(text, normalize_embeddings=True).astype(np.float32)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, normalize_embeddings=True).astype(np.float32)
