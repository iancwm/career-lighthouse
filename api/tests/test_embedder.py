import numpy as np
from services.embedder import Embedder


def test_embed_returns_correct_dimension():
    embedder = Embedder()
    vec = embedder.encode("hello world")
    assert vec.shape == (384,)
    assert vec.dtype == np.float32


def test_embed_batch_returns_correct_shape():
    embedder = Embedder()
    vecs = embedder.encode_batch(["hello", "world"])
    assert vecs.shape == (2, 384)


def test_embed_same_text_same_vector():
    embedder = Embedder()
    v1 = embedder.encode("career advice")
    v2 = embedder.encode("career advice")
    np.testing.assert_array_equal(v1, v2)
