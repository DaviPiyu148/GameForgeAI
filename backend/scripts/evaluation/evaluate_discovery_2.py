import asyncio
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Set, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.schemas.discovery import DiscoverySearchRequest
from app.services.discovery_service import DiscoveryService
from app.search.catalog import CatalogManager
from app.search.embedder import QueryEmbedder
from app.search.index import FAISSIndexManager
from app.search.lexical import normalize_string, tokenize


def compute_dcg_at_k(relevances: List[int], k: int = 10) -> float:
    """Compute Discounted Cumulative Gain at rank K."""
    dcg = 0.0
    for i, rel in enumerate(relevances[:k], 1):
        if rel > 0:
            dcg += (2**rel - 1) / math.log2(i + 1)
    return dcg


def compute_ndcg_at_k(relevances: List[int], ideal_count: int, k: int = 10) -> float:
    """Compute Normalized Discounted Cumulative Gain at rank K."""
    dcg = compute_dcg_at_k(relevances, k)
    ideal_relevances = [1] * min(ideal_count, k)
    idcg = compute_dcg_at_k(ideal_relevances, k)
    if idcg <= 0.0:
        return 1.0 if dcg == 0.0 else 0.0
    return dcg / idcg


async def run_evaluation():
    print("=" * 80, flush=True)
    print("GAMEFORGE AI — DISCOVERY ENGINE 2.0 COMPREHENSIVE BENCHMARK EVALUATION", flush=True)
    print("=" * 80, flush=True)

    # 1. Load benchmark fixture
    benchmark_path = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "discovery_benchmark_set.json")
    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmark_queries: List[Dict[str, Any]] = json.load(f)

    print(f"Loaded {len(benchmark_queries)} benchmark queries.", flush=True)

    # 2. Instantiate managers
    cm = CatalogManager.get_instance()
    embedder = QueryEmbedder.get_instance()
    index_mgr = FAISSIndexManager.get_instance()
    d2_service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=cm)

    # 3. Evaluate Baseline (Pure Semantic FAISS)
    print("\n[1/2] Running Baseline (Pure Semantic FAISS) Evaluation...", flush=True)
    baseline_p5_list = []
    baseline_r10_list = []
    baseline_mrr_list = []
    baseline_ndcg_list = []
    baseline_latencies = []
    baseline_top_results: Dict[str, List[str]] = {}

    for i, q in enumerate(benchmark_queries, 1):
        prompt = q["prompt"]
        if i % 10 == 0 or i == len(benchmark_queries):
            print(f"  Processed {i}/{len(benchmark_queries)} baseline queries...", flush=True)
        expected_landmarks = [normalize_string(lm) for lm in q.get("expected_landmarks", [])]
        
        t0 = time.perf_counter()
        # Baseline semantic retrieval only
        q_vec = embedder.embed_query(prompt)
        raw_matches = index_mgr.search(q_vec, top_k=20)
        dt = (time.perf_counter() - t0) * 1000
        baseline_latencies.append(dt)

        top_games = []
        for gid, score in raw_matches[:10]:
            g = cm.get_game(gid)
            if g:
                top_games.append(g)

        baseline_top_results[q["id"]] = [g["title"] for g in top_games[:5]]

        # Calculate metrics
        relevances = []
        first_hit_rank = 0
        hits_at_10 = 0

        for rank, g in enumerate(top_games[:10], 1):
            g_title_norm = normalize_string(g["title"])
            is_relevant = any(exp in g_title_norm or g_title_norm in exp for exp in expected_landmarks)
            if is_relevant:
                relevances.append(1)
                hits_at_10 += 1
                if first_hit_rank == 0:
                    first_hit_rank = rank
            else:
                relevances.append(0)

        # Handle queries with no expected landmarks (e.g. no-match test)
        if not expected_landmarks:
            baseline_p5_list.append(1.0)
            baseline_r10_list.append(1.0)
            baseline_mrr_list.append(1.0)
            baseline_ndcg_list.append(1.0)
        else:
            p5 = sum(relevances[:5]) / 5.0
            r10 = min(1.0, hits_at_10 / max(1, len(expected_landmarks)))
            mrr = 1.0 / first_hit_rank if first_hit_rank > 0 else 0.0
            ndcg = compute_ndcg_at_k(relevances, len(expected_landmarks), k=10)

            baseline_p5_list.append(p5)
            baseline_r10_list.append(r10)
            baseline_mrr_list.append(mrr)
            baseline_ndcg_list.append(ndcg)

    # 4. Evaluate Discovery 2.0 (Hybrid Retrieval & Ranker)
    print("[2/2] Running Discovery Engine 2.0 (Hybrid + RRF + Dynamic Ranker) Evaluation...", flush=True)
    d2_p5_list = []
    d2_r10_list = []
    d2_mrr_list = []
    d2_ndcg_list = []
    d2_latencies = []
    d2_top_results: Dict[str, List[str]] = {}

    for i, q in enumerate(benchmark_queries, 1):
        prompt = q["prompt"]
        if i % 10 == 0 or i == len(benchmark_queries):
            print(f"  Processed {i}/{len(benchmark_queries)} Discovery 2.0 queries...", flush=True)
        expected_landmarks = [normalize_string(lm) for lm in q.get("expected_landmarks", [])]

        t0 = time.perf_counter()
        req = DiscoverySearchRequest(prompt=prompt, limit=12)
        resp = await d2_service.search(req)
        dt = (time.perf_counter() - t0) * 1000
        d2_latencies.append(dt)

        top_games = [r.game for r in resp.results]
        d2_top_results[q["id"]] = [g.title for g in top_games[:5]]

        # Calculate metrics
        relevances = []
        first_hit_rank = 0
        hits_at_10 = 0

        for rank, g in enumerate(top_games[:10], 1):
            g_title_norm = normalize_string(g.title)
            is_relevant = any(exp in g_title_norm or g_title_norm in exp for exp in expected_landmarks)
            if is_relevant:
                relevances.append(1)
                hits_at_10 += 1
                if first_hit_rank == 0:
                    first_hit_rank = rank
            else:
                relevances.append(0)

        if not expected_landmarks:
            # For synthetic no-match, if no_strong_match is true, precision is 1.0
            d2_p5_list.append(1.0 if resp.no_strong_match else 0.0)
            d2_r10_list.append(1.0 if resp.no_strong_match else 0.0)
            d2_mrr_list.append(1.0 if resp.no_strong_match else 0.0)
            d2_ndcg_list.append(1.0 if resp.no_strong_match else 0.0)
        else:
            p5 = sum(relevances[:5]) / 5.0
            r10 = min(1.0, hits_at_10 / max(1, len(expected_landmarks)))
            mrr = 1.0 / first_hit_rank if first_hit_rank > 0 else 0.0
            ndcg = compute_ndcg_at_k(relevances, len(expected_landmarks), k=10)

            d2_p5_list.append(p5)
            d2_r10_list.append(r10)
            d2_mrr_list.append(mrr)
            d2_ndcg_list.append(ndcg)

    # 5. Summary Statistics
    base_p5_avg = sum(baseline_p5_list) / len(baseline_p5_list)
    base_r10_avg = sum(baseline_r10_list) / len(baseline_r10_list)
    base_mrr_avg = sum(baseline_mrr_list) / len(baseline_mrr_list)
    base_ndcg_avg = sum(baseline_ndcg_list) / len(baseline_ndcg_list)
    base_lat_avg = sum(baseline_latencies) / len(baseline_latencies)
    baseline_latencies.sort()
    base_lat_p95 = baseline_latencies[int(len(baseline_latencies) * 0.95)]

    d2_p5_avg = sum(d2_p5_list) / len(d2_p5_list)
    d2_r10_avg = sum(d2_r10_list) / len(d2_r10_list)
    d2_mrr_avg = sum(d2_mrr_list) / len(d2_mrr_list)
    d2_ndcg_avg = sum(d2_ndcg_list) / len(d2_ndcg_list)
    d2_lat_avg = sum(d2_latencies) / len(d2_latencies)
    d2_latencies.sort()
    d2_lat_p95 = d2_latencies[int(len(d2_latencies) * 0.95)]

    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS: BASELINE vs DISCOVERY ENGINE 2.0")
    print("=" * 80)
    print(f"{'Metric':<18} | {'Baseline (Pure Semantic)':<25} | {'Discovery 2.0 (Hybrid)':<25} | {'Delta':<12}")
    print("-" * 86)
    print(f"{'Precision@5':<18} | {base_p5_avg:<25.4f} | {d2_p5_avg:<25.4f} | {f'+{d2_p5_avg - base_p5_avg:.4f}' if d2_p5_avg >= base_p5_avg else f'{d2_p5_avg - base_p5_avg:.4f}':<12}")
    print(f"{'Recall@10':<18} | {base_r10_avg:<25.4f} | {d2_r10_avg:<25.4f} | {f'+{d2_r10_avg - base_r10_avg:.4f}' if d2_r10_avg >= base_r10_avg else f'{d2_r10_avg - base_r10_avg:.4f}':<12}")
    print(f"{'MRR':<18} | {base_mrr_avg:<25.4f} | {d2_mrr_avg:<25.4f} | {f'+{d2_mrr_avg - base_mrr_avg:.4f}' if d2_mrr_avg >= base_mrr_avg else f'{d2_mrr_avg - base_mrr_avg:.4f}':<12}")
    print(f"{'NDCG@10':<18} | {base_ndcg_avg:<25.4f} | {d2_ndcg_avg:<25.4f} | {f'+{d2_ndcg_avg - base_ndcg_avg:.4f}' if d2_ndcg_avg >= base_ndcg_avg else f'{d2_ndcg_avg - base_ndcg_avg:.4f}':<12}")
    print(f"{'Avg Latency (ms)':<18} | {base_lat_avg:<25.2f} | {d2_lat_avg:<25.2f} | {f'+{d2_lat_avg - base_lat_avg:.2f}' if d2_lat_avg >= base_lat_avg else f'{d2_lat_avg - base_lat_avg:.2f}':<12}")
    print(f"{'P95 Latency (ms)':<18} | {base_lat_p95:<25.2f} | {d2_lat_p95:<25.2f} | {f'+{d2_lat_p95 - base_lat_p95:.2f}' if d2_lat_p95 >= base_lat_p95 else f'{d2_lat_p95 - base_lat_p95:.2f}':<12}")
    print("=" * 80)

    # 6. Landmark Comparison Table
    landmark_query_ids = ["q01", "q02", "q03", "q04", "q05", "q06", "q16", "q22", "q23", "q31", "q33", "q34"]
    print("\nLANDMARK QUERY RANKING COMPARISON TABLE:")
    print("-" * 80)
    for qid in landmark_query_ids:
        q_item = next((q for q in benchmark_queries if q["id"] == qid), None)
        if not q_item:
            continue
        prompt = q_item["prompt"]
        exp = ", ".join(q_item.get("expected_landmarks", []))
        base_top = baseline_top_results.get(qid, [])[:2]
        d2_top = d2_top_results.get(qid, [])[:2]
        print(f"Query: '{prompt}' (Expected: {exp})")
        print(f"  Baseline Top 2:    {base_top}")
        print(f"  Discovery 2.0 Top 2: {d2_top}\n")

    report_data = {
        "query_count": len(benchmark_queries),
        "baseline": {
            "p5": round(base_p5_avg, 4),
            "r10": round(base_r10_avg, 4),
            "mrr": round(base_mrr_avg, 4),
            "ndcg": round(base_ndcg_avg, 4),
            "avg_latency_ms": round(base_lat_avg, 2),
            "p95_latency_ms": round(base_lat_p95, 2),
        },
        "discovery_2": {
            "p5": round(d2_p5_avg, 4),
            "r10": round(d2_r10_avg, 4),
            "mrr": round(d2_mrr_avg, 4),
            "ndcg": round(d2_ndcg_avg, 4),
            "avg_latency_ms": round(d2_lat_avg, 2),
            "p95_latency_ms": round(d2_lat_p95, 2),
        },
        "delta": {
            "p5": round(d2_p5_avg - base_p5_avg, 4),
            "r10": round(d2_r10_avg - base_r10_avg, 4),
            "mrr": round(d2_mrr_avg - base_mrr_avg, 4),
            "ndcg": round(d2_ndcg_avg - base_ndcg_avg, 4),
        }
    }

    report_path = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "benchmark_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print(f"Benchmark summary report saved to {report_path}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
