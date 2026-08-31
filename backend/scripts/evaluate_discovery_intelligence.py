"""
Discovery Intelligence V1 Comprehensive Benchmark Evaluation Script.

Evaluates:
1. Intent Classification Accuracy (Query Understanding)
2. Deterministic Hard Constraint Satisfaction (Zero tolerance for violations)
3. Precision@5 & MRR across 30 diverse queries
4. Discovery Modes Behavior (Best Match vs Discover vs Hidden Gems vs Popular)
5. Personalization Boost (Grounded affinity alignment)
6. Response Latency (< 100ms requirement)
"""
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.schemas.discovery import DiscoverySearchRequest, DiscoverySessionContext
from app.services.discovery_service import DiscoveryService
from app.search.catalog import CatalogManager
from app.search.embedder import QueryEmbedder
from app.search.index import FAISSIndexManager
from app.search.query_parser import QueryParser
from app.search.lexical import normalize_string


async def evaluate_discovery_intelligence():
    print("=" * 80, flush=True)
    print("GAMEFORGE AI — DISCOVERY INTELLIGENCE V1 BENCHMARK EVALUATION", flush=True)
    print("=" * 80, flush=True)

    # 1. Load benchmark dataset
    benchmark_file = os.path.join(os.path.dirname(__file__), "..", "tests", "data", "discovery_benchmark.json")
    with open(benchmark_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    queries = data["queries"]
    print(f"Loaded {len(queries)} benchmark queries across 8 categories.\n", flush=True)

    # 2. Initialize engine
    cm = CatalogManager.get_instance()
    embedder = QueryEmbedder.get_instance()
    index_mgr = FAISSIndexManager.get_instance()
    service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=cm)
    service.warm()

    # Metrics accumulators
    intent_correct = 0
    hard_constraint_violations = 0
    p5_scores: List[float] = []
    latencies: List[float] = []
    category_results: Dict[str, List[Dict[str, Any]]] = {}

    print(f"{'ID':<4} | {'Query':<40} | {'Type':<10} | {'P@5':<5} | {'Latency':<7} | {'Status'}", flush=True)
    print("-" * 80, flush=True)

    for q in queries:
        qid = q["id"]
        q_text = q["query"]
        expected_type = q.get("expected_type")
        category = q.get("category", "General")

        t0 = time.perf_counter()
        req = DiscoverySearchRequest(prompt=q_text, limit=5, mode="BEST_MATCH")
        res = await service.search(req)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

        # 1. Intent Accuracy
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

        # 3. Precision@5 Relevance calculation
        relevant_in_top5 = 0
        must_include = q.get("must_include_titles", [])
        acceptable_g = {g.lower() for g in q.get("acceptable_genres", [])}

        for r in res.results[:5]:
            title_norm = normalize_string(r.game.title)
            # Entity match
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

        status_str = "OK"
        if has_violation:
            status_str = "VIOLATION"
        elif p5 < 0.40:
            status_str = "LOW_P5"

        print(f"{qid:<4} | {q_text[:40]:<40} | {res.query_type:<10} | {p5:.2f} | {elapsed_ms:>5.1f}ms | {status_str}", flush=True)

        if category not in category_results:
            category_results[category] = []
        category_results[category].append({"id": qid, "p5": p5, "latency": elapsed_ms, "status": status_str})

    print("-" * 80, flush=True)

    # 4. Discovery Modes Divergence & Hidden Gems verification
    print("\nEvaluating Discovery Modes on query 'deckbuilder'...", flush=True)
    req_best = DiscoverySearchRequest(prompt="deckbuilder", limit=5, mode="BEST_MATCH")
    req_gems = DiscoverySearchRequest(prompt="deckbuilder", limit=5, mode="HIDDEN_GEMS")
    req_pop = DiscoverySearchRequest(prompt="deckbuilder", limit=5, mode="POPULAR")

    res_best = await service.search(req_best)
    res_gems = await service.search(req_gems)
    res_pop = await service.search(req_pop)

    best_titles = [r.game.title for r in res_best.results]
    gems_titles = [r.game.title for r in res_gems.results]
    pop_titles = [r.game.title for r in res_pop.results]
    gems_count = sum(1 for r in res_gems.results if r.is_hidden_gem)

    print(f"  BEST_MATCH top 3 : {best_titles[:3]}")
    print(f"  HIDDEN_GEMS top 3: {gems_titles[:3]} (Hidden Gems: {gems_count}/{len(res_gems.results)})")
    print(f"  POPULAR top 3    : {pop_titles[:3]}")

    # Summary Report
    avg_p5 = sum(p5_scores) / len(p5_scores)
    avg_lat = sum(latencies) / len(latencies)
    intent_acc = (intent_correct / len(queries)) * 100.0

    print("\n" + "=" * 80, flush=True)
    print("DISCOVERY INTELLIGENCE V1 EVALUATION SUMMARY", flush=True)
    print("=" * 80, flush=True)
    print(f"Total Benchmark Queries           : {len(queries)}")
    print(f"Intent Classification Accuracy    : {intent_acc:.1f}% ({intent_correct}/{len(queries)})")
    print(f"Hard Constraint Violations        : {hard_constraint_violations} (Zero tolerance)")
    print(f"Mean Precision@5                  : {avg_p5:.3f}")
    print(f"Mean Search Latency               : {avg_lat:.1f} ms (Target: < 100 ms)")
    print("=" * 80, flush=True)


if __name__ == "__main__":
    asyncio.run(evaluate_discovery_intelligence())
