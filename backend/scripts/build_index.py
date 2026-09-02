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
    reviewed_only: bool = False,
) -> Dict[str, Any]:
    """
    Build FAISS IndexFlatIP index over normalized catalog semantic profiles.
    """
    if reviewed_only:
        if index_path == DEFAULT_INDEX_PATH:
            index_path = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "games_index_reviewed_only.faiss")
        if meta_path == DEFAULT_META_PATH:
            meta_path = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "index_meta_reviewed_only.json")

    if not os.path.exists(catalog_path) and os.path.exists("backend/data/processed/games_catalog.json"):
        catalog_path = "backend/data/processed/games_catalog.json"
        if not reviewed_only:
            index_path = "backend/data/processed/games_index.faiss"
            meta_path = "backend/data/processed/index_meta.json"
        else:
            index_path = "backend/data/processed/games_index_reviewed_only.faiss"
            meta_path = "backend/data/processed/index_meta_reviewed_only.json"

    start_time = time.time()
    print("=" * 60)
    mode_label = "Reviewed-Only (total_reviews > 0)" if reviewed_only else f"Top {max_records}"
    print(f"Building FAISS Index ({mode_label}) using {model_name}...")
    print("=" * 60)

    if not os.path.exists(catalog_path):
        raise FileNotFoundError(f"Catalog file not found at {catalog_path}. Run ingest_catalog.py first.")

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog: List[Dict[str, Any]] = json.load(f)

    if reviewed_only:
        print("Filtering catalog to reviewed games only (total_reviews > 0)...")
        catalog = [g for g in catalog if g.get("total_reviews", 0) > 0]
    elif max_records and max_records > 0 and len(catalog) > max_records:
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

    # 4. Save Index and Metadata atomically to prevent corruption from interrupted builds
    import hashlib
    def get_catalog_fingerprint(cat_path: str) -> str:
        try:
            size = os.path.getsize(cat_path)
            hasher = hashlib.sha256()
            hasher.update(str(size).encode("utf-8"))
            with open(cat_path, "rb") as f:
                hasher.update(f.read(8192))
                if size > 16384:
                    f.seek(size - 8192)
                    hasher.update(f.read(8192))
            return hasher.hexdigest()
        except Exception:
            return ""

    catalog_fp = get_catalog_fingerprint(catalog_path)
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    temp_index_path = f"{index_path}.tmp"
    temp_meta_path = f"{meta_path}.tmp"

    faiss.write_index(index, temp_index_path)
    index_file_size_mb = os.path.getsize(temp_index_path) / (1024 * 1024)

    meta = {
        "catalog_version": "1.0.0",
        "embedding_model": model_name,
        "embedding_dimension": dim,
        "index_type": "IndexFlatIP",
        "metric": "cosine",
        "normalized": True,
        "record_count": total_records,
        "catalog_fingerprint": catalog_fp,
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

    with open(temp_meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    # Atomic replace
    if os.path.exists(index_path):
        os.remove(index_path)
    os.replace(temp_index_path, index_path)

    if os.path.exists(meta_path):
        os.remove(meta_path)
    os.replace(temp_meta_path, meta_path)

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
    parser.add_argument("--reviewed-only", action="store_true", help="Build index over all reviewed games (total_reviews > 0)")
    parser.add_argument("--index-path", type=str, default=DEFAULT_INDEX_PATH, help="Output path for FAISS index")
    parser.add_argument("--meta-path", type=str, default=DEFAULT_META_PATH, help="Output path for metadata JSON")
    args = parser.parse_args()

    build_index(
        max_records=args.max_records,
        batch_size=args.batch_size,
        reviewed_only=args.reviewed_only,
        index_path=args.index_path,
        meta_path=args.meta_path,
    )
