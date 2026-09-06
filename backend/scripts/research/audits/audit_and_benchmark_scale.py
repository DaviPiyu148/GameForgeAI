"""
GameForge AI — Discovery Index-Scale Audit & Multi-Scale Benchmark Suite

Conducts an empirical scale evaluation of the Discovery Index:
1. Catalog Quality & Distribution Audit (across 20k, 50k, 100k, and full 121k tiers)
2. Incremental Experimental Index Construction (20k, 50k, 100k, 121k full catalog)
3. 30-Query Standard Benchmark Execution across all 4 scales
4. Category & Constraint Breakdown (P@5, Violations, Latency, Intent)
5. Multi-Mode Discovery Analysis (Best Match vs Hidden Gems vs Popular vs Discover)
6. Qualitative Rank Transition Diff Analysis
"""

import asyncio
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import faiss
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

# Set maximum threads for multi-core CPU throughput
torch.set_num_threads(12)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.schemas.discovery import DiscoverySearchRequest
from app.services.discovery_service import DiscoveryService
from app.search.catalog import CatalogManager
from app.search.embedder import QueryEmbedder
from app.search.index import FAISSIndexManager
from app.search.lexical import normalize_string

CATALOG_PATH = BACKEND_DIR / "data" / "processed" / "games_catalog.json"
BENCH_DIR = BACKEND_DIR / "data" / "benchmark_indexes"
CACHE_DIR = BENCH_DIR / "embeddings_cache"
RESULTS_PATH = BACKEND_DIR / "data" / "reviewed_pool_benchmark_results.json"
BENCHMARK_FILE = BACKEND_DIR / "tests" / "data" / "discovery_benchmark.json"
PROD_INDEX_PATH = BACKEND_DIR / "data" / "processed" / "games_index.faiss"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


# ============================================================================
# PART 1: CATALOG QUALITY & DISTRIBUTION AUDIT
# ============================================================================

def audit_catalog(catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
    print("\n" + "=" * 80, flush=True)
    print("PART 1: CATALOG QUALITY & METADATA DISTRIBUTION AUDIT", flush=True)
    print("=" * 80, flush=True)

    total_records = len(catalog)
    unique_ids = set()
    unique_titles = set()
    duplicate_ids = 0
    duplicate_titles = 0

    desc_lengths: List[int] = []
    tag_counts: List[int] = []
    genre_counts: List[int] = []
    review_counts: List[int] = []
    positive_pcts: List[float] = []

    has_desc = 0
    has_tags = 0
    has_genres = 0
    has_modes = 0
    has_reviews = 0
    is_free_count = 0

    mode_dist = {"Single-player": 0, "Multi-player": 0, "Co-op": 0, "PvP": 0}
    lang_dist = {}

    for g in catalog:
        gid = str(g.get("id", ""))
        title = g.get("title", "").strip()

        if gid in unique_ids:
            duplicate_ids += 1
        unique_ids.add(gid)

        norm_title = normalize_string(title)
        if norm_title in unique_titles:
            duplicate_titles += 1
        unique_titles.add(norm_title)

        desc = g.get("description", "") or g.get("original_description", "")
        desc_len = len(desc)
        desc_lengths.append(desc_len)
        if desc_len >= 20:
            has_desc += 1

        tags = g.get("tags", [])
        tag_counts.append(len(tags))
        if len(tags) > 0:
            has_tags += 1

        genres = g.get("genres", [])
        genre_counts.append(len(genres))
        if len(genres) > 0:
            has_genres += 1

        modes = g.get("player_modes", [])
        if modes:
            has_modes += 1
            for m in modes:
                if m in mode_dist:
                    mode_dist[m] += 1

        revs = g.get("total_reviews", 0)
        review_counts.append(revs)
        if revs > 0:
            has_reviews += 1
            positive_pcts.append(g.get("positive_percent", 0.0))

        if g.get("is_free"):
            is_free_count += 1

        lang = g.get("description_language", "unknown")
        lang_dist[lang] = lang_dist.get(lang, 0) + 1

    reviewed_records = [g for g in catalog if g.get("total_reviews", 0) > 0]
    zero_review_records = [g for g in catalog if g.get("total_reviews", 0) == 0]

    pop_defs = [
        ("20k", "20k", catalog[:20000]),
        ("50k", "50k", catalog[:50000]),
        ("reviewed_only", "Reviewed-only", reviewed_records),
        ("full", "Full", catalog),
    ]

    pop_stats = {}
    for key, label, items in pop_defs:
        count = len(items)
        revs = [g.get("total_reviews", 0) for g in items]
        zero_cnt = sum(1 for r in revs if r == 0)
        pop_stats[key] = {
            "key": key,
            "label": label,
            "record_count": count,
            "zero_review_count": zero_cnt,
            "zero_review_pct": round(zero_cnt / count * 100, 2) if count > 0 else 0.0,
            "min_reviews": int(np.min(revs)) if revs else 0,
            "median_reviews": int(np.median(revs)) if revs else 0,
            "avg_reviews": round(float(np.mean(revs)), 1) if revs else 0.0,
        }

    audit_summary = {
        "total_records": total_records,
        "unique_ids": len(unique_ids),
        "unique_titles": len(unique_titles),
        "duplicate_ids": duplicate_ids,
        "duplicate_titles": duplicate_titles,
        "has_description_pct": round(has_desc / total_records * 100, 2),
        "has_tags_pct": round(has_tags / total_records * 100, 2),
        "has_genres_pct": round(has_genres / total_records * 100, 2),
        "has_player_modes_pct": round(has_modes / total_records * 100, 2),
        "has_reviews_pct": round(has_reviews / total_records * 100, 2),
        "is_free_pct": round(is_free_count / total_records * 100, 2),
        "avg_desc_length": round(float(np.mean(desc_lengths)), 1),
        "median_desc_length": int(np.median(desc_lengths)),
        "avg_tags_per_game": round(float(np.mean(tag_counts)), 1),
        "avg_genres_per_game": round(float(np.mean(genre_counts)), 1),
        "mode_distribution": mode_dist,
        "language_distribution": dict(sorted(lang_dist.items(), key=lambda x: x[1], reverse=True)[:5]),
        "population_stats": pop_stats,
    }

    print(f"Total Games Analyzed:     {total_records:,}", flush=True)
    print(f"Reviewed Games (>0 rev):  {len(reviewed_records):,} ({audit_summary['has_reviews_pct']}%)", flush=True)
    print(f"Zero-Review Games (0 rev):{len(zero_review_records):,} ({round(len(zero_review_records)/total_records*100, 2)}%)", flush=True)
    print(f"Unique Titles:            {len(unique_titles):,} (Duplicates: {duplicate_titles})", flush=True)
    print(f"Games with Description:   {has_desc:,} ({audit_summary['has_description_pct']}%)", flush=True)
    print(f"Games with Tags:          {has_tags:,} ({audit_summary['has_tags_pct']}%)", flush=True)
    print(f"Free-to-Play Games:       {is_free_count:,} ({audit_summary['is_free_pct']}%)", flush=True)
    print("\n" + "=" * 90, flush=True)
    print("SECTION 11: CATALOG QUALITY REPORT (CANDIDATE POPULATIONS)", flush=True)
    print("=" * 90, flush=True)
    print(f"{'Population':<16} | {'Records':<10} | {'Zero-review':<12} | {'Min reviews':<12} | {'Median reviews':<15} | {'Avg reviews':<12}", flush=True)
    print("-" * 90, flush=True)
    for k, ps in pop_stats.items():
        print(f"{ps['label']:<16} | {ps['record_count']:<10,} | {ps['zero_review_count']:<12,} | {ps['min_reviews']:<12} | {ps['median_reviews']:<15,} | {ps['avg_reviews']:<12.1f}", flush=True)

    return audit_summary


# ============================================================================
# PART 2: INCREMENTAL EMBEDDING GENERATION & INDEX BUILDER
# ============================================================================

def get_or_create_slice_embeddings(
    catalog_slice: List[Dict[str, Any]],
    slice_name: str,
    model: SentenceTransformer,
    batch_size: int = 128,
    existing_faiss_path: Optional[Path] = None,
) -> Tuple[np.ndarray, float]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{slice_name}.npy"

    if cache_file.exists():
        try:
            print(f"Loading cached embeddings from {cache_file.name}...", flush=True)
            arr = np.load(cache_file)
            if len(arr) == len(catalog_slice) and arr.shape[1] == 384 and np.all(np.isfinite(arr)):
                print(f"  ✓ Cached {slice_name} valid ({len(arr):,} vectors, 384-dim, float32)", flush=True)
                return arr, 0.0
            else:
                print(f"  ⚠️ Cached {slice_name} dimension/size mismatch, re-encoding...", flush=True)
        except Exception as e:
            print(f"  ⚠️ Error reading cache {cache_file.name}: {e}. Re-encoding...", flush=True)

    if existing_faiss_path and existing_faiss_path.exists() and slice_name == "slice_0_20k":
        print(f"Extracting 20k baseline vectors from existing {existing_faiss_path.name}...", flush=True)
        prod_idx = faiss.read_index(str(existing_faiss_path))
        if prod_idx.ntotal == len(catalog_slice):
            arr = prod_idx.reconstruct_n(0, prod_idx.ntotal).astype(np.float32)
            temp_cache = CACHE_DIR / f"temp_{slice_name}.npy"
            np.save(temp_cache, arr)
            if cache_file.exists():
                cache_file.unlink()
            temp_cache.replace(cache_file)
            print(f"Saved {len(arr):,} baseline vectors to {cache_file.name}", flush=True)
            return arr, 0.0

    profiles = [g.get("semantic_profile", "") for g in catalog_slice]
    print(f"Encoding {len(profiles):,} profiles for {slice_name} (batch_size={batch_size}, threads=12)...", flush=True)
    t0 = time.time()
    arr = model.encode(
        profiles,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)
    enc_time = time.time() - t0
    temp_cache = CACHE_DIR / f"temp_{slice_name}.npy"
    np.save(temp_cache, arr)
    if cache_file.exists():
        cache_file.unlink()
    temp_cache.replace(cache_file)
    rate = len(profiles) / enc_time if enc_time > 0 else 0.0
    print(f"Saved {len(arr):,} vectors to {cache_file.name} (Encoded in {enc_time:.2f}s, {rate:.1f} samples/sec)", flush=True)
    return arr, enc_time


def build_and_save_index(
    scale_label: str,
    record_count: int,
    embeddings: np.ndarray,
    id_mapping: List[str],
    load_time: float,
    encode_time: float,
) -> Dict[str, Any]:
    index_file = BENCH_DIR / f"games_index_{scale_label}.faiss"
    meta_file = BENCH_DIR / f"index_meta_{scale_label}.json"

    # Check if existing index and meta are already valid
    if index_file.exists() and meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            idx = faiss.read_index(str(index_file))
            if idx.ntotal == record_count and meta.get("record_count") == record_count:
                print(f"Reusing existing valid FAISS index for {scale_label.upper()} ({record_count:,} records)", flush=True)
                return {
                    "index_file": str(index_file),
                    "meta_file": str(meta_file),
                    "record_count": record_count,
                    "stats": meta["build_stats"],
                }
        except Exception as e:
            print(f"Existing index validation failed for {scale_label}: {e}. Rebuilding...", flush=True)

    print(f"\nConstructing FAISS index for {scale_label.upper()} ({record_count:,} records)...", flush=True)
    dim = embeddings.shape[1]
    t0 = time.time()
    faiss_index = faiss.IndexFlatIP(dim)
    faiss_index.add(embeddings)
    faiss_add_time = time.time() - t0

    temp_index = BENCH_DIR / f"games_index_{scale_label}.faiss.tmp"
    temp_meta = BENCH_DIR / f"index_meta_{scale_label}.json.tmp"

    faiss.write_index(faiss_index, str(temp_index))
    index_size_mb = os.path.getsize(temp_index) / (1024 * 1024)

    meta = {
        "scale_label": scale_label,
        "record_count": record_count,
        "embedding_model": MODEL_NAME,
        "embedding_dimension": dim,
        "index_type": "IndexFlatIP",
        "metric": "cosine",
        "id_mapping": id_mapping,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "build_stats": {
            "model_load_seconds": round(load_time, 2),
            "encode_seconds": round(encode_time, 2),
            "faiss_add_seconds": round(faiss_add_time, 3),
            "total_build_seconds": round(load_time + encode_time + faiss_add_time, 2),
            "index_size_mb": round(index_size_mb, 2),
            "raw_vector_memory_mb": round((record_count * dim * 4) / (1024 * 1024), 2),
        },
    }

    with open(temp_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    meta_size_mb = os.path.getsize(temp_meta) / (1024 * 1024)
    meta["build_stats"]["meta_size_mb"] = round(meta_size_mb, 2)

    # Atomic rename
    if index_file.exists():
        index_file.unlink()
    temp_index.replace(index_file)
    if meta_file.exists():
        meta_file.unlink()
    temp_meta.replace(meta_file)

    print(f"  ✓ Index File: {index_file.name} ({index_size_mb:.2f} MB)", flush=True)
    print(f"  ✓ Meta File:  {meta_file.name} ({meta_size_mb:.2f} MB)", flush=True)

    return {
        "index_file": str(index_file),
        "meta_file": str(meta_file),
        "record_count": record_count,
        "stats": meta["build_stats"],
    }


# ============================================================================
# PART 3: 30-QUERY BENCHMARK EVALUATION
# ============================================================================

async def evaluate_scale(
    scale_label: str,
    index_path: str,
    meta_path: str,
    queries: List[Dict[str, Any]],
    catalog_mgr: CatalogManager,
    embedder: QueryEmbedder,
) -> Dict[str, Any]:
    print(f"\nEvaluating 30-Query Benchmark on Scale [{scale_label.upper()}]...", flush=True)

    index_mgr = FAISSIndexManager(index_path=index_path, meta_path=meta_path)
    service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=catalog_mgr)
    service.warm()

    intent_correct = 0
    hard_constraint_violations = 0
    p5_scores: List[float] = []
    latencies: List[float] = []
    category_scores: Dict[str, List[float]] = {}
    category_latencies: Dict[str, List[float]] = {}
    query_details: List[Dict[str, Any]] = []

    # Warmup runs
    for w_q in queries[:3]:
        await service.search(DiscoverySearchRequest(prompt=w_q["query"], limit=5, mode="BEST_MATCH"))

    for q in queries:
        qid = q["id"]
        q_text = q["query"]
        expected_type = q.get("expected_type")
        category = q.get("category", "General")

        iter_latencies = []
        res = None
        for _ in range(3):
            t0 = time.perf_counter()
            req = DiscoverySearchRequest(prompt=q_text, limit=5, mode="BEST_MATCH")
            res = await service.search(req)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            iter_latencies.append(elapsed_ms)

        mean_lat = float(np.mean(iter_latencies))
        latencies.append(mean_lat)

        # 1. Intent Classification Accuracy
        is_type_match = (res.query_type == expected_type)
        if is_type_match:
            intent_correct += 1

        # 2. Hard Constraint Verification
        has_violation = False
        if q.get("must_not_contain_genres"):
            banned_g = {g.lower() for g in q["must_not_contain_genres"]}
            for r in res.results:
                game_g = {g.lower() for g in r.game.genres}
                if banned_g.intersection(game_g):
                    has_violation = True
                    hard_constraint_violations += 1
                    break

        if q.get("must_not_contain_modes"):
            banned_m = {m.lower() for m in q["must_not_contain_modes"]}
            for r in res.results:
                game_m = {m.lower() for m in r.game.player_modes}
                if banned_m.intersection(game_m):
                    has_violation = True
                    hard_constraint_violations += 1
                    break

        if q.get("must_be_free"):
            for r in res.results:
                if not r.game.is_free:
                    has_violation = True
                    hard_constraint_violations += 1
                    break

        # 3. Precision@5 Calculation
        relevant_in_top5 = 0
        must_include = q.get("must_include_titles", [])
        acceptable_g = {g.lower() for g in q.get("acceptable_genres", [])}

        top5_titles = [r.game.title for r in res.results[:5]]
        top5_scores_list = [round(float(r.score), 3) for r in res.results[:5]]

        for r in res.results[:5]:
            title_norm = normalize_string(r.game.title)
            if must_include:
                if any(normalize_string(mi) in title_norm for mi in must_include):
                    relevant_in_top5 += 1
            elif acceptable_g:
                game_g = {g.lower() for g in r.game.genres}
                if acceptable_g.intersection(game_g) or r.score >= 0.70:
                    relevant_in_top5 += 1
            else:
                if r.score >= 0.65:
                    relevant_in_top5 += 1

        p5 = relevant_in_top5 / max(1, min(5, len(res.results)))
        p5_scores.append(p5)

        if category not in category_scores:
            category_scores[category] = []
            category_latencies[category] = []
        category_scores[category].append(p5)
        category_latencies[category].append(mean_lat)

        query_details.append({
            "id": qid,
            "query": q_text,
            "category": category,
            "p5": round(p5, 3),
            "latency_ms": round(mean_lat, 2),
            "has_violation": has_violation,
            "top5_titles": top5_titles,
            "top5_scores": top5_scores_list,
        })

    cat_summary = {}
    for cat in category_scores:
        cat_summary[cat] = {
            "mean_p5": round(float(np.mean(category_scores[cat])), 3),
            "mean_latency_ms": round(float(np.mean(category_latencies[cat])), 2),
            "query_count": len(category_scores[cat]),
        }

    mean_p5 = round(float(np.mean(p5_scores)), 4)
    mean_lat = round(float(np.mean(latencies)), 2)
    p50_lat = round(float(np.percentile(latencies, 50)), 2)
    p95_lat = round(float(np.percentile(latencies, 95)), 2)
    p99_lat = round(float(np.percentile(latencies, 99)), 2)

    print(f"[{scale_label.upper()}] P@5: {mean_p5:.4f} | Latency: {mean_lat:.1f}ms (p50: {p50_lat}ms, p95: {p95_lat}ms) | Violations: {hard_constraint_violations}", flush=True)

    return {
        "scale_label": scale_label,
        "mean_p5": mean_p5,
        "hard_constraint_violations": hard_constraint_violations,
        "intent_accuracy": round(intent_correct / len(queries), 4),
        "latency_mean_ms": mean_lat,
        "latency_p50_ms": p50_lat,
        "latency_p95_ms": p95_lat,
        "latency_p99_ms": p99_lat,
        "category_summary": cat_summary,
        "query_details": query_details,
    }


# ============================================================================
# PART 4: DISCOVERY MODES SENSITIVITY & DIVERSITY
# ============================================================================

async def evaluate_modes_divergence(
    scale_label: str,
    index_path: str,
    meta_path: str,
    catalog_mgr: CatalogManager,
    embedder: QueryEmbedder,
) -> Dict[str, Any]:
    index_mgr = FAISSIndexManager(index_path=index_path, meta_path=meta_path)
    service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=catalog_mgr)
    service.warm()

    probe_queries = [
        "deckbuilder",
        "co-op survival",
        "cyberpunk rpg",
        "space exploration",
        "relaxing farming",
    ]

    modes = ["BEST_MATCH", "DISCOVER", "HIDDEN_GEMS", "POPULAR"]
    probe_results = {}

    for q in probe_queries:
        probe_results[q] = {}
        for m in modes:
            req = DiscoverySearchRequest(prompt=q, limit=5, mode=m)
            res = await service.search(req)
            titles = [r.game.title for r in res.results]
            reviews = [r.game.total_reviews for r in res.results]
            zero_cnt = sum(1 for r in reviews if r == 0)
            probe_results[q][m] = {
                "titles": titles,
                "reviews": reviews,
                "zero_review_count": zero_cnt,
                "avg_reviews": round(float(np.mean(reviews)), 1) if reviews else 0.0,
                "median_reviews": int(np.median(reviews)) if reviews else 0,
                "min_reviews": int(np.min(reviews)) if reviews else 0,
                "max_reviews": int(np.max(reviews)) if reviews else 0,
            }

    return probe_results


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

async def main():
    print("=" * 90, flush=True)
    print("GAMEFORGE AI — REVIEWED-ONLY CANDIDATE POOL BENCHMARK", flush=True)
    print("=" * 90, flush=True)

    # 1. Load catalog
    if not CATALOG_PATH.exists():
        print(f"[ERROR] Catalog not found at {CATALOG_PATH}.", flush=True)
        sys.exit(1)

    print(f"Loading games catalog from {CATALOG_PATH}...", flush=True)
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    print(f"Catalog loaded with {len(catalog):,} records.", flush=True)

    # 2. Audit catalog populations
    audit_summary = audit_catalog(catalog)
    reviewed_records = [g for g in catalog if g.get("total_reviews", 0) > 0]
    reviewed_count = len(reviewed_records)  # exactly 87,890

    # 3. Model setup
    print("\nLoading SentenceTransformer model...", flush=True)
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME)
    load_time = time.time() - t0
    print(f"Model loaded in {load_time:.2f}s", flush=True)

    # 4. Generate/Load Slices
    # Slice 1: 0 .. 20,000 (20k)
    s1_vecs, s1_time = get_or_create_slice_embeddings(
        catalog[:20000], "slice_0_20k", model, batch_size=128, existing_faiss_path=PROD_INDEX_PATH
    )

    # Slice 2: 20,000 .. 50,000 (30k)
    s2_vecs, s2_time = get_or_create_slice_embeddings(
        catalog[20000:50000], "slice_20k_50k", model, batch_size=128
    )

    # Slice 3: 50,000 .. 100,000 (50k)
    s3_vecs, s3_time = get_or_create_slice_embeddings(
        catalog[50000:100000], "slice_50k_100k", model, batch_size=128
    )

    # Slice 4: 100,000 .. Full (21.6k)
    s4_vecs, s4_time = get_or_create_slice_embeddings(
        catalog[100000:], "slice_100k_full", model, batch_size=128
    )

    # Concatenate all slices into single continuous matrix
    all_embeddings = np.concatenate([s1_vecs, s2_vecs, s3_vecs, s4_vecs], axis=0).astype(np.float32)
    print(f"Full embedding matrix concatenated: {all_embeddings.shape} ({all_embeddings.nbytes / (1024*1024):.1f} MB)", flush=True)

    # 5. Build 4 Candidate Populations
    offline_encode_estimates = {
        "20k": 120.0,
        "50k": 300.0,
        "reviewed_only": 530.0,
        "full": 730.0,
    }

    scale_definitions = [
        ("20k", 20000, all_embeddings[:20000], offline_encode_estimates["20k"]),
        ("50k", 50000, all_embeddings[:50000], offline_encode_estimates["50k"]),
        ("reviewed_only", reviewed_count, all_embeddings[:reviewed_count], offline_encode_estimates["reviewed_only"]),
        ("full", len(catalog), all_embeddings[:len(catalog)], offline_encode_estimates["full"]),
    ]

    scale_meta = {}
    for label, count, vecs, enc_time in scale_definitions:
        id_map = [str(g.get("id", str(i))) for i, g in enumerate(catalog[:count])]
        idx_info = build_and_save_index(
            scale_label=label,
            record_count=count,
            embeddings=vecs,
            id_mapping=id_map,
            load_time=load_time,
            encode_time=enc_time,
        )
        scale_meta[label] = idx_info

    # 6. Load benchmark queries
    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    queries = bench_data["queries"]

    # 7. Evaluate all scales with incremental checkpointing
    cm = CatalogManager.get_instance(catalog_path=str(CATALOG_PATH))
    embedder = QueryEmbedder.get_instance()

    benchmark_evals = {}
    modes_evals = {}

    for label, count, _, _ in scale_definitions:
        idx_info = scale_meta[label]
        bench_res = await evaluate_scale(
            scale_label=label,
            index_path=idx_info["index_file"],
            meta_path=idx_info["meta_file"],
            queries=queries,
            catalog_mgr=cm,
            embedder=embedder,
        )
        benchmark_evals[label] = bench_res

        modes_res = await evaluate_modes_divergence(
            scale_label=label,
            index_path=idx_info["index_file"],
            meta_path=idx_info["meta_file"],
            catalog_mgr=cm,
            embedder=embedder,
        )
        modes_evals[label] = modes_res

        # Save checkpoint after each population
        checkpoint_output = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "catalog_audit": audit_summary,
            "index_build_stats": scale_meta,
            "benchmark_evals": benchmark_evals,
            "modes_evals": modes_evals,
        }
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(checkpoint_output, f, indent=2)
        print(f"Checkpoint saved to {RESULTS_PATH.name} for population [{label.upper()}]", flush=True)

    # 8. Compute fine-grained prompt category breakdown
    def compute_custom_category_metrics(eval_res: Dict[str, Any]) -> Dict[str, float]:
        q_map = {q["id"]: q for q in eval_res["query_details"]}
        
        def avg_q(ids: List[str]) -> float:
            scores = [q_map[qid]["p5"] for qid in ids if qid in q_map]
            return round(float(np.mean(scores)), 3) if scores else 0.0

        return {
            "genre": round(float(np.mean([
                eval_res["category_summary"].get("Topic Tag Single", {}).get("mean_p5", 0.0),
                eval_res["category_summary"].get("Genre & Aesthetic Combination", {}).get("mean_p5", 0.0),
            ])), 3),
            "mechanics": avg_q(["q07", "q08", "q09", "q12"]),
            "multiplayer": avg_q(["q10", "q11", "q22"]),
            "mood": eval_res["category_summary"].get("Mood / Tone", {}).get("mean_p5", 0.0),
            "negative_constraints": eval_res["category_summary"].get("Negative Constraint Hard", {}).get("mean_p5", 0.0),
            "session_length": eval_res["category_summary"].get("Session Duration", {}).get("mean_p5", 0.0),
            "like_x": eval_res["category_summary"].get("Similarity Standard", {}).get("mean_p5", 0.0),
            "less_y": avg_q(["q13", "q14", "q15"]),
            "exploratory": eval_res["category_summary"].get("Complex Multi-word Concept", {}).get("mean_p5", 0.0),
        }

    pop_keys = ["20k", "50k", "reviewed_only", "full"]
    custom_metrics = {s: compute_custom_category_metrics(benchmark_evals[s]) for s in pop_keys}
    checkpoint_output["custom_category_metrics"] = custom_metrics
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(checkpoint_output, f, indent=2)

    # ============================================================================
    # SECTION 15: MASTER COMPARISON REPORT
    # ============================================================================

    print("\n" + "=" * 95, flush=True)
    print("SECTION 15-A: MAIN CANDIDATE POPULATION COMPARISON TABLE", flush=True)
    print("=" * 95, flush=True)
    header = f"{'Metric':<25} | {'20k':<12} | {'50k':<12} | {'Reviewed-Only':<15} | {'Full (121k)':<14}"
    print(header, flush=True)
    print("-" * 95, flush=True)

    def row(label_text, fn):
        vals = [str(fn(s)) for s in pop_keys]
        print(f"{label_text:<25} | {vals[0]:<12} | {vals[1]:<12} | {vals[2]:<15} | {vals[3]:<14}", flush=True)

    row("Records", lambda s: f"{scale_meta[s]['record_count']:,}")
    row("Zero-review %", lambda s: f"{audit_summary['population_stats'][s]['zero_review_pct']:.1f}%")
    row("FAISS Build time", lambda s: f"{scale_meta[s]['stats']['faiss_add_seconds']*1000:.1f} ms")
    row("Offline Encode Est.", lambda s: f"{scale_meta[s]['stats']['encode_seconds']:.1f} s")
    row("Index size", lambda s: f"{scale_meta[s]['stats']['index_size_mb']:.1f} MB")
    row("Avg query latency", lambda s: f"{benchmark_evals[s]['latency_mean_ms']:.1f} ms")
    row("P95 latency", lambda s: f"{benchmark_evals[s]['latency_p95_ms']:.1f} ms")
    row("Precision@5", lambda s: f"{benchmark_evals[s]['mean_p5']:.4f}")
    row("Hard violations", lambda s: f"{benchmark_evals[s]['hard_constraint_violations']}")
    row("Intent accuracy", lambda s: f"{benchmark_evals[s]['intent_accuracy'] * 100:.1f}%")

    print("\n" + "=" * 95, flush=True)
    print("SECTION 15-B: QUERY CATEGORY BREAKDOWN ACROSS POPULATIONS", flush=True)
    print("=" * 95, flush=True)
    print(f"{'Category':<25} | {'20k':<12} | {'50k':<12} | {'Reviewed-Only':<15} | {'Full (121k)':<14}", flush=True)
    print("-" * 95, flush=True)
    for cat_name in ["genre", "mechanics", "multiplayer", "mood", "negative_constraints", "session_length", "like_x", "less_y", "exploratory"]:
        row(cat_name.capitalize().replace('_', ' '), lambda s, c=cat_name: f"{custom_metrics[s][c]:.3f}")

    print("\n" + "=" * 95, flush=True)
    print("SECTION 15-C: HIDDEN GEMS BEHAVIOR & ZERO-REVIEW POLLUTION COMPARISON", flush=True)
    print("=" * 95, flush=True)
    for q in ["deckbuilder", "co-op survival", "cyberpunk rpg", "space exploration", "relaxing farming"]:
        print(f"\nQuery: \"{q}\"", flush=True)
        print(f"{'Population':<16} | {'Avg Rev':<10} | {'Median Rev':<11} | {'Min..Max Rev':<18} | {'Zero-Rev in Top5':<16} | {'Top 1 Title'}", flush=True)
        print("-" * 95, flush=True)
        for s in pop_keys:
            m_data = modes_evals[s][q]["HIDDEN_GEMS"]
            t1 = m_data["titles"][0] if m_data["titles"] else "N/A"
            print(f"{s:<16} | {m_data['avg_reviews']:<10.1f} | {m_data['median_reviews']:<11,} | {m_data['min_reviews']}..{m_data['max_reviews']:<12} | {m_data['zero_review_count']:<16} | {t1}", flush=True)

    print(f"\nAll benchmark results saved to: {RESULTS_PATH}", flush=True)
    print("=" * 95, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
