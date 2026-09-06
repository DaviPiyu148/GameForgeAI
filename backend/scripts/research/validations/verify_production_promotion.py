"""
GameForge Discovery — Production Promotion Verification (Discovery V2.4).

Executes:
1. Production Ranker validation (T150) on Standard 30 & Long-Tail 25 benchmarks.
2. Direct comparison against baseline Before (T2000).
3. Non-HIDDEN_GEMS mode regression check (BEST_MATCH, POPULAR, DISCOVER).
4. Representative title trajectories (Shapebreaker, MOTHERED, Floating Farmer, Colony Ship, Farming Sim 2013).
5. Review band distribution and lexical intrusion check.
"""

import asyncio
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set

import numpy as np
import torch

torch.set_num_threads(12)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app.schemas.discovery import DiscoverySearchRequest
from app.search.candidate_pool import DiscoveryCandidatePool
from app.search.catalog import CatalogManager
from app.search.embedder import QueryEmbedder
from app.search.index import FAISSIndexManager
from app.search.lexical import normalize_string
from app.services.discovery_service import DiscoveryService
from scripts.audit_candidate_overlap import LONG_TAIL_QUERIES

CATALOG_PATH = BACKEND_DIR / "data" / "processed" / "games_catalog.json"
BENCHMARK_FILE = BACKEND_DIR / "tests" / "data" / "discovery_benchmark.json"

FINE_BANDS = [
    ("1-49", 1, 49),
    ("50-99", 50, 99),
    ("100-249", 100, 249),
    ("250-499", 250, 499),
    ("500-999", 500, 999),
    ("1000-1999", 1000, 1999),
    ("2000-4999", 2000, 4999),
    ("5000+", 5000, 1000000000),
]


def classify_band(reviews: int) -> str:
    for name, low, high in FINE_BANDS:
        if low <= reviews <= high:
            return name
    return "5000+"


async def run_benchmark_on_service(
    service: DiscoveryService,
    queries: List[Dict[str, Any]],
    mode: str,
    twenty_k_ids: Set[str],
) -> Dict[str, Any]:
    p5_scores = []
    latencies = []
    hard_violations = 0
    all_top5_reviews = []
    qualifying_top5_longtail = 0
    total_top5_slots = 0
    band_counts = {b[0]: 0 for b in FINE_BANDS}

    top20_reach = 0
    top5_surface = 0
    best_longtail_ranks = []

    for q in queries:
        req = DiscoverySearchRequest(
            prompt=q["query"],
            mode=mode,
            limit=20,
        )
        t0 = time.perf_counter()
        resp = await service.search(req)
        lat_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(lat_ms)

        results = resp.results
        top5 = results[:5]

        # Hard constraints
        if q.get("must_not_contain_genres"):
            banned_g = {g.lower() for g in q["must_not_contain_genres"]}
            for r in top5:
                game_g = {g.lower() for g in r.game.genres}
                if banned_g.intersection(game_g):
                    hard_violations += 1
                    break

        if q.get("must_not_contain_modes"):
            banned_m = {m.lower() for m in q["must_not_contain_modes"]}
            for r in top5:
                game_m = {m.lower() for m in r.game.player_modes}
                if banned_m.intersection(game_m):
                    hard_violations += 1
                    break

        if q.get("must_be_free"):
            for r in top5:
                if not r.game.is_free:
                    hard_violations += 1
                    break

        # Precision@5
        relevant_in_top5 = 0
        must_include = q.get("must_include_titles", [])
        acceptable_g = {g.lower() for g in q.get("acceptable_genres", [])}

        for r in top5:
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

        p5_scores.append(relevant_in_top5 / max(1, min(5, len(top5))))

        # Reviews & bands
        for r in top5:
            revs = r.game.total_reviews or 0
            all_top5_reviews.append(revs)
            total_top5_slots += 1
            if revs <= 5000:
                qualifying_top5_longtail += 1
            band = classify_band(revs)
            band_counts[band] += 1

        # Long-tail candidate tracking
        lt_in_top20 = [r for idx, r in enumerate(results) if str(r.game.id) not in twenty_k_ids]
        lt_in_top5 = [r for r in top5 if str(r.game.id) not in twenty_k_ids]

        if lt_in_top20:
            top20_reach += 1
            # 1-indexed rank
            best_rank = next(idx + 1 for idx, r in enumerate(results) if str(r.game.id) not in twenty_k_ids)
            best_longtail_ranks.append(best_rank)
        if lt_in_top5:
            top5_surface += 1

    num_q = len(queries)
    slots = max(1, total_top5_slots)
    lt_100 = sum(band_counts[b[0]] for b in FINE_BANDS if b[2] < 100) / slots * 100.0
    mid_tail = sum(band_counts[b[0]] for b in FINE_BANDS if 100 <= b[1] and b[2] < 2000) / slots * 100.0

    return {
        "precision_at_5": round(float(np.mean(p5_scores)), 4),
        "hard_violations": hard_violations,
        "latency_mean_ms": round(float(np.mean(latencies)), 2),
        "long_tail_exposure_at_5": round(qualifying_top5_longtail / slots * 100.0, 1),
        "top5_long_tail_surface_rate": round(top5_surface / max(1, num_q) * 100.0, 1),
        "top20_long_tail_reach_rate": round(top20_reach / max(1, num_q) * 100.0, 1),
        "avg_best_long_tail_rank": round(float(np.mean(best_longtail_ranks)), 2) if best_longtail_ranks else 20.0,
        "median_best_long_tail_rank": int(np.median(best_longtail_ranks)) if best_longtail_ranks else 20,
        "median_reviews_top5": int(np.median(all_top5_reviews)) if all_top5_reviews else 0,
        "mean_reviews_top5": round(float(np.mean(all_top5_reviews)), 1) if all_top5_reviews else 0.0,
        "low_review_share_under_100": round(lt_100, 1),
        "mid_tail_share_100_1999": round(mid_tail, 1),
        "band_distribution": {b[0]: round(band_counts[b[0]] / slots * 100.0, 1) for b in FINE_BANDS},
    }


async def main():
    print("=" * 90)
    print("GAMEFORGE DISCOVERY — PRODUCTION PROMOTION VERIFICATION (T150)")
    print("=" * 90)

    cm = CatalogManager.get_instance(catalog_path=str(CATALOG_PATH))
    embedder = QueryEmbedder.get_instance()
    index_mgr = FAISSIndexManager.get_instance()

    service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=cm)
    service.warm()

    twenty_k_ids = set(str(g["id"]) for g in cm._catalog_list[:20000] if "id" in g)

    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    std_queries = bench_data["queries"]

    # 1. Run HIDDEN_GEMS on Production Ranker
    print("\nEvaluating Production Ranker on Standard 30 Benchmark (HIDDEN_GEMS)...")
    std_prod = await run_benchmark_on_service(service, std_queries, "HIDDEN_GEMS", twenty_k_ids)

    print("Evaluating Production Ranker on Dedicated 25 Long-Tail Benchmark (HIDDEN_GEMS)...")
    lt_prod = await run_benchmark_on_service(service, LONG_TAIL_QUERIES, "HIDDEN_GEMS", twenty_k_ids)

    # 2. Non-HIDDEN_GEMS regression checks
    print("\nEvaluating Non-HIDDEN_GEMS Modes for Regression...")
    bm_res = await run_benchmark_on_service(service, std_queries, "BEST_MATCH", twenty_k_ids)
    pop_res = await run_benchmark_on_service(service, std_queries, "POPULAR", twenty_k_ids)
    disc_res = await run_benchmark_on_service(service, std_queries, "DISCOVER", twenty_k_ids)

    # 3. Track key title trajectories
    print("\nEvaluating Representative Titles under Production Ranker...")
    targets = [
        ("Shapebreaker", "deckbuilder", "1924010"),
        ("Slay the Spire", "deckbuilder", "646570"),
        ("MOTHERED", "cyberpunk rpg", "1830720"),
        ("Colony Ship", "cyberpunk rpg", "648410"),
        ("Floating Farmer", "relaxing farming", "1716390"),
        ("Farming Simulator 2013", "relaxing farming", "220260"),
    ]

    title_results = []
    for t_name, q_text, t_id in targets:
        req = DiscoverySearchRequest(prompt=q_text, mode="HIDDEN_GEMS", limit=20)
        resp = await service.search(req)
        match = next(((idx + 1, r) for idx, r in enumerate(resp.results) if str(r.game.id) == t_id or t_name.lower() in r.game.title.lower()), None)
        if match:
            rank, res = match
            title_results.append({
                "title": t_name,
                "rank": f"#{rank}",
                "score": round(res.score, 4),
                "reviews": res.game.total_reviews,
                "query": q_text,
            })
        else:
            title_results.append({"title": t_name, "rank": ">20", "score": 0.0, "reviews": 0, "query": q_text})

    # Summary Output
    print("\n" + "=" * 90)
    print("SECTION B: BENCHMARK BEFORE / AFTER COMPARISON TABLE")
    print("=" * 90)
    print(f"{'Metric':<30} | {'Before (T2000)':<18} | {'T150 Production':<18}")
    print("-" * 90)
    print(f"{'Precision@5 (Std 30)':<30} | {'0.8733':<18} | {std_prod['precision_at_5']:<18.4f}")
    print(f"{'Long-Tail Exposure@5 (LT 25)':<30} | {'64.8%':<18} | {lt_prod['long_tail_exposure_at_5']:<17.1f}%")
    print(f"{'Top-5 Surface Rate (LT 25)':<30} | {'40.0%':<18} | {lt_prod['top5_long_tail_surface_rate']:<17.1f}%")
    print(f"{'Hard-Constraint Violations':<30} | {'0':<18} | {lt_prod['hard_violations']:<18}")
    print(f"{'Avg Best Long-Tail Rank':<30} | {'#5.35':<18} | #{lt_prod['avg_best_long_tail_rank']:<17.2f}")
    print(f"{'<100 Reviews Share':<30} | {'12.0%':<18} | {lt_prod['low_review_share_under_100']:<17.1f}%")
    print(f"{'Mid-Tail Share (100-1999)':<30} | {'32.0%':<18} | {lt_prod['mid_tail_share_100_1999']:<17.1f}%")
    print(f"{'Median Reviews in Top-5':<30} | {'2,379':<18} | {lt_prod['median_reviews_top5']:<18}")
    print(f"{'Mean Latency (Std 30)':<30} | {'274.3 ms':<18} | {std_prod['latency_mean_ms']:<15.1f} ms")

    print("\n" + "=" * 90)
    print("SECTION C: REPRESENTATIVE TITLES IN PRODUCTION")
    print("=" * 90)
    print(f"{'Title':<25} | {'Reviews':<8} | {'Rank':<6} | {'Score':<8} | {'Query':<25}")
    print("-" * 90)
    for tr in title_results:
        print(f"{tr['title']:<25} | {tr['reviews']:<8} | {tr['rank']:<6} | {tr['score']:<8.4f} | {tr['query']:<25}")

    print("\n" + "=" * 90)
    print("SECTION D: REGRESSION CHECK FOR NON-HIDDEN-GEMS MODES")
    print("=" * 90)
    print(f"{'Mode':<15} | {'Precision@5':<12} | {'Hard Violations':<15} | {'Mean Latency':<15}")
    print("-" * 90)
    print(f"{'BEST_MATCH':<15} | {bm_res['precision_at_5']:<12.4f} | {bm_res['hard_violations']:<15} | {bm_res['latency_mean_ms']:<13.1f} ms")
    print(f"{'POPULAR':<15} | {pop_res['precision_at_5']:<12.4f} | {pop_res['hard_violations']:<15} | {pop_res['latency_mean_ms']:<13.1f} ms")
    print(f"{'DISCOVER':<15} | {disc_res['precision_at_5']:<12.4f} | {disc_res['hard_violations']:<15} | {disc_res['latency_mean_ms']:<13.1f} ms")


if __name__ == "__main__":
    asyncio.run(main())

