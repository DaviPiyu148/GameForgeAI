import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

import faiss
import numpy as np

from app.search.candidate_pool import DiscoveryCandidatePool


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


POOL_INDEX_PATHS: Dict[DiscoveryCandidatePool, Tuple[str, str]] = {
    DiscoveryCandidatePool.POPULAR_20K: (
        "data/processed/games_index.faiss",
        "data/processed/index_meta.json",
    ),
    DiscoveryCandidatePool.REVIEWED_ONLY: (
        "data/processed/games_index_reviewed_only.faiss",
        "data/processed/index_meta_reviewed_only.json",
    ),
    DiscoveryCandidatePool.FULL_CATALOG: (
        "data/processed/games_index_full.faiss",
        "data/processed/index_meta_full.json",
    ),
}


class FAISSIndexManager:
    """Manager for loading, querying, and managing multi-pool FAISS vector indexes."""

    _instance: Optional["FAISSIndexManager"] = None
    _lock = threading.RLock()

    def __init__(
        self,
        index_path: str = "data/processed/games_index.faiss",
        meta_path: str = "data/processed/index_meta.json",
        pool_paths: Optional[Dict[DiscoveryCandidatePool, Tuple[str, str]]] = None,
    ):
        self.index_path = resolve_file_path(index_path)
        self.meta_path = resolve_file_path(meta_path)
        self._custom_pool_paths = pool_paths or {}
        self.index: Optional[faiss.Index] = None
        self.id_mapping: List[str] = []
        self.metadata: Dict[str, Any] = {}
        self._pool_cache: Dict[DiscoveryCandidatePool, Dict[str, Any]] = {}
        self._load_index()

    def _load_index(self) -> None:
        if not os.path.exists(self.index_path) or not os.path.exists(self.meta_path):
            logger.warning(
                f"FAISS index or meta file not found at {self.index_path} / {self.meta_path}. Index is uninitialized."
            )
            return

        logger.info(f"Loading primary FAISS index from {self.index_path}...")
        self.index = faiss.read_index(self.index_path)
        with open(self.meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        self.id_mapping = [str(x) for x in self.metadata.get("id_mapping", [])]
        self._id_to_pos: Dict[str, int] = {gid: idx for idx, gid in enumerate(self.id_mapping)}
        logger.info(f"FAISS index loaded successfully with {self.index.ntotal} vectors.")

        # Seed primary pool into pool cache
        self._pool_cache[DiscoveryCandidatePool.POPULAR_20K] = {
            "index": self.index,
            "id_mapping": self.id_mapping,
            "id_to_pos": self._id_to_pos,
            "id_set": set(self.id_mapping),
            "metadata": self.metadata,
        }

    def _get_or_load_pool(self, pool: DiscoveryCandidatePool = DiscoveryCandidatePool.POPULAR_20K) -> Optional[Dict[str, Any]]:
        if pool in self._pool_cache:
            return self._pool_cache[pool]

        with self._lock:
            if pool in self._pool_cache:
                return self._pool_cache[pool]

            if pool == DiscoveryCandidatePool.POPULAR_20K:
                if self.index is not None:
                    pool_data = {
                        "index": self.index,
                        "id_mapping": self.id_mapping,
                        "id_to_pos": getattr(self, "_id_to_pos", {gid: idx for idx, gid in enumerate(self.id_mapping)}),
                        "id_set": set(self.id_mapping),
                        "metadata": self.metadata,
                    }
                    self._pool_cache[pool] = pool_data
                    return pool_data
                return None

            if self.index is None and not self._custom_pool_paths:
                return None

            paths = self._custom_pool_paths.get(pool) or POOL_INDEX_PATHS.get(pool)
            if not paths:
                return self._pool_cache.get(DiscoveryCandidatePool.POPULAR_20K)

            idx_path = resolve_file_path(paths[0])
            meta_path = resolve_file_path(paths[1])

            if not os.path.exists(idx_path) or not os.path.exists(meta_path):
                # Fallback to legacy benchmark path if present
                legacy_map = {
                    DiscoveryCandidatePool.REVIEWED_ONLY: (
                        "data/benchmark_indexes/games_index_reviewed_only.faiss",
                        "data/benchmark_indexes/index_meta_reviewed_only.json",
                    ),
                    DiscoveryCandidatePool.FULL_CATALOG: (
                        "data/benchmark_indexes/games_index_full.faiss",
                        "data/benchmark_indexes/index_meta_full.json",
                    ),
                }
                leg = legacy_map.get(pool)
                if leg and os.path.exists(resolve_file_path(leg[0])) and os.path.exists(resolve_file_path(leg[1])):
                    idx_path = resolve_file_path(leg[0])
                    meta_path = resolve_file_path(leg[1])
                else:
                    logger.info(f"Designated index for pool {pool.value} not found at {idx_path}; falling back to primary index.")
                    return self._get_or_load_pool(DiscoveryCandidatePool.POPULAR_20K)

            try:
                logger.info(f"Loading FAISS index for pool {pool.value} from {idx_path}...")
                pool_idx = faiss.read_index(idx_path)
                with open(meta_path, "r", encoding="utf-8") as f:
                    pool_meta = json.load(f)
                mapping = [str(x) for x in pool_meta.get("id_mapping", [])]
                id_to_pos = {gid: idx for idx, gid in enumerate(mapping)}
                id_set = set(mapping)
                pool_data = {
                    "index": pool_idx,
                    "id_mapping": mapping,
                    "id_to_pos": id_to_pos,
                    "id_set": id_set,
                    "metadata": pool_meta,
                }
                self._pool_cache[pool] = pool_data
                logger.info(f"FAISS index for pool {pool.value} loaded successfully ({pool_idx.ntotal} vectors).")
                return pool_data
            except Exception as ex:
                logger.warning(f"Failed to load FAISS index for pool {pool.value}: {ex}")
                return self._get_or_load_pool(DiscoveryCandidatePool.POPULAR_20K)

    @classmethod
    def get_instance(
        cls,
        index_path: str = "data/processed/games_index.faiss",
        meta_path: str = "data/processed/index_meta.json",
        pool_paths: Optional[Dict[DiscoveryCandidatePool, Tuple[str, str]]] = None,
    ) -> "FAISSIndexManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(index_path=index_path, meta_path=meta_path, pool_paths=pool_paths)
        return cls._instance

    def is_ready(self, pool: DiscoveryCandidatePool = DiscoveryCandidatePool.POPULAR_20K) -> bool:
        pool_data = self._get_or_load_pool(pool)
        return (
            pool_data is not None
            and pool_data.get("index") is not None
            and pool_data["index"].ntotal > 0
            and len(pool_data.get("id_mapping", [])) > 0
        )

    def get_id_set(self, pool: DiscoveryCandidatePool = DiscoveryCandidatePool.POPULAR_20K) -> Set[str]:
        """Retrieve the exact set of game IDs in the specified candidate pool."""
        pool_data = self._get_or_load_pool(pool)
        if pool_data and "id_set" in pool_data:
            return pool_data["id_set"]
        return set(self.id_mapping)

    def get_id_mapping(self, pool: DiscoveryCandidatePool = DiscoveryCandidatePool.POPULAR_20K) -> List[str]:
        """Retrieve ordered list of game IDs in the specified candidate pool."""
        pool_data = self._get_or_load_pool(pool)
        if pool_data and "id_mapping" in pool_data:
            return pool_data["id_mapping"]
        return self.id_mapping

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 50,
        pool: DiscoveryCandidatePool = DiscoveryCandidatePool.POPULAR_20K,
    ) -> List[Tuple[str, float]]:
        """
        Execute vector similarity search on the specified candidate pool index.
        Returns list of (game_id, score) pairs.
        """
        pool_data = self._get_or_load_pool(pool)
        if not pool_data or pool_data.get("index") is None:
            raise RuntimeError(f"FAISS index for pool {pool.value} is not initialized or empty.")

        index = pool_data["index"]
        id_mapping = pool_data["id_mapping"]

        vec = np.asarray(query_vector, dtype=np.float32)
        if vec.ndim == 1:
            vec = np.expand_dims(vec, axis=0)

        # L2-normalize query vector for cosine similarity
        norm = np.linalg.norm(vec, axis=1, keepdims=True)
        if norm[0, 0] > 0:
            vec = vec / norm

        k = min(top_k, index.ntotal)
        scores, indices = index.search(vec, k)

        results: List[Tuple[str, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(id_mapping):
                game_id = id_mapping[idx]
                results.append((game_id, float(score)))

        return results

    def get_vector(
        self,
        game_id: str,
        pool: DiscoveryCandidatePool = DiscoveryCandidatePool.POPULAR_20K,
    ) -> Optional[np.ndarray]:
        """
        Retrieve precomputed normalized embedding vector for a game in O(1) time.
        """
        pool_data = self._get_or_load_pool(pool)
        if not pool_data or pool_data.get("index") is None:
            return None

        id_to_pos = pool_data.get("id_to_pos", {})
        idx = id_to_pos.get(str(game_id))
        if idx is None:
            return None
        try:
            vec = pool_data["index"].reconstruct(idx)
            return np.asarray(vec, dtype=np.float32)
        except Exception as e:
            logger.debug(f"Failed to reconstruct vector for game_id {game_id}: {e}")
            return None

    def get_vectors(
        self,
        game_ids: List[str],
        pool: DiscoveryCandidatePool = DiscoveryCandidatePool.POPULAR_20K,
    ) -> Dict[str, np.ndarray]:
        """Batch retrieve precomputed vectors for existing games."""
        result: Dict[str, np.ndarray] = {}
        for gid in game_ids:
            v = self.get_vector(gid, pool=pool)
            if v is not None:
                result[str(gid)] = v
        return result


