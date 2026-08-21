import logging
import threading
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer


from app.config import settings

logger = logging.getLogger(__name__)


class QueryEmbedder:
    """Thread-safe singleton query embedding generator using SentenceTransformer."""

    _instance: Optional["QueryEmbedder"] = None
    _lock = threading.Lock()

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", token: Optional[str] = None):
        self.model_name = model_name
        hf_token = token or settings.HF_TOKEN
        logger.info(f"Loading QueryEmbedder model: {model_name} (authenticated={'yes' if hf_token else 'no'})")
        if hf_token:
            self.model = SentenceTransformer(model_name, token=hf_token)
        else:
            self.model = SentenceTransformer(model_name)
        if hasattr(self.model, "get_embedding_dimension"):
            self.dimension = self.model.get_embedding_dimension()
        else:
            self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"QueryEmbedder loaded successfully (dimension={self.dimension})")

    @classmethod
    def get_instance(cls, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> "QueryEmbedder":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(model_name=model_name)
        return cls._instance

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string into a normalized 2D numpy float32 array (1, dim)."""
        clean_q = query.strip()
        if not clean_q:
            raise ValueError("Query string cannot be empty")

        embedding = self.model.encode(
            clean_q,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        vec = np.asarray(embedding, dtype=np.float32)
        if vec.ndim == 1:
            vec = np.expand_dims(vec, axis=0)
        return vec
