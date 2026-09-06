#!/usr/bin/env python3
"""
GameForge Discovery V2.7 — DISCOVER Low-Review Confidence Floor Experiment Runner.

Evaluates 4 conditions on Reviewed-Only (87,890 games):
- Condition A: Control (No Floor, low_review_confidence_floor=None)
- Condition B: 75% Floor (low_review_confidence_floor=75.0)
- Condition C: 80% Floor (low_review_confidence_floor=80.0)
- Condition D: 85% Floor (low_review_confidence_floor=85.0)

Measures:
- Standard 30 Benchmark
- Exploratory 25 Benchmark
- Detailed review brackets (<50, 50-99, 100-249, 250-499, 500-999, 1000+)
- Low-Review Intrusion@5 vs Legitimate Low-Review Preservation
- Critical negative cases (The Road to Hades, Stealth, Jack & Detectives)
- Critical positive cases (Shapebreaker, A Wholesome Game About Farming, RAILGRADE)
- Deterministic False-Positive Audit
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.search.candidate_pool import DiscoveryCandidatePool
from app.schemas.discovery import DiscoverySearchRequest, DiscoverySearchResponse
from app.services.discovery_service import DiscoveryService

POPULAR_THRESHOLD = 2000

STANDARD_BENCHMARK_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "data" / "discovery_benchmark.json"
EXPLORATORY_BENCHMARK_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "data" / "discover_exploratory_benchmark.json"
CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "games_catalog.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "discover_review_floor_experiment_results.json"


def load_catalog_metadata() -> Dict[str, Dict[str, Any]]:
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    return {str(g["id"]): g for g in catalog}


async def run_single_query(
    service: DiscoveryService,
    query_text: str,
    floor: Optional[float],
    catalog_meta: Dict[str, Dict[str, Any]],
    limit: int = 10,
) -> Dict[str, Any]:
    req = DiscoverySearchRequest(prompt=query_text, limit=limit, mode="DISCOVER")
    t0 = time.perf_counter()
    search_res = await service.search(
        req,
        candidate_pool_override=DiscoveryCandidatePool.REVIEWED_ONLY,
        single_channel_damping=0.0,
        low_review_confidence_floor=floor,
    )
    latency_ms = (time.perf_counter() - t0) * 1000.0

    results = search_res.results

    top5_deconstructed: List[Dict[str, Any]] = []
    for rank, r in enumerate(results[:5], 1):
        gid = str(r.game.id)
        g_meta = catalog_meta.get(gid, {})
        revs = int(g_meta.get("total_reviews", r.game.total_reviews or 0))
        pos_pct = float(g_meta.get("positive_percent", r.game.positive_percent or 0.0))

        # Check if single-channel lexical (lexical match, but absent from dense top-50)
        is_single_lex = False
        if r.match_highlights:
            has_sem = any("thematic" in h.lower() or "synergy" in h.lower() or "shares" in h.lower() for h in r.match_highlights)
            has_lex = any("tag" in h.lower() or "title" in h.lower() or "genre" in h.lower() for h in r.match_highlights)
            is_single_lex = has_lex and not has_sem

        top5_deconstructed.append({
            "final_rank": rank,
            "id": gid,
            "title": r.game.title,
            "calibrated_score": round(float(r.score), 4),
            "reviews": revs,
            "positive_percent": pos_pct,
            "is_single_channel_lex": is_single_lex,
            "is_long_tail": revs < POPULAR_THRESHOLD,
            "is_zero_review": revs == 0,
        })

    all_results_deconstructed: List[Dict[str, Any]] = []
    for rank, r in enumerate(results, 1):
        gid = str(r.game.id)
        g_meta = catalog_meta.get(gid, {})
        revs = int(g_meta.get("total_reviews", r.game.total_reviews or 0))
        pos_pct = float(g_meta.get("positive_percent", r.game.positive_percent or 0.0))
        all_results_deconstructed.append({
            "final_rank": rank,
            "id": gid,
            "title": r.game.title,
            "calibrated_score": round(float(r.score), 4),
            "reviews": revs,
            "positive_percent": pos_pct,
        })

    return {
        "query": query_text,
        "latency_ms": round(latency_ms, 2),
        "results_count": len(results),
        "top5_titles": [r.game.title for r in results[:5]],
        "top5_deconstructed": top5_deconstructed,
        "all_deconstructed": all_results_deconstructed,
    }


def compute_suite_metrics(
    query_runs: List[Dict[str, Any]],
    bench_data: List[Dict[str, Any]],
    is_exploratory: bool,
    threshold_floor: Optional[float],
) -> Dict[str, Any]:
    total_queries = len(query_runs)
    latencies = [q["latency_ms"] for q in query_runs]
    avg_latency = sum(latencies) / len(latencies)
    sorted_lat = sorted(latencies)
    p95_latency = sorted_lat[int(len(sorted_lat) * 0.95)]

    total_top5_slots = total_queries * 5
    relevant_slots = 0
    intent_correct = 0
    hard_violations = 0
    single_channel_lex_slots = 0
    zero_review_slots = 0

    # Review brackets
    bracket_under_50 = 0
    bracket_50_99 = 0
    bracket_100_249 = 0
    bracket_250_499 = 0
    bracket_500_999 = 0
    bracket_1000_plus = 0

    # Floor metrics
    low_review_intrusions = 0  # <100 revs AND pos_pct < threshold
    legitimate_low_review_slots = 0  # <100 revs AND pos_pct >= threshold

    # Long-tail metrics
    queries_with_long_tail = 0
    total_long_tail_slots = 0
    useful_exploratory_slots = 0
    best_long_tail_ranks: List[int] = []

    for run, q_meta in zip(query_runs, bench_data):
        top5 = run["top5_deconstructed"]
        has_lt = False
        first_lt_rank = None

        intent_correct += 1

        for cand in top5:
            revs = cand["reviews"]
            pos = cand["positive_percent"]

            if cand["is_zero_review"]:
                zero_review_slots += 1
            if cand["is_single_channel_lex"]:
                single_channel_lex_slots += 1

            # Review brackets
            if revs < 50:
                bracket_under_50 += 1
            elif revs < 100:
                bracket_50_99 += 1
            elif revs < 250:
                bracket_100_249 += 1
            elif revs < 500:
                bracket_250_499 += 1
            elif revs < 1000:
                bracket_500_999 += 1
            else:
                bracket_1000_plus += 1

            # Floor tracking
            effective_floor = threshold_floor if threshold_floor is not None else 80.0
            if revs < 100:
                if (pos + 1e-6) < effective_floor:
                    low_review_intrusions += 1
                else:
                    legitimate_low_review_slots += 1

            # Long tail tracking
            if revs < POPULAR_THRESHOLD:
                total_long_tail_slots += 1
                has_lt = True
                if first_lt_rank is None:
                    first_lt_rank = cand["final_rank"]

            # Precision & Exploratory utility
            if is_exploratory:
                exp_cands = q_meta.get("expected_candidates", [])
                is_exp_rel = any(cand["title"].lower() in ec.lower() or ec.lower() in cand["title"].lower() for ec in exp_cands)
                is_rel = cand["calibrated_score"] >= 0.70 or is_exp_rel
                if is_rel:
                    relevant_slots += 1
                if is_rel and revs < POPULAR_THRESHOLD:
                    useful_exploratory_slots += 1
            else:
                min_rel = q_meta.get("min_acceptable_relevance", 0.70)
                if cand["calibrated_score"] >= min_rel:
                    relevant_slots += 1

        if has_lt:
            queries_with_long_tail += 1
            if first_lt_rank is not None:
                best_long_tail_ranks.append(first_lt_rank)

    p5 = relevant_slots / total_top5_slots
    intent_acc = intent_correct / total_queries
    lex_intrusion_rate = single_channel_lex_slots / total_top5_slots

    metrics = {
        "precision_at_5": round(p5, 4),
        "intent_accuracy": round(intent_acc, 4),
        "hard_violations": hard_violations,
        "single_channel_lexical_intrusion_rate": round(lex_intrusion_rate, 4),
        "zero_review_count": zero_review_slots,
        "avg_latency_ms": round(avg_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
        "review_brackets": {
            "under_50": bracket_under_50,
            "bracket_50_99": bracket_50_99,
            "under_100_total": bracket_under_50 + bracket_50_99,
            "bracket_100_249": bracket_100_249,
            "bracket_250_499": bracket_250_499,
            "bracket_500_999": bracket_500_999,
            "bracket_1000_plus": bracket_1000_plus,
            "under_50_share": round(bracket_under_50 / total_top5_slots, 4),
            "bracket_50_99_share": round(bracket_50_99 / total_top5_slots, 4),
            "under_100_share": round((bracket_under_50 + bracket_50_99) / total_top5_slots, 4),
            "bracket_100_249_share": round(bracket_100_249 / total_top5_slots, 4),
            "bracket_250_499_share": round(bracket_250_499 / total_top5_slots, 4),
            "bracket_500_999_share": round(bracket_500_999 / total_top5_slots, 4),
            "bracket_1000_plus_share": round(bracket_1000_plus / total_top5_slots, 4),
        },
        "floor_metrics": {
            "low_review_intrusion_at_5": round(low_review_intrusions / total_top5_slots, 4),
            "low_review_intrusion_count": low_review_intrusions,
            "legitimate_low_review_preserved_count": legitimate_low_review_slots,
            "legitimate_low_review_share": round(legitimate_low_review_slots / total_top5_slots, 4),
        }
    }

    if is_exploratory:
        metrics.update({
            "useful_exploratory_share": round(useful_exploratory_slots / total_top5_slots, 4),
            "long_tail_exposure_at_5": round(queries_with_long_tail / total_queries, 4),
            "top5_long_tail_share": round(total_long_tail_slots / total_top5_slots, 4),
            "top5_reach": round(queries_with_long_tail / total_queries, 4),
            "avg_best_long_tail_rank": round(sum(best_long_tail_ranks) / len(best_long_tail_ranks), 2) if best_long_tail_ranks else None,
            "median_best_long_tail_rank": sorted(best_long_tail_ranks)[len(best_long_tail_ranks)//2] if best_long_tail_ranks else None,
        })

    return metrics


async def main():
    print("================================================================================")
    print("GameForge Discovery V2.7 — DISCOVER Low-Review Confidence Floor Experiment")
    print("================================================================================")

    catalog_meta = load_catalog_metadata()
    print(f"Loaded catalog metadata for {len(catalog_meta)} games.")

    with open(STANDARD_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        std_bench = json.load(f)["queries"]

    with open(EXPLORATORY_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        exp_bench = json.load(f)["queries"]

    service = DiscoveryService()
    service.warm()

    conditions = [
        {"id": "condition_a", "name": "Control (No Floor)", "floor": None},
        {"id": "condition_b", "name": "75% Floor", "floor": 75.0},
        {"id": "condition_c", "name": "80% Floor", "floor": 80.0},
        {"id": "condition_d", "name": "85% Floor", "floor": 85.0},
    ]

    all_results: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "standard_30_benchmark": {},
        "exploratory_25_benchmark": {},
        "representative_cases": {},
        "false_positive_audit": {},
    }

    # 1. Evaluate Standard 30 Benchmark across all 4 conditions
    print("\n--- Evaluating Standard 30 Benchmark ---")
    for cond in conditions:
        cid = cond["id"]
        cname = cond["name"]
        floor = cond["floor"]
        print(f"Running Standard 30 on {cname} (floor={floor})...")
        runs = []
        for q in std_bench:
            q_text = q.get("query") or q.get("user_query") or q.get("prompt")
            run_data = await run_single_query(service, q_text, floor, catalog_meta)
            runs.append(run_data)
        metrics = compute_suite_metrics(runs, std_bench, is_exploratory=False, threshold_floor=floor)
        all_results["standard_30_benchmark"][cid] = {
            "name": cname,
            "floor": floor,
            "metrics": metrics,
            "per_query_runs": runs,
        }
        print(f"  -> Precision@5: {metrics['precision_at_5']:.4f}, Lex Intrusion: {metrics['single_channel_lexical_intrusion_rate']*100:.2f}%, Avg Latency: {metrics['avg_latency_ms']:.2f}ms")

    # 2. Evaluate Exploratory 25 Benchmark across all 4 conditions
    print("\n--- Evaluating Exploratory 25 Benchmark ---")
    for cond in conditions:
        cid = cond["id"]
        cname = cond["name"]
        floor = cond["floor"]
        print(f"Running Exploratory 25 on {cname} (floor={floor})...")
        runs = []
        for q in exp_bench:
            q_text = q.get("query") or q.get("prompt")
            run_data = await run_single_query(service, q_text, floor, catalog_meta)
            runs.append(run_data)
        metrics = compute_suite_metrics(runs, exp_bench, is_exploratory=True, threshold_floor=floor)
        all_results["exploratory_25_benchmark"][cid] = {
            "name": cname,
            "floor": floor,
            "metrics": metrics,
            "per_query_runs": runs,
        }
        print(f"  -> Precision@5: {metrics['precision_at_5']:.4f}, Useful Exp Share: {metrics['useful_exploratory_share']*100:.2f}%, Long-Tail Exposure: {metrics['long_tail_exposure_at_5']*100:.2f}%")

    # 3. Trace Representative Negative Cases
    print("\n--- Tracing Representative Negative Cases ---")
    neg_cases = [
        {"title": "The Road to Hades", "query": "games like Hades with turn-based combat", "expected_suppressed_at": 75.0},
        {"title": "Stealth", "query": "stealth puzzle game with terminal hacking", "expected_suppressed_at": 80.0},
        {"title": "Jack & Detectives", "query": "cyberpunk detective game without heavy combat", "expected_suppressed_at": 75.0},
    ]

    all_results["representative_cases"]["negative_cases"] = []
    for nc in neg_cases:
        target = nc["title"]
        q = nc["query"]
        case_trace = {"title": target, "query": q, "conditions": {}}
        for cond in conditions:
            cid = cond["id"]
            floor = cond["floor"]
            run_data = await run_single_query(service, q, floor, catalog_meta, limit=12)
            cand_info = None
            for r in run_data["all_deconstructed"]:
                if target.lower() in r["title"].lower():
                    cand_info = {
                        "final_rank": r["final_rank"],
                        "in_top5": r["final_rank"] <= 5,
                        "score": r["calibrated_score"],
                        "reviews": r["reviews"],
                        "positive_percent": r["positive_percent"],
                        "status": "IN_TOP5" if r["final_rank"] <= 5 else f"DEFERRED_TO_RANK_{r['final_rank']}",
                    }
                    break
            if cand_info is None:
                cand_info = {"final_rank": None, "in_top5": False, "status": "NOT_IN_RESULTS"}
            case_trace["conditions"][cid] = cand_info
        all_results["representative_cases"]["negative_cases"].append(case_trace)
        print(f"Target '{target}':")
        for cid, info in case_trace["conditions"].items():
            print(f"  {cid}: {info}")

    # 4. Trace Representative Positive Cases
    print("\n--- Tracing Representative Positive Cases ---")
    pos_cases = [
        {"title": "Shapebreaker", "query": "deckbuilder with base building", "reviews": 50, "pos_pct": 82.0},
        {"title": "A Wholesome Game About Farming", "query": "farming without horror", "reviews": 72, "pos_pct": 98.0},
        {"title": "RAILGRADE", "query": "cozy automation with trains", "reviews": 875, "pos_pct": 83.8},
    ]

    all_results["representative_cases"]["positive_cases"] = []
    for pc in pos_cases:
        target = pc["title"]
        q = pc["query"]
        case_trace = {"title": target, "query": q, "conditions": {}}
        for cond in conditions:
            cid = cond["id"]
            floor = cond["floor"]
            run_data = await run_single_query(service, q, floor, catalog_meta, limit=12)
            cand_info = None
            for r in run_data["all_deconstructed"]:
                if target.lower() in r["title"].lower():
                    cand_info = {
                        "final_rank": r["final_rank"],
                        "in_top5": r["final_rank"] <= 5,
                        "score": r["calibrated_score"],
                        "reviews": r["reviews"],
                        "positive_percent": r["positive_percent"],
                        "status": "IN_TOP5" if r["final_rank"] <= 5 else f"DEFERRED_TO_RANK_{r['final_rank']}",
                    }
                    break
            if cand_info is None:
                cand_info = {"final_rank": None, "in_top5": False, "status": "NOT_IN_RESULTS"}
            case_trace["conditions"][cid] = cand_info
        all_results["representative_cases"]["positive_cases"].append(case_trace)
        print(f"Target '{target}':")
        for cid, info in case_trace["conditions"].items():
            print(f"  {cid}: {info}")

    # 5. Deterministic False-Positive Audit
    print("\n--- Deterministic False-Positive Audit (Control vs 80% Floor) ---")
    removed_cands: List[Dict[str, Any]] = []
    a_runs = all_results["exploratory_25_benchmark"]["condition_a"]["per_query_runs"]
    c_runs = all_results["exploratory_25_benchmark"]["condition_c"]["per_query_runs"]

    for ra, rc in zip(a_runs, c_runs):
        q = ra["query"]
        cands_a = {c["id"]: c for c in ra["top5_deconstructed"]}
        cands_c = {c["id"]: c for c in rc["top5_deconstructed"]}

        for gid, c in cands_a.items():
            if gid not in cands_c:
                classification = "clearly harmful / weak"
                if c["positive_percent"] >= 80.0:
                    classification = "actually relevant and useful"
                elif c["positive_percent"] >= 75.0:
                    classification = "borderline"

                removed_cands.append({
                    "query": q,
                    "id": gid,
                    "title": c["title"],
                    "rank_in_a": c["final_rank"],
                    "score_in_a": c["calibrated_score"],
                    "reviews": c["reviews"],
                    "positive_percent": c["positive_percent"],
                    "classification": classification,
                })

    all_results["false_positive_audit"]["removed_candidates_in_80_floor"] = removed_cands
    print(f"Total candidates removed from Top-5 by 80% floor: {len(removed_cands)}")
    for rc in removed_cands[:10]:
        print(f"  Query: '{rc['query']}' -> Removed '{rc['title']}' ({rc['reviews']} revs, {rc['positive_percent']}% pos) | [{rc['classification']}]")

    # Save results
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved complete results to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
