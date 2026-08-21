import argparse
import datetime
import json
import os
import time
from typing import Any, Dict, List

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "games_catalog.json")
DEFAULT_INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "games_index.faiss")
DEFAULT_META_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "index_meta.json")


def build_index(
    catalog_path: str = DEFAULT_CATALOG_PATH,
    index_path: str = DEFAULT_INDEX_PATH,
    meta_path: str = DEFAULT_META_PATH,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    max_records: int = 20000,
    batch_size: int = 128,
) -> Dict[str, Any]:
    """
    Build FAISS IndexFlatIP index over normalized catalog semantic profiles.
    """
    if not os.path.exists(catalog_path) and os.path.exists("backend/data/processed/games_catalog.json"):
        catalog_path = "backend/data/processed/games_catalog.json"
        index_path = "backend/data/processed/games_index.faiss"
        meta_path = "backend/data/processed/index_meta.json"

    start_time = time.time()
    print("=" * 60)
    print(f"Building FAISS Index using {model_name}...")
    print("=" * 60)

    if not os.path.exists(catalog_path):
        raise FileNotFoundError(f"Catalog file not found at {catalog_path}. Run ingest_catalog.py first.")

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog: List[Dict[str, Any]] = json.load(f)

    if max_records and max_records > 0 and len(catalog) > max_records:
        print(f"Subsetting catalog to top {max_records} games by popularity/relevance...")
        catalog = catalog[:max_records]

    total_records = len(catalog)
    print(f"Total records to index: {total_records}")

    profiles = [g.get("semantic_profile", "") for g in catalog]
    id_mapping = [g.get("id", str(i)) for i, g in enumerate(catalog)]

    # 1. Load Embedding Model
    print(f"Loading SentenceTransformer: {model_name}...")
    t_model_load = time.time()
    model = SentenceTransformer(model_name)
    model_load_time = time.time() - t_model_load
    print(f"Model loaded in {model_load_time:.2f}s")

    # 2. Generate Normalized Embeddings
    print(f"Encoding {total_records} profiles with batch_size={batch_size}...")
    t_encode = time.time()
    embeddings = model.encode(
        profiles,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    encode_time = time.time() - t_encode
    rate = total_records / encode_time if encode_time > 0 else 0.0
    print(f"Encoding complete in {encode_time:.2f}s ({rate:.1f} samples/sec)")

    embeddings = embeddings.astype(np.float32)
    dim = embeddings.shape[1]

    # 3. Build FAISS IndexFlatIP (Inner Product == Cosine Similarity for L2-normalized vectors)
    print(f"Creating FAISS IndexFlatIP(dim={dim})...")
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    print(f"FAISS index populated: {index.ntotal} vectors")

    # 4. Save Index and Metadata
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    faiss.write_index(index, index_path)
    index_file_size_mb = os.path.getsize(index_path) / (1024 * 1024)

    meta = {
        "catalog_version": "1.0.0",
        "embedding_model": model_name,
        "embedding_dimension": dim,
        "index_type": "IndexFlatIP",
        "metric": "cosine",
        "normalized": True,
        "record_count": total_records,
        "id_mapping": id_mapping,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "build_stats": {
            "model_load_seconds": round(model_load_time, 2),
            "encode_seconds": round(encode_time, 2),
            "total_seconds": round(time.time() - start_time, 2),
            "samples_per_sec": round(rate, 1),
            "index_size_mb": round(index_file_size_mb, 2),
        },
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    total_time = time.time() - start_time
    print("=" * 60)
    print(f"Index successfully built in {total_time:.2f}s!")
    print(f"Index File:   {index_path} ({index_file_size_mb:.2f} MB)")
    print(f"Meta File:    {meta_path}")
    print("=" * 60)

    return meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build FAISS Vector Index for GameForge AI")
    parser.add_argument("--max-records", type=int, default=20000, help="Max records to index (0 for all)")
    parser.add_argument("--batch-size", type=int, default=128, help="Encoding batch size")
    args = parser.parse_args()

    build_index(max_records=args.max_records, batch_size=args.batch_size)
