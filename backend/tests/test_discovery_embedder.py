import numpy as np
import pytest

from app.search.embedder import QueryEmbedder


def test_embedder_singleton_instance():
    inst1 = QueryEmbedder.get_instance()
    inst2 = QueryEmbedder.get_instance()
    assert inst1 is inst2
    assert inst1.dimension == 384


def test_embed_query_produces_normalized_vector():
    embedder = QueryEmbedder.get_instance()
    vec = embedder.embed_query("cyberpunk action roguelite")

    assert isinstance(vec, np.ndarray)
    assert vec.dtype == np.float32
    assert vec.shape == (1, 384)

    # Check vector is L2-normalized (norm == 1.0)
    norm = np.linalg.norm(vec[0])
    assert abs(norm - 1.0) < 1e-4


def test_embed_query_empty_string_raises_value_error():
    embedder = QueryEmbedder.get_instance()
    with pytest.raises(ValueError, match="cannot be empty"):
        embedder.embed_query("   ")
