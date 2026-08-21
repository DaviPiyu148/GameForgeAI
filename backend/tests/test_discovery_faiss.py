import json
import os
import tempfile
import faiss
import numpy as np
import pytest

from app.search.index import FAISSIndexManager


def test_faiss_index_manager_synthetic_index():
    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = os.path.join(tmpdir, "test_index.faiss")
        meta_path = os.path.join(tmpdir, "test_meta.json")

        dim = 384
        num_vectors = 5
        rng = np.random.default_rng(42)
        vectors = rng.standard_normal((num_vectors, dim)).astype(np.float32)
        # Normalize vectors
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / norms

        index = faiss.IndexFlatIP(dim)
        index.add(vectors)
        faiss.write_index(index, index_path)

        id_mapping = ["game_10", "game_20", "game_30", "game_40", "game_50"]
        meta = {
            "catalog_version": "1.0.0",
            "embedding_dimension": dim,
            "id_mapping": id_mapping,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)

        # Create manager instance with synthetic paths
        manager = FAISSIndexManager(index_path=index_path, meta_path=meta_path)
        assert manager.is_ready() is True

        # Query with vector identical to game_20 (index 1)
        query_vec = vectors[1:2]
        results = manager.search(query_vec, top_k=3)

        assert len(results) == 3
        # First result should be game_20 with score ≈ 1.0
        assert results[0][0] == "game_20"
        assert abs(results[0][1] - 1.0) < 1e-4


def test_faiss_index_manager_uninitialized():
    manager = FAISSIndexManager(index_path="nonexistent.faiss", meta_path="nonexistent.json")
    assert manager.is_ready() is False

    with pytest.raises(RuntimeError, match="not initialized"):
        manager.search(np.zeros((1, 384), dtype=np.float32))
