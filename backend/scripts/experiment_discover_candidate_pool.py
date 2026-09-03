"""
GameForge Discovery V2.4 — DISCOVER Candidate-Pool Experiment Runner
Evaluates DISCOVER mode under Condition A (POPULAR_20K) vs Condition B (REVIEWED_ONLY_87,890).
"""
import asyncio
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.discovery import DiscoverySearchRequest, DiscoverySearchResult
from app.search.candidate_pool import DiscoveryCandidatePool
from app.search.catalog import CatalogManager
from app.search.embedder import QueryEmbedder
from app.search.index import FAISSIndexManager
from app.search.lexical import normalize_string
from app.search.query_parser import QueryParser
from app.search.ranker import Ranker
from app.search.ranking_config import (
    DEFAULT_QUALITY_REVIEW_THRESHOLD,
    DISCOVERY_MODES,
    RRF_K,
    DIRECT_SCORE_WEIGHT,
    RRF_SCORE_WEIGHT,
    MAX_STEAM_REVIEWS_LOG,
    QUALITY_WEIGHT,
    NOVELTY_WEIGHT,
    HIDDEN_GEM_MIN_REVIEWS,
)
from app.services.discovery_service import DiscoveryService

CATALOG_PATH = BACKEND_DIR / "data" / "processed" / "games_catalog.json"
STD_BENCHMARK_PATH = BACKEND_DIR / "tests" / "data" / "discovery_benchmark.json"
DISC_BENCHMARK_PATH = BACKEND_DIR / "tests" / "data" / "discover_exploratory_benchmark.json"
OUTPUT_RESULTS_PATH = BACKEND_DIR / "data" / "discover_experiment_results.json"


def load_twenty_k_ids(catalog_mgr: CatalogManager) -> Set[str]:
    cat = catalog_mgr.get_all_games()
    sorted_cat = sorted(cat, key=lambda g: g.get("total_reviews", 0), reverse=True)
    return {str(g["id"]) for g in sorted_cat[:20000]}


def evaluate_precision(query_spec: Dict[str, Any], results: List[DiscoverySearchResult]) -> Tuple[float, bool]:
    must_include = query_spec.get("must_include_titles", [])
    acceptable_genres = {g.lower() for g in query_spec.get("acceptable_genres", [])}
    acceptable_tags = {t.lower() for t in query_spec.get("acceptable_tags", [])}
    hard_neg_terms = [t.lower() for t in query_spec.get("hard_negative_terms", [])]
    banned_genres = {g.lower() for g in query_spec.get("must_not_contain_genres", [])}
    banned_modes = {m.lower() for m in query_spec.get("must_not_contain_modes", [])}

    has_violation = False
    for r in results:
        g_genres = {g.lower() for g in r.game.genres}
        g_modes = {m.lower() for m in r.game.player_modes}
        g_tags = {t.lower() for t in r.game.tags}
        g_title_lower = r.game.title.lower()

        if banned_genres and banned_genres.intersection(g_genres):
            has_violation = True
        if banned_modes and banned_modes.intersection(g_modes):
            has_violation = True
        if query_spec.get("must_be_free") and not r.game.is_free:
            has_violation = True
        if hard_neg_terms:
            for term in hard_neg_terms:
                if term in g_title_lower or term in g_tags:
                    has_violation = True

    relevant_count = 0
    top5 = results[:5]
    for r in top5:
        t_norm = normalize_string(r.game.title)
        g_genres = {g.lower() for g in r.game.genres}
        g_tags = {t.lower() for t in r.game.tags}

        if must_include:
            if any(normalize_string(mi) in t_norm for mi in must_include):
                relevant_count += 1
        elif acceptable_genres or acceptable_tags:
            match_genre = bool(acceptable_genres.intersection(g_genres))
            match_tag = bool(acceptable_tags.intersection(g_tags))
            if match_genre or match_tag or r.score >= 0.70:
                relevant_count += 1
        else:
            if r.score >= 0.65:
                relevant_count += 1

    p5 = relevant_count / max(1, min(5, len(results)))
    return p5, has_violation


async def run_detailed_pipeline(
    query_text: str,
    pool: DiscoveryCandidatePool,
    service: DiscoveryService,
    catalog_mgr: CatalogManager,
    mode: str = "DISCOVER",
) -> Dict[str, Any]:
    top_k = 50
    t_start = time.perf_counter()

    # 1. Intent Parsing
    t0 = time.perf_counter()
    parsed_query = service.query_parser.parse(query_text)
    t_parse = time.perf_counter() - t0

    # 2. Dense FAISS
    t0 = time.perf_counter()
    dense_candidates = []
    dense_gids = []
    if parsed_query.query_type == "SIMILARITY" and parsed_query.target_game:
        embed_text = parsed_query.target_game.get("semantic_profile") or parsed_query.target_game.get("title")
    else:
        embed_text = parsed_query.clean_search_query or query_text

    q_vec = service.embedder.embed_query(embed_text)
    t_embed = time.perf_counter() - t0

    t0 = time.perf_counter()
    raw_dense = service.index_manager.search(q_vec, top_k=top_k, pool=pool)
    for gid, score in raw_dense:
        g = catalog_mgr.get_game(gid)
        if g:
            dense_candidates.append((g, float(score)))
            dense_gids.append(gid)
    t_dense = time.perf_counter() - t0

    # 3. Lexical
    t0 = time.perf_counter()
    raw_lex = service.lexical_index.search_lexical(
        query=parsed_query.clean_search_query or query_text,
        limit=top_k,
        query_type=parsed_query.query_type,
        candidate_pool=pool,
    )
    lex_gids = [str(g.get("id")) for g, _, _ in raw_lex]
    t_lex = time.perf_counter() - t0

    # 4. RRF
    t0 = time.perf_counter()
    rrf_scores: Dict[str, float] = {}
    candidate_map: Dict[str, Dict[str, Any]] = {}
    k_const = 60.0

    for rank, (game, _) in enumerate(dense_candidates):
        gid = str(game.get("id"))
        rrf_scores[gid] = rrf_scores.get(gid, 0.0) + (1.0 / (k_const + rank + 1))
        candidate_map[gid] = game

    for rank, (game, _, _) in enumerate(raw_lex):
        gid = str(game.get("id"))
        rrf_scores[gid] = rrf_scores.get(gid, 0.0) + (1.0 / (k_const + rank + 1))
        candidate_map[gid] = game

    sorted_rrf = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    rrf_gids = [gid for gid, _ in sorted_rrf]
    t_rrf = time.perf_counter() - t0

    # 5. Full Search via DiscoveryService
    t0 = time.perf_counter()
    req = DiscoverySearchRequest(prompt=query_text, limit=50, mode=mode)
    full_res = await service.search(req, candidate_pool_override=pool)
    t_rank = time.perf_counter() - t0
    t_total = time.perf_counter() - t_start

    top20_gids = [str(r.game.id) for r in full_res.results[:20]]
    top5_gids = [str(r.game.id) for r in full_res.results[:5]]

    return {
        "query": query_text,
        "query_type": full_res.query_type,
        "target_entity": parsed_query.target_entity,
        "dense_gids": dense_gids,
        "lex_gids": lex_gids,
        "rrf_gids": rrf_gids,
        "top20_gids": top20_gids,
        "top5_gids": top5_gids,
        "results": full_res.results,
        "timings_ms": {
            "parse": round(t_parse * 1000.0, 2),
            "embed": round(t_embed * 1000.0, 2),
            "dense": round(t_dense * 1000.0, 2),
            "lex": round(t_lex * 1000.0, 2),
            "rrf": round(t_rrf * 1000.0, 2),
            "rank": round(t_rank * 1000.0, 2),
            "total": round(t_total * 1000.0, 2),
        },
    }


def compute_diversity_metrics(results: List[DiscoverySearchResult]) -> Dict[str, float]:
    top5 = results[:5]
    if not top5:
        return {"genre_div": 0.0, "tag_div": 0.0, "franchise_div": 0.0}

    all_genres: Set[str] = set()
    all_tags: Set[str] = set()
    franchises: Set[str] = set()

    for r in top5:
        all_genres.update([g.lower() for g in r.game.genres])
        all_tags.update([t.lower() for t in r.game.tags])
        fam = Ranker._extract_franchise_family(r.game.title) or r.game.title.lower()
        franchises.add(fam)

    return {
        "genre_div": float(len(all_genres)),
        "tag_div": float(len(all_tags)),
        "franchise_div": float(len(franchises)),
    }


def compute_review_distribution(results: List[DiscoverySearchResult]) -> Dict[str, int]:
    dist = {
        "<100": 0,
        "100-249": 0,
        "250-499": 0,
        "500-999": 0,
        "1000-1999": 0,
        "2000-4999": 0,
        "5000+": 0,
    }
    for r in results[:5]:
        rev = r.game.total_reviews
        if rev < 100:
            dist["<100"] += 1
        elif rev < 250:
            dist["100-249"] += 1
        elif rev < 500:
            dist["250-499"] += 1
        elif rev < 1000:
            dist["500-999"] += 1
        elif rev < 2000:
            dist["1000-1999"] += 1
        elif rev < 5000:
            dist["2000-4999"] += 1
        else:
            dist["5000+"] += 1
    return dist


async def evaluate_suite(
    suite_name: str,
    queries: List[Dict[str, Any]],
    pool: DiscoveryCandidatePool,
    service: DiscoveryService,
    catalog_mgr: CatalogManager,
    twenty_k_ids: Set[str],
    mode: str = "DISCOVER",
) -> Dict[str, Any]:
    print(f"  Evaluating {suite_name} [{mode}] on {pool.value} ({len(queries)} queries)...")
    p5_list: List[float] = []
    latencies: List[float] = []
    hard_violations_count = 0
    intent_correct = 0

    zero_review_dense = 0
    zero_review_lex = 0
    zero_review_rrf = 0
    zero_review_top20 = 0
    zero_review_top5 = 0

    long_tail_exposed_queries = 0
    total_top5_slots = len(queries) * 5
    long_tail_slots = 0
    useful_exploratory_slots = 0

    genre_div_list: List[float] = []
    tag_div_list: List[float] = []
    franchise_div_list: List[float] = []

    agg_rev_dist = {
        "<100": 0,
        "100-249": 0,
        "250-499": 0,
        "500-999": 0,
        "1000-1999": 0,
        "2000-4999": 0,
        "5000+": 0,
    }
    top5_reviews_all: List[int] = []

    timing_breakdown = {
        "parse": [],
        "embed": [],
        "dense": [],
        "lex": [],
        "rrf": [],
        "rank": [],
        "total": [],
    }

    query_records: List[Dict[str, Any]] = []

    for q in queries:
        q_text = q["query"]
        trace = await run_detailed_pipeline(q_text, pool, service, catalog_mgr, mode=mode)
        results = trace["results"]

        # Latency & Timings
        latencies.append(trace["timings_ms"]["total"])
        for k, v in trace["timings_ms"].items():
            timing_breakdown[k].append(v)

        # Precision & Hard Constraints
        p5, has_violation = evaluate_precision(q, results)
        p5_list.append(p5)
        if has_violation:
            hard_violations_count += 1

        if trace["query_type"] == q.get("expected_type"):
            intent_correct += 1

        # Zero-review checks across all layers
        for gid in trace["dense_gids"]:
            g = catalog_mgr.get_game(gid)
            if g and g.get("total_reviews", 0) == 0:
                zero_review_dense += 1

        for gid in trace["lex_gids"]:
            g = catalog_mgr.get_game(gid)
            if g and g.get("total_reviews", 0) == 0:
                zero_review_lex += 1

        for gid in trace["rrf_gids"]:
            g = catalog_mgr.get_game(gid)
            if g and g.get("total_reviews", 0) == 0:
                zero_review_rrf += 1

        for gid in trace["top20_gids"]:
            g = catalog_mgr.get_game(gid)
            if g and g.get("total_reviews", 0) == 0:
                zero_review_top20 += 1

        for gid in trace["top5_gids"]:
            g = catalog_mgr.get_game(gid)
            if g and g.get("total_reviews", 0) == 0:
                zero_review_top5 += 1

        # Diversity
        div_m = compute_diversity_metrics(results)
        genre_div_list.append(div_m["genre_div"])
        tag_div_list.append(div_m["tag_div"])
        franchise_div_list.append(div_m["franchise_div"])

        # Review distributions & Novelty
        q_rev_dist = compute_review_distribution(results)
        for k, v in q_rev_dist.items():
            agg_rev_dist[k] += v

        top5 = results[:5]
        top5_gids = [str(r.game.id) for r in top5]
        top5_revs = [r.game.total_reviews for r in top5]
        top5_reviews_all.extend(top5_revs)

        # Useful Novelty: outside 20k + no violation + calibrated score >= 0.70
        q_has_long_tail = False
        for r in top5:
            gid = str(r.game.id)
            if gid not in twenty_k_ids:
                long_tail_slots += 1
                q_has_long_tail = True
                if not has_violation and r.score >= 0.70:
                    useful_exploratory_slots += 1

        if q_has_long_tail:
            long_tail_exposed_queries += 1

        query_records.append({
            "id": q["id"],
            "query": q_text,
            "category": q.get("category", ""),
            "p5": round(p5, 3),
            "latency_ms": trace["timings_ms"]["total"],
            "top5_titles": [r.game.title for r in top5],
            "top5_reviews": top5_revs,
            "top5_scores": [round(float(r.score), 3) for r in top5],
            "top5_outside_20k": [str(r.game.id) not in twenty_k_ids for r in top5],
            "trace": trace,
        })

    mean_p5 = float(np.mean(p5_list))
    p95_latency = float(np.percentile(latencies, 95))
    mean_latency = float(np.mean(latencies))

    return {
        "suite_name": suite_name,
        "candidate_pool": pool.value,
        "query_count": len(queries),
        "mean_p5": round(mean_p5, 4),
        "hard_violations": hard_violations_count,
        "intent_accuracy": round(intent_correct / max(1, len(queries)), 4),
        "mean_latency_ms": round(mean_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
        "timing_breakdown_ms": {k: round(float(np.mean(v)), 2) for k, v in timing_breakdown.items()},
        "zero_review_invariants": {
            "dense": zero_review_dense,
            "lexical": zero_review_lex,
            "rrf": zero_review_rrf,
            "top20": zero_review_top20,
            "top5": zero_review_top5,
        },
        "novelty": {
            "long_tail_exposure_pct": round((long_tail_exposed_queries / max(1, len(queries))) * 100.0, 2),
            "top5_long_tail_share_pct": round((long_tail_slots / max(1, total_top5_slots)) * 100.0, 2),
            "useful_exploratory_share_pct": round((useful_exploratory_slots / max(1, total_top5_slots)) * 100.0, 2),
            "median_reviews_top5": int(np.median(top5_reviews_all)) if top5_reviews_all else 0,
            "review_distribution": agg_rev_dist,
        },
        "diversity": {
            "mean_genre_diversity": round(float(np.mean(genre_div_list)), 2),
            "mean_tag_diversity": round(float(np.mean(tag_div_list)), 2),
            "mean_franchise_diversity": round(float(np.mean(franchise_div_list)), 2),
        },
        "queries": query_records,
    }


def compute_stage_overlap(list_a: List[str], list_b: List[str]) -> Dict[str, Any]:
    set_a = set(list_a)
    set_b = set(list_b)
    intersection = set_a.intersection(set_b)
    union = set_a.union(set_b)
    jaccard = len(intersection) / max(1, len(union))
    new_in_b = set_b - set_a
    return {
        "size_a": len(set_a),
        "size_b": len(set_b),
        "intersection": len(intersection),
        "union": len(union),
        "jaccard": round(jaccard, 4),
        "new_candidates_count": len(new_in_b),
    }


async def main():
    print("=" * 80)
    print("GAMEFORGE DISCOVERY V2.4 — DISCOVER CANDIDATE-POOL EXPERIMENT")
    print("=" * 80)

    # 1. Warm service & load catalogs
    print("Initializing DiscoveryService...")
    service = DiscoveryService()
    await asyncio.to_thread(service.warm)
    catalog_mgr = service.catalog_manager
    twenty_k_ids = load_twenty_k_ids(catalog_mgr)
    print(f"Catalog loaded: {len(catalog_mgr.get_all_games())} games (20k head identified).")

    # Verify Reviewed-Only index health
    rev_index_path = BACKEND_DIR / "data" / "processed" / "games_index_reviewed_only.faiss"
    rev_meta_path = BACKEND_DIR / "data" / "processed" / "index_meta_reviewed_only.json"
    print(f"Checking Reviewed-Only FAISS index at {rev_index_path}...")
    if not rev_index_path.exists():
        print("[ERROR] Reviewed-only FAISS index missing!")
        return

    # 2. Load Benchmarks
    with open(STD_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        std_benchmark = json.load(f)
    std_queries = std_benchmark["queries"]

    with open(DISC_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        disc_benchmark = json.load(f)
    disc_queries = disc_benchmark["queries"]

    # 3. Test Lazy-Loading & Cold/Warm Latency
    print("\nEvaluating Index Lazy-Loading and Cold vs Warm Latency...")
    # Fresh IndexManager to measure cold load of 20k vs reviewed_only
    fresh_mgr = FAISSIndexManager()
    fresh_mgr._pool_cache.clear()

    t0 = time.perf_counter()
    pool_20k_data = fresh_mgr._get_or_load_pool(DiscoveryCandidatePool.POPULAR_20K)
    cold_load_20k_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    pool_rev_data = fresh_mgr._get_or_load_pool(DiscoveryCandidatePool.REVIEWED_ONLY)
    cold_load_rev_ms = (time.perf_counter() - t0) * 1000.0

    # Warm load
    t0 = time.perf_counter()
    _ = fresh_mgr._get_or_load_pool(DiscoveryCandidatePool.REVIEWED_ONLY)
    warm_reuse_rev_ms = (time.perf_counter() - t0) * 1000.0

    print(f"  Cold Load 20k Index:          {cold_load_20k_ms:.2f} ms")
    print(f"  Cold Load Reviewed-Only Index: {cold_load_rev_ms:.2f} ms")
    print(f"  Warm Reuse In-Memory Index:    {warm_reuse_rev_ms:.4f} ms")

    # 4. Run Benchmark Suites under Condition A and Condition B
    print("\n" + "=" * 80)
    print("RUNNING EXPERIMENT: STANDARD 30 BENCHMARK")
    print("=" * 80)
    std_res_20k = await evaluate_suite("Standard 30", std_queries, DiscoveryCandidatePool.POPULAR_20K, service, catalog_mgr, twenty_k_ids)
    std_res_rev = await evaluate_suite("Standard 30", std_queries, DiscoveryCandidatePool.REVIEWED_ONLY, service, catalog_mgr, twenty_k_ids)

    print("\n" + "=" * 80)
    print("RUNNING EXPERIMENT: DEDICATED 25 EXPLORATORY DISCOVER BENCHMARK")
    print("=" * 80)
    disc_res_20k = await evaluate_suite("Dedicated 25 Exploratory", disc_queries, DiscoveryCandidatePool.POPULAR_20K, service, catalog_mgr, twenty_k_ids)
    disc_res_rev = await evaluate_suite("Dedicated 25 Exploratory", disc_queries, DiscoveryCandidatePool.REVIEWED_ONLY, service, catalog_mgr, twenty_k_ids)

    # 5. Overlap & Funnel Analysis across Stages (Dedicated Exploratory Suite)
    print("\n" + "=" * 80)
    print("COMPUTING CANDIDATE OVERLAP & FUNNEL DYNAMICS")
    print("=" * 80)

    stages = ["dense", "lexical", "rrf", "top20", "top5"]
    overlap_totals = {s: {"jaccard": [], "new_candidates": []} for s in stages}

    funnel_totals = {
        "pool_size": 87890,
        "dense_new": [],
        "lex_new": [],
        "rrf_new": [],
        "top20_new": [],
        "top5_new": [],
    }

    for q20k, qrev in zip(disc_res_20k["queries"], disc_res_rev["queries"]):
        t20k = q20k["trace"]
        trev = qrev["trace"]

        o_dense = compute_stage_overlap(t20k["dense_gids"], trev["dense_gids"])
        o_lex = compute_stage_overlap(t20k["lex_gids"], trev["lex_gids"])
        o_rrf = compute_stage_overlap(t20k["rrf_gids"], trev["rrf_gids"])
        o_top20 = compute_stage_overlap(t20k["top20_gids"], trev["top20_gids"])
        o_top5 = compute_stage_overlap(t20k["top5_gids"], trev["top5_gids"])

        overlap_totals["dense"]["jaccard"].append(o_dense["jaccard"])
        overlap_totals["dense"]["new_candidates"].append(o_dense["new_candidates_count"])

        overlap_totals["lexical"]["jaccard"].append(o_lex["jaccard"])
        overlap_totals["lexical"]["new_candidates"].append(o_lex["new_candidates_count"])

        overlap_totals["rrf"]["jaccard"].append(o_rrf["jaccard"])
        overlap_totals["rrf"]["new_candidates"].append(o_rrf["new_candidates_count"])

        overlap_totals["top20"]["jaccard"].append(o_top20["jaccard"])
        overlap_totals["top20"]["new_candidates"].append(o_top20["new_candidates_count"])

        overlap_totals["top5"]["jaccard"].append(o_top5["jaccard"])
        overlap_totals["top5"]["new_candidates"].append(o_top5["new_candidates_count"])

        funnel_totals["dense_new"].append(o_dense["new_candidates_count"])
        funnel_totals["lex_new"].append(o_lex["new_candidates_count"])
        funnel_totals["rrf_new"].append(o_rrf["new_candidates_count"])
        funnel_totals["top20_new"].append(o_top20["new_candidates_count"])
        funnel_totals["top5_new"].append(o_top5["new_candidates_count"])

    overlap_summary = {
        s: {
            "mean_jaccard": round(float(np.mean(overlap_totals[s]["jaccard"])), 4),
            "mean_new_candidates": round(float(np.mean(overlap_totals[s]["new_candidates"])), 2),
        }
        for s in stages
    }

    funnel_summary = {
        "candidate_pool_size": 87890,
        "mean_new_dense_candidates": round(float(np.mean(funnel_totals["dense_new"])), 1),
        "mean_new_lexical_candidates": round(float(np.mean(funnel_totals["lex_new"])), 1),
        "mean_new_rrf_candidates": round(float(np.mean(funnel_totals["rrf_new"])), 1),
        "mean_new_top20_candidates": round(float(np.mean(funnel_totals["top20_new"])), 1),
        "mean_new_top5_candidates": round(float(np.mean(funnel_totals["top5_new"])), 1),
        "new_candidate_reach_rate_pct": round(float(np.mean([1 if x > 0 else 0 for x in funnel_totals["rrf_new"]])) * 100.0, 1),
        "new_candidate_top20_rate_pct": round(float(np.mean([1 if x > 0 else 0 for x in funnel_totals["top20_new"]])) * 100.0, 1),
        "new_candidate_top5_rate_pct": round(float(np.mean([1 if x > 0 else 0 for x in funnel_totals["top5_new"]])) * 100.0, 1),
    }

    # 6. Deep Dive Queries Selection
    # Select 5 representative exploratory queries:
    # disc01: "cozy automation with trains"
    # disc02: "cyberpunk detective game without heavy combat"
    # disc05: "deckbuilder with base building"
    # disc14: "games like Stardew Valley but more exploratory"
    # disc12: "farming without horror"
    deep_dive_ids = ["disc01", "disc02", "disc05", "disc14", "disc12"]
    deep_dives = []

    for q_id in deep_dive_ids:
        q_spec = next(q for q in disc_queries if q["id"] == q_id)
        q20 = next(r for r in disc_res_20k["queries"] if r["id"] == q_id)
        qrev = next(r for r in disc_res_rev["queries"] if r["id"] == q_id)

        t5_20_details = []
        for r in q20["trace"]["results"][:5]:
            t5_20_details.append({
                "title": r.game.title,
                "reviews": r.game.total_reviews,
                "score": round(float(r.score), 4),
                "outside_20k": str(r.game.id) not in twenty_k_ids,
            })

        t5_rev_details = []
        for r in qrev["trace"]["results"][:5]:
            t5_rev_details.append({
                "title": r.game.title,
                "reviews": r.game.total_reviews,
                "score": round(float(r.score), 4),
                "outside_20k": str(r.game.id) not in twenty_k_ids,
            })

        deep_dives.append({
            "id": q_id,
            "query": q_spec["query"],
            "category": q_spec["category"],
            "condition_a_top5": t5_20_details,
            "condition_b_top5": t5_rev_details,
        })

    # 7. Non-DISCOVER Regression Check
    print("\nRunning Non-DISCOVER Regression Verification...")
    bm_res = await evaluate_suite("Standard 30", std_queries, DiscoveryCandidatePool.POPULAR_20K, service, catalog_mgr, twenty_k_ids, mode="BEST_MATCH")
    pop_res = await evaluate_suite("Standard 30", std_queries, DiscoveryCandidatePool.POPULAR_20K, service, catalog_mgr, twenty_k_ids, mode="POPULAR")
    hg_res = await evaluate_suite("Standard 30", std_queries, DiscoveryCandidatePool.REVIEWED_ONLY, service, catalog_mgr, twenty_k_ids, mode="HIDDEN_GEMS")

    # 8. Compile Comprehensive Experiment Report JSON
    report = {
        "experiment": "Discovery V2.4 — DISCOVER Candidate-Pool Experiment",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cold_load_benchmarks": {
            "cold_load_20k_ms": round(cold_load_20k_ms, 2),
            "cold_load_reviewed_only_ms": round(cold_load_rev_ms, 2),
            "warm_reuse_ms": round(warm_reuse_rev_ms, 4),
        },
        "standard_30_benchmark": {
            "condition_a_20k": {
                "precision5": std_res_20k["mean_p5"],
                "hard_violations": std_res_20k["hard_violations"],
                "intent_accuracy": std_res_20k["intent_accuracy"],
                "mean_latency_ms": std_res_20k["mean_latency_ms"],
                "p95_latency_ms": std_res_20k["p95_latency_ms"],
                "long_tail_exposure_pct": std_res_20k["novelty"]["long_tail_exposure_pct"],
                "top5_long_tail_share_pct": std_res_20k["novelty"]["top5_long_tail_share_pct"],
                "useful_exploratory_share_pct": std_res_20k["novelty"]["useful_exploratory_share_pct"],
                "median_reviews": std_res_20k["novelty"]["median_reviews_top5"],
                "diversity": std_res_20k["diversity"],
                "zero_review_invariants": std_res_20k["zero_review_invariants"],
                "timing_breakdown": std_res_20k["timing_breakdown_ms"],
            },
            "condition_b_reviewed_only": {
                "precision5": std_res_rev["mean_p5"],
                "hard_violations": std_res_rev["hard_violations"],
                "intent_accuracy": std_res_rev["intent_accuracy"],
                "mean_latency_ms": std_res_rev["mean_latency_ms"],
                "p95_latency_ms": std_res_rev["p95_latency_ms"],
                "long_tail_exposure_pct": std_res_rev["novelty"]["long_tail_exposure_pct"],
                "top5_long_tail_share_pct": std_res_rev["novelty"]["top5_long_tail_share_pct"],
                "useful_exploratory_share_pct": std_res_rev["novelty"]["useful_exploratory_share_pct"],
                "median_reviews": std_res_rev["novelty"]["median_reviews_top5"],
                "diversity": std_res_rev["diversity"],
                "zero_review_invariants": std_res_rev["zero_review_invariants"],
                "timing_breakdown": std_res_rev["timing_breakdown_ms"],
            },
        },
        "dedicated_25_exploratory_benchmark": {
            "condition_a_20k": {
                "precision5": disc_res_20k["mean_p5"],
                "hard_violations": disc_res_20k["hard_violations"],
                "intent_accuracy": disc_res_20k["intent_accuracy"],
                "mean_latency_ms": disc_res_20k["mean_latency_ms"],
                "p95_latency_ms": disc_res_20k["p95_latency_ms"],
                "long_tail_exposure_pct": disc_res_20k["novelty"]["long_tail_exposure_pct"],
                "top5_long_tail_share_pct": disc_res_20k["novelty"]["top5_long_tail_share_pct"],
                "useful_exploratory_share_pct": disc_res_20k["novelty"]["useful_exploratory_share_pct"],
                "median_reviews": disc_res_20k["novelty"]["median_reviews_top5"],
                "review_distribution": disc_res_20k["novelty"]["review_distribution"],
                "diversity": disc_res_20k["diversity"],
                "zero_review_invariants": disc_res_20k["zero_review_invariants"],
                "timing_breakdown": disc_res_20k["timing_breakdown_ms"],
            },
            "condition_b_reviewed_only": {
                "precision5": disc_res_rev["mean_p5"],
                "hard_violations": disc_res_rev["hard_violations"],
                "intent_accuracy": disc_res_rev["intent_accuracy"],
                "mean_latency_ms": disc_res_rev["mean_latency_ms"],
                "p95_latency_ms": disc_res_rev["p95_latency_ms"],
                "long_tail_exposure_pct": disc_res_rev["novelty"]["long_tail_exposure_pct"],
                "top5_long_tail_share_pct": disc_res_rev["novelty"]["top5_long_tail_share_pct"],
                "useful_exploratory_share_pct": disc_res_rev["novelty"]["useful_exploratory_share_pct"],
                "median_reviews": disc_res_rev["novelty"]["median_reviews_top5"],
                "review_distribution": disc_res_rev["novelty"]["review_distribution"],
                "diversity": disc_res_rev["diversity"],
                "zero_review_invariants": disc_res_rev["zero_review_invariants"],
                "timing_breakdown": disc_res_rev["timing_breakdown_ms"],
            },
        },
        "stage_overlap": overlap_summary,
        "discover_funnel": funnel_summary,
        "deep_dive_queries": deep_dives,
        "non_discover_regression": {
            "best_match_p5": bm_res["mean_p5"],
            "best_match_violations": bm_res["hard_violations"],
            "popular_p5": pop_res["mean_p5"],
            "popular_violations": pop_res["hard_violations"],
            "hidden_gems_p5": hg_res["mean_p5"],
            "hidden_gems_violations": hg_res["hard_violations"],
        },
    }

    OUTPUT_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 80)
    print(f"EXPERIMENT COMPLETE! Results saved to {OUTPUT_RESULTS_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
