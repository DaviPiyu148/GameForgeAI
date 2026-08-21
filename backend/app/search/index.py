import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np


logger = logging.getLogger(__name__)


def resolve_file_path(rel_path: str) -> str:
    """Resolve file path across root and backend working directories."""
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", rel_path)),
        os.path.join("backend", rel_path),
        rel_path,
    ]
    for p in candidates:
        norm_p = os.path.normpath(p)
        if os.path.exists(norm_p):
            return norm_p
    return os.path.normpath(rel_path)


class FAISSIndexManager:
    """Manager for loading and querying the FAISS vector index."""

    _instance: Optional["FAISSIndexManager"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        index_path: str = "data/processed/games_index.faiss",
        meta_path: str = "data/processed/index_meta.json",
    ):
        self.index_path = resolve_file_path(index_path)
        self.meta_path = resolve_file_path(meta_path)
        self.index: Optional[faiss.Index] = None
        self.id_mapping: List[str] = []
        self.metadata: Dict[str, Any] = {}
        self._load_index()

    def _load_index(self) -> None:
        if not os.path.exists(self.index_path) or not os.path.exists(self.meta_path):
            logger.warning(
                f"FAISS index or meta file not found at {self.index_path} / {self.meta_path}. Index is uninitialized."
            )
            return

        logger.info(f"Loading FAISS index from {self.index_path}...")
        self.index = faiss.read_index(self.index_path)
        with open(self.meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        self.id_mapping = [str(x) for x in self.metadata.get("id_mapping", [])]
        logger.info(f"FAISS index loaded successfully with {self.index.ntotal} vectors.")

    @classmethod
    def get_instance(
        cls,
        index_path: str = "data/processed/games_index.faiss",
        meta_path: str = "data/processed/index_meta.json",
    ) -> "FAISSIndexManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(index_path=index_path, meta_path=meta_path)
        return cls._instance

    def is_ready(self) -> bool:
        return self.index is not None and self.index.ntotal > 0 and len(self.id_mapping) > 0

    def search(self, query_vector: np.ndarray, top_k: int = 50) -> List[Tuple[str, float]]:
        """
        Execute vector similarity search.
        Returns list of (game_id, score) pairs.
        """
        if not self.is_ready():
            raise RuntimeError("FAISS index is not initialized or empty. Please run build_index.py.")

        vec = np.asarray(query_vector, dtype=np.float32)
        if vec.ndim == 1:
            vec = np.expand_dims(vec, axis=0)

        # L2-normalize query vector for cosine similarity
        norm = np.linalg.norm(vec, axis=1, keepdims=True)
        if norm[0, 0] > 0:
            vec = vec / norm

        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(vec, k)

        results: List[Tuple[str, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.id_mapping):
                game_id = self.id_mapping[idx]
                results.append((game_id, float(score)))

        return results
