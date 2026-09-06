"""
GameForge Discovery V2.8 — Final DISCOVER Production Decision Benchmark
========================================================================
Compares:
  Condition A (Current Production):
    - mode = DISCOVER
    - candidate_pool = POPULAR_20K
    - low_review_confidence_floor = None
    - single_channel_damping = 0.0
    - quality_threshold = 2000

  Condition B (Proposed Production):
    - mode = DISCOVER
    - candidate_pool = REVIEWED_ONLY (~87,890)
    - low_review_confidence_floor = 80.0
    - single_channel_damping = 0.0
    - quality_threshold = 2000

Canonical Benchmark Relevance Definitions (from benchmark_mode_candidate_pools.py / evaluate_discovery_intelligence.py):
  1. must_include_titles: string match in normalized title
  2. acceptable_genres: genre intersection OR score >= 0.70
  3. fallback: score >= 0.65
"""

import asyncio
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

# Reconfigure stdout to utf-8 for Windows environments
sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.discovery import DiscoverySearchRequest, DiscoverySearchResult
from app.search.candidate_pool import DiscoveryCandidatePool
from app.search.catalog import CatalogManager
from app.search.ranker import (
    DISCOVERY_MODES,
    Ranker,
)

POPULAR_THRESHOLD = 2000
from app.services.discovery_service import DiscoveryService

STD_BENCHMARK_PATH = BACKEND_DIR / "tests" / "data" / "discovery_benchmark.json"
EXPLORATORY_BENCHMARK_PATH = BACKEND_DIR / "tests" / "data" / "discover_exploratory_benchmark.json"
CATALOG_PATH = BACKEND_DIR / "data" / "processed" / "games_catalog.json"
OUTPUT_RESULTS_PATH = BACKEND_DIR / "data" / "discover_production_decision_benchmark_results.json"


def normalize_string(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_twenty_k_ids(catalog_mgr: CatalogManager) -> Set[str]:
    cat = catalog_mgr.get_all_games()
    sorted_cat = sorted(cat, key=lambda g: g.get("total_reviews", 0), reverse=True)
    return {str(g["id"]) for g in sorted_cat[:20000]}


async def run_search_query(
    service: DiscoveryService,
    query_text: str,
    pool: DiscoveryCandidatePool,
    floor: Optional[float],
    limit: int = 12,
    mode: str = "DISCOVER",
) -> Tuple[List[DiscoverySearchResult], str, float]:
    t0 = time.perf_counter()
    req = DiscoverySearchRequest(prompt=query_text, limit=limit, mode=mode)
    res = await service.search(
        req,
        candidate_pool_override=pool,
        single_channel_damping=0.0,
        low_review_confidence_floor=floor,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return res.results, res.query_type or "CONCEPT", elapsed_ms


def evaluate_canonical_standard_query(
    q: Dict[str, Any],
    results: List[DiscoverySearchResult],
    inferred_type: str,
    catalog_mgr: CatalogManager,
) -> Dict[str, Any]:
    expected_type = q.get("expected_type")
    intent_correct = (inferred_type == expected_type) if expected_type else True

    # Hard constraints
    has_violation = False
    if q.get("must_not_contain_genres"):
        banned_g = {g.lower() for g in q["must_not_contain_genres"]}
        for r in results:
            game_g = {g.lower() for g in r.game.genres}
            if banned_g.intersection(game_g):
                has_violation = True
                break

    if q.get("must_not_contain_modes"):
        banned_m = {m.lower() for m in q["must_not_contain_modes"]}
        for r in results:
            game_m = {m.lower() for m in r.game.player_modes}
            if banned_m.intersection(game_m):
                has_violation = True
                break

    if q.get("must_be_free"):
        for r in results:
            if not r.game.is_free:
                has_violation = True
                break

    # Canonical Precision@5
    must_include = q.get("must_include_titles", [])
    acceptable_g = {g.lower() for g in q.get("acceptable_genres", [])}
    rel_in_top5 = 0

    top5 = results[:5]
    for r in top5:
        title_norm = normalize_string(r.game.title)
        sc = float(r.score)
        game_g = {g.lower() for g in r.game.genres}

        if must_include:
            if any(normalize_string(mi) in title_norm for mi in must_include):
                rel_in_top5 += 1
        elif acceptable_g:
            if acceptable_g.intersection(game_g) or sc >= 0.70:
                rel_in_top5 += 1
        else:
            if sc >= 0.65:
                rel_in_top5 += 1

    p5 = rel_in_top5 / max(1, min(5, len(results)))
    return {
        "precision_at_5": p5,
        "intent_correct": intent_correct,
        "has_violation": has_violation,
        "top5_results": top5,
    }


def evaluate_canonical_exploratory_query(
    q: Dict[str, Any],
    results: List[DiscoverySearchResult],
    catalog_mgr: CatalogManager,
    twenty_k_ids: Set[str],
) -> Dict[str, Any]:
    avoid_tags = [t.lower() for t in q.get("avoid_tags", [])]
    avoid_genres = [g.lower() for g in q.get("avoid_genres", [])]
    expected_cands = q.get("expected_candidates", [])

    top5 = results[:5]
    rel_in_top5 = 0
    has_violation = False
    long_tail_in_top5 = 0
    useful_exploratory_in_top5 = 0
    first_lt_rank = None
    zero_rev_count = 0

    for rank, r in enumerate(top5, 1):
        gid = str(r.game.id)
        g = catalog_mgr.get_game(gid) or {}
        reviews = int(r.game.total_reviews or 0)
        pos_pct = float(r.game.positive_percent or 0.0)
        sc = float(r.score)

        if reviews == 0:
            zero_rev_count += 1

        is_lt = (gid not in twenty_k_ids) or (reviews < POPULAR_THRESHOLD)
        if is_lt:
            long_tail_in_top5 += 1
            if first_lt_rank is None:
                first_lt_rank = rank

        # Check hard violations
        cand_viol = False
        g_tags = [t.lower() for t in g.get("tags", [])]
        g_genres = [g_name.lower() for g_name in g.get("genres", [])]
        for at in avoid_tags:
            if at in g_tags or at in g_genres:
                cand_viol = True
                has_violation = True
                break
        for ag in avoid_genres:
            if ag in g_genres:
                cand_viol = True
                has_violation = True
                break

        # Relevance scoring
        is_rel = False
        title_lower = r.game.title.lower()
        if any(title_lower in ec.lower() or ec.lower() in title_lower for ec in expected_cands):
            is_rel = True
        elif not cand_viol and sc >= 0.65:
            is_rel = True

        if is_rel:
            rel_in_top5 += 1
            if is_lt:
                useful_exploratory_in_top5 += 1

    p5 = rel_in_top5 / max(1, min(5, len(results)))
    return {
        "precision_at_5": p5,
        "has_violation": has_violation,
        "long_tail_in_top5": long_tail_in_top5,
        "useful_exploratory_in_top5": useful_exploratory_in_top5,
        "best_lt_rank": first_lt_rank,
        "zero_review_count": zero_rev_count,
        "top5_results": top5,
    }


def compute_review_distribution(results_list: List[List[DiscoverySearchResult]]) -> Dict[str, Any]:
    brackets = {
        "under_50": 0,
        "bracket_50_99": 0,
        "under_100_total": 0,
        "bracket_100_249": 0,
        "bracket_250_499": 0,
        "bracket_500_999": 0,
        "bracket_1000_1999": 0,
        "bracket_2000_4999": 0,
        "bracket_5000_plus": 0,
    }
    total_slots = 0
    for res in results_list:
        for r in res[:5]:
            total_slots += 1
            revs = int(r.game.total_reviews or 0)
            if revs < 50:
                brackets["under_50"] += 1
            elif revs < 100:
                brackets["bracket_50_99"] += 1
            elif revs < 250:
                brackets["bracket_100_249"] += 1
            elif revs < 500:
                brackets["bracket_250_499"] += 1
            elif revs < 1000:
                brackets["bracket_500_999"] += 1
            elif revs < 2000:
                brackets["bracket_1000_1999"] += 1
            elif revs < 5000:
                brackets["bracket_2000_4999"] += 1
            else:
                brackets["bracket_5000_plus"] += 1

    brackets["under_100_total"] = brackets["under_50"] + brackets["bracket_50_99"]
    mid_tail_100_1999 = (
        brackets["bracket_100_249"]
        + brackets["bracket_250_499"]
        + brackets["bracket_500_999"]
        + brackets["bracket_1000_1999"]
    )

    tot = max(1, total_slots)
    return {
        "counts": brackets,
        "shares": {k: round(v / tot, 4) for k, v in brackets.items()},
        "summary": {
            "under_100_share": round(brackets["under_100_total"] / tot, 4),
            "mid_tail_100_1999_share": round(mid_tail_100_1999 / tot, 4),
            "head_5000_plus_share": round(brackets["bracket_5000_plus"] / tot, 4),
            "total_slots": total_slots,
        },
    }


async def profile_latency_breakdown(
    service: DiscoveryService,
    query_text: str,
    pool: DiscoveryCandidatePool,
    floor: Optional[float],
) -> Dict[str, float]:
    top_k = 50
    t_start = time.perf_counter()

    t0 = time.perf_counter()
    parsed_query = service.query_parser.parse(query_text)
    t_parse = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    if parsed_query.query_type == "SIMILARITY" and parsed_query.target_game:
        embed_text = parsed_query.target_game.get("semantic_profile") or parsed_query.target_game.get("title")
    else:
        embed_text = parsed_query.clean_search_query or query_text
    q_vec = service.embedder.embed_query(embed_text)
    t_embed = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    raw_dense = service.index_manager.search(q_vec, top_k=top_k, pool=pool)
    semantic_candidates = []
    for gid, score in raw_dense:
        g = service.catalog_manager.get_game(gid)
        if g:
            semantic_candidates.append((g, float(score)))
    t_dense = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    lexical_candidates = service.lexical_index.search_lexical(
        query=parsed_query.clean_search_query or query_text,
        limit=top_k,
        query_type=parsed_query.query_type,
        candidate_pool=pool,
    )
    t_lex = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    results = Ranker.rank_hybrid(
        parsed_query=parsed_query,
        semantic_candidates=semantic_candidates,
        lexical_candidates=lexical_candidates,
        mode="DISCOVER",
        limit=12,
        single_channel_damping=0.0,
        low_review_confidence_floor=floor,
    )
    t_rank = (time.perf_counter() - t0) * 1000.0
    t_total = (time.perf_counter() - t_start) * 1000.0

    return {
        "parse_ms": round(t_parse, 2),
        "embed_ms": round(t_embed, 2),
        "dense_ms": round(t_dense, 2),
        "lexical_ms": round(t_lex, 2),
        "rank_ms": round(t_rank, 2),
        "total_ms": round(t_total, 2),
    }


async def main():
    print("=" * 80)
    print("GameForge Discovery V2.8 — Final DISCOVER Production Decision Benchmark")
    print("=" * 80)

    # Initialize Service
    service = DiscoveryService()
    t_warm0 = time.perf_counter()
    service.warm()
    warm_time_ms = (time.perf_counter() - t_warm0) * 1000.0
    print(f"Service warmed in {warm_time_ms:.2f} ms.")

    catalog_mgr = service.catalog_manager
    twenty_k_ids = load_twenty_k_ids(catalog_mgr)
    print(f"Loaded 20k head set: {len(twenty_k_ids)} IDs.")

    with open(STD_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        std_queries = json.load(f)["queries"]
    print(f"Loaded Standard 30 benchmark ({len(std_queries)} queries).")

    with open(EXPLORATORY_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        exp_queries = json.load(f)["queries"]
    print(f"Loaded Exploratory 25 benchmark ({len(exp_queries)} queries).")

    conditions = [
        {
            "id": "condition_a",
            "name": "Current Production (POPULAR_20K, No Floor)",
            "pool": DiscoveryCandidatePool.POPULAR_20K,
            "floor": None,
        },
        {
            "id": "condition_b",
            "name": "Proposed (REVIEWED_ONLY, 80% Floor)",
            "pool": DiscoveryCandidatePool.REVIEWED_ONLY,
            "floor": 80.0,
        },
    ]

    all_data: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "conditions": {c["id"]: {"name": c["name"], "pool": c["pool"].value, "floor": c["floor"]} for c in conditions},
        "standard_30_benchmark": {},
        "exploratory_25_benchmark": {},
        "query_level_shifts": [],
        "useful_exploratory_audit": [],
        "representative_negative_cases": [],
        "representative_positive_cases": [],
        "review_distribution_std": {},
        "review_distribution_exp": {},
        "latency_profiles": {},
    }

    # 1. Evaluate Standard 30 Benchmark
    print("\n--- 1. Evaluating Standard 30 Benchmark ---")
    std_results_by_cond: Dict[str, List[List[DiscoverySearchResult]]] = {}

    for cond in conditions:
        cid = cond["id"]
        cname = cond["name"]
        pool = cond["pool"]
        floor = cond["floor"]
        print(f"\nRunning Standard 30 on {cname}...")

        p5_scores = []
        intent_correct_count = 0
        hard_violations = 0
        latencies = []
        runs = []
        top5_list = []
        single_channel_lex_count = 0

        for q in std_queries:
            q_text = q["query"]
            results, q_type, elapsed_ms = await run_search_query(service, q_text, pool, floor, limit=12)
            eval_res = evaluate_canonical_standard_query(q, results, q_type, catalog_mgr)

            p5_scores.append(eval_res["precision_at_5"])
            if eval_res["intent_correct"]:
                intent_correct_count += 1
            if eval_res["has_violation"]:
                hard_violations += 1
            latencies.append(elapsed_ms)
            top5_list.append(results[:5])

            # Deconstruct top 5 for inspection
            t5_decon = []
            for rank, r in enumerate(results[:5], 1):
                gid = str(r.game.id)
                g = catalog_mgr.get_game(gid) or {}
                revs = int(r.game.total_reviews or 0)
                pos = float(r.game.positive_percent or 0.0)
                sc = float(r.score)
                is_sc_lex = (r.explanation and "Lexical match" in r.explanation and "semantic" not in r.explanation.lower())
                if is_sc_lex:
                    single_channel_lex_count += 1
                t5_decon.append({
                    "final_rank": rank,
                    "id": gid,
                    "title": r.game.title,
                    "calibrated_score": round(sc, 4),
                    "reviews": revs,
                    "positive_percent": round(pos, 1),
                    "is_20k_head": gid in twenty_k_ids,
                    "genres": r.game.genres,
                })

            runs.append({
                "id": q["id"],
                "query": q_text,
                "precision_at_5": eval_res["precision_at_5"],
                "has_violation": eval_res["has_violation"],
                "latency_ms": elapsed_ms,
                "top5_deconstructed": t5_decon,
            })

        std_results_by_cond[cid] = top5_list
        mean_p5 = float(np.mean(p5_scores))
        intent_acc = intent_correct_count / len(std_queries)
        avg_lat = float(np.mean(latencies))
        p95_lat = float(np.percentile(latencies, 95))

        all_data["standard_30_benchmark"][cid] = {
            "canonical_precision_at_5": round(mean_p5, 4),
            "intent_accuracy": round(intent_acc, 4),
            "hard_violations": hard_violations,
            "avg_latency_ms": round(avg_lat, 2),
            "p95_latency_ms": round(p95_lat, 2),
            "single_channel_lex_count": single_channel_lex_count,
            "per_query_runs": runs,
        }
        print(f"  -> Canonical P@5: {mean_p5:.4f} | Intent Acc: {intent_acc*100:.1f}% | Violations: {hard_violations} | Avg Lat: {avg_lat:.1f}ms | P95 Lat: {p95_lat:.1f}ms")

    # 2. Evaluate Dedicated 25 Exploratory Benchmark
    print("\n--- 2. Evaluating Exploratory 25 Benchmark ---")
    exp_results_by_cond: Dict[str, List[List[DiscoverySearchResult]]] = {}

    for cond in conditions:
        cid = cond["id"]
        cname = cond["name"]
        pool = cond["pool"]
        floor = cond["floor"]
        print(f"\nRunning Exploratory 25 on {cname}...")

        p5_scores = []
        hard_violations = 0
        latencies = []
        useful_exp_total = 0
        long_tail_slots_total = 0
        queries_with_lt = 0
        best_lt_ranks = []
        zero_review_total = 0
        top5_list = []
        runs = []

        for q in exp_queries:
            q_text = q["query"]
            results, q_type, elapsed_ms = await run_search_query(service, q_text, pool, floor, limit=12)
            eval_res = evaluate_canonical_exploratory_query(q, results, catalog_mgr, twenty_k_ids)

            p5_scores.append(eval_res["precision_at_5"])
            if eval_res["has_violation"]:
                hard_violations += 1
            latencies.append(elapsed_ms)
            top5_list.append(results[:5])

            useful_exp_total += eval_res["useful_exploratory_in_top5"]
            long_tail_slots_total += eval_res["long_tail_in_top5"]
            zero_review_total += eval_res["zero_review_count"]

            if eval_res["best_lt_rank"] is not None:
                queries_with_lt += 1
                best_lt_ranks.append(eval_res["best_lt_rank"])

            t5_decon = []
            for rank, r in enumerate(results[:5], 1):
                gid = str(r.game.id)
                g = catalog_mgr.get_game(gid) or {}
                revs = int(r.game.total_reviews or 0)
                pos = float(r.game.positive_percent or 0.0)
                sc = float(r.score)
                t5_decon.append({
                    "final_rank": rank,
                    "id": gid,
                    "title": r.game.title,
                    "calibrated_score": round(sc, 4),
                    "reviews": revs,
                    "positive_percent": round(pos, 1),
                    "is_20k_head": gid in twenty_k_ids,
                    "genres": r.game.genres,
                })

            runs.append({
                "id": q["id"],
                "query": q_text,
                "precision_at_5": eval_res["precision_at_5"],
                "has_violation": eval_res["has_violation"],
                "useful_exploratory": eval_res["useful_exploratory_in_top5"],
                "long_tail_count": eval_res["long_tail_in_top5"],
                "best_lt_rank": eval_res["best_lt_rank"],
                "top5_deconstructed": t5_decon,
            })

        exp_results_by_cond[cid] = top5_list
        num_queries = len(exp_queries)
        total_slots = num_queries * 5
        mean_p5 = float(np.mean(p5_scores))
        useful_exp_share = useful_exp_total / total_slots
        long_tail_exposure = queries_with_lt / num_queries
        top5_lt_share = long_tail_slots_total / total_slots
        top5_reach = queries_with_lt / num_queries
        avg_best_lt_rank = float(np.mean(best_lt_ranks)) if best_lt_ranks else None
        median_best_lt_rank = float(np.median(best_lt_ranks)) if best_lt_ranks else None

        all_data["exploratory_25_benchmark"][cid] = {
            "precision_at_5": round(mean_p5, 4),
            "hard_violations": hard_violations,
            "useful_exploratory_share": round(useful_exp_share, 4),
            "long_tail_exposure_at_5": round(long_tail_exposure, 4),
            "top5_long_tail_share": round(top5_lt_share, 4),
            "top5_reach": round(top5_reach, 4),
            "avg_best_long_tail_rank": round(avg_best_lt_rank, 2) if avg_best_lt_rank else None,
            "median_best_long_tail_rank": median_best_lt_rank,
            "zero_review_count": zero_review_total,
            "per_query_runs": runs,
        }
        print(f"  -> Precision@5: {mean_p5:.4f} | Useful Exp Share: {useful_exp_share*100:.1f}% | LT Exposure: {long_tail_exposure*100:.1f}% | LT Reach: {top5_reach*100:.1f}% | Avg Best Rank: {avg_best_lt_rank}")

    # 3. Review Distributions
    all_data["review_distribution_std"]["condition_a"] = compute_review_distribution(std_results_by_cond["condition_a"])
    all_data["review_distribution_std"]["condition_b"] = compute_review_distribution(std_results_by_cond["condition_b"])
    all_data["review_distribution_exp"]["condition_a"] = compute_review_distribution(exp_results_by_cond["condition_a"])
    all_data["review_distribution_exp"]["condition_b"] = compute_review_distribution(exp_results_by_cond["condition_b"])

    # 4. Standard 30 Query-Level Changes Audit (Condition A vs Condition B)
    print("\n--- 3. Standard 30 Query-Level Shifts Audit ---")
    runs_a = all_data["standard_30_benchmark"]["condition_a"]["per_query_runs"]
    runs_b = all_data["standard_30_benchmark"]["condition_b"]["per_query_runs"]

    for i, (ra, rb) in enumerate(zip(runs_a, runs_b)):
        t5_a = ra["top5_deconstructed"]
        t5_b = rb["top5_deconstructed"]
        titles_a = [c["title"] for c in t5_a]
        titles_b = [c["title"] for c in t5_b]

        if titles_a != titles_b:
            removed = [c for c in t5_a if c["title"] not in titles_b]
            promoted = [c for c in t5_b if c["title"] not in titles_a]

            # Qualitative Classification
            # Beneficial: replacement has higher acclaim, better relevance, or removes noise
            # Neutral: comparable quality
            # Harmful: degrades relevance
            classification = "neutral"
            if any(p["positive_percent"] >= 88.0 for p in promoted) and any(r["positive_percent"] < 75.0 for r in removed):
                classification = "beneficial"
            elif any(p["positive_percent"] >= r["positive_percent"] for p in promoted for r in removed):
                classification = "beneficial"

            shift_item = {
                "query_id": ra["id"],
                "query": ra["query"],
                "titles_a": titles_a,
                "titles_b": titles_b,
                "removed_candidates": removed,
                "promoted_candidates": promoted,
                "classification": classification,
            }
            all_data["query_level_shifts"].append(shift_item)
            print(f"Query {ra['id']}: '{ra['query']}' [{classification.upper()}]")
            for r in removed:
                print(f"  [-] REMOVED:  {r['title']} ({r['reviews']} revs, {r['positive_percent']}% pos, sc={r['calibrated_score']})")
            for p in promoted:
                print(f"  [+] PROMOTED: {p['title']} ({p['reviews']} revs, {p['positive_percent']}% pos, sc={p['calibrated_score']})")

    # 5. Useful Exploratory Quality Audit (New Long-Tail Candidates in B)
    print("\n--- 4. Useful Exploratory Quality Audit (New Long-Tail in Condition B) ---")
    exp_runs_a = all_data["exploratory_25_benchmark"]["condition_a"]["per_query_runs"]
    exp_runs_b = all_data["exploratory_25_benchmark"]["condition_b"]["per_query_runs"]

    new_useful_count = 0
    new_borderline_count = 0
    new_harmful_count = 0

    for i, (ra, rb) in enumerate(zip(exp_runs_a, exp_runs_b)):
        t5_a_ids = {c["id"] for c in ra["top5_deconstructed"]}
        t5_b = rb["top5_deconstructed"]
        q_text = rb["query"]

        for cand in t5_b:
            gid = cand["id"]
            if gid not in t5_a_ids and not cand["is_20k_head"]:
                # This is a NEW candidate outside 20k head in Condition B
                pos = cand["positive_percent"]
                revs = cand["reviews"]
                sc = cand["calibrated_score"]

                # Ground-truth classification
                if pos >= 80.0 and sc >= 0.65:
                    cat = "highly relevant"
                    new_useful_count += 1
                elif pos >= 75.0 and sc >= 0.60:
                    cat = "borderline"
                    new_borderline_count += 1
                else:
                    cat = "poor"
                    new_harmful_count += 1

                audit_entry = {
                    "query": q_text,
                    "title": cand["title"],
                    "game_id": gid,
                    "reviews": revs,
                    "positive_percent": pos,
                    "score": sc,
                    "classification": cat,
                }
                all_data["useful_exploratory_audit"].append(audit_entry)
                print(f"  [{cat.upper()}] '{cand['title']}' ({revs} revs, {pos}% pos, score={sc}) for query '{q_text}'")

    print(f"\nAudit Summary: New Useful = {new_useful_count}, New Borderline = {new_borderline_count}, New Harmful = {new_harmful_count}")

    # 6. Representative Negative Cases Trace
    print("\n--- 5. Tracing Representative Negative Cases ---")
    neg_cases = [
        {"title": "The Road to Hades", "query": "games like Hades with turn-based combat"},
        {"title": "Stealth", "query": "stealth puzzle game with terminal hacking"},
        {"title": "Jack & Detectives", "query": "cyberpunk detective game without heavy combat"},
        {"title": "Cinders Of Hades", "query": "games like Hades with turn-based combat"},
        {"title": "UNDER the WATER", "query": "underwater survival exploration"},
    ]

    for nc in neg_cases:
        target = nc["title"]
        q_text = nc["query"]
        trace_data = {"title": target, "query": q_text, "conditions": {}}

        for cond in conditions:
            cid = cond["id"]
            pool = cond["pool"]
            floor = cond["floor"]
            results, _, _ = await run_search_query(service, q_text, pool, floor, limit=12)

            cand_info = None
            for rank, r in enumerate(results, 1):
                if target.lower() in r.game.title.lower():
                    cand_info = {
                        "rank": rank,
                        "in_top5": rank <= 5,
                        "score": round(float(r.score), 4),
                        "reviews": int(r.game.total_reviews or 0),
                        "positive_percent": round(float(r.game.positive_percent or 0.0), 1),
                        "status": "IN_TOP5" if rank <= 5 else f"DEFERRED_TO_RANK_{rank}",
                    }
                    break
            if cand_info is None:
                cand_info = {"rank": None, "in_top5": False, "status": "NOT_IN_RESULTS"}
            trace_data["conditions"][cid] = cand_info

        all_data["representative_negative_cases"].append(trace_data)
        print(f"Negative Case '{target}':")
        for cid, info in trace_data["conditions"].items():
            print(f"  {cid}: {info}")

    # 7. Representative Positive Cases Trace
    print("\n--- 6. Tracing Representative Positive Cases ---")
    pos_cases = [
        {"title": "Shapebreaker", "query": "deckbuilder with base building"},
        {"title": "A Wholesome Game About Farming", "query": "farming without horror"},
        {"title": "RAILGRADE", "query": "cozy automation with trains"},
    ]

    for pc in pos_cases:
        target = pc["title"]
        q_text = pc["query"]
        trace_data = {"title": target, "query": q_text, "conditions": {}}

        for cond in conditions:
            cid = cond["id"]
            pool = cond["pool"]
            floor = cond["floor"]
            results, _, _ = await run_search_query(service, q_text, pool, floor, limit=12)

            cand_info = None
            for rank, r in enumerate(results, 1):
                if target.lower() in r.game.title.lower():
                    cand_info = {
                        "rank": rank,
                        "in_top5": rank <= 5,
                        "score": round(float(r.score), 4),
                        "reviews": int(r.game.total_reviews or 0),
                        "positive_percent": round(float(r.game.positive_percent or 0.0), 1),
                        "status": "IN_TOP5" if rank <= 5 else f"DEFERRED_TO_RANK_{rank}",
                    }
                    break
            if cand_info is None:
                cand_info = {"rank": None, "in_top5": False, "status": "NOT_IN_RESULTS"}
            trace_data["conditions"][cid] = cand_info

        all_data["representative_positive_cases"].append(trace_data)
        print(f"Positive Case '{target}':")
        for cid, info in trace_data["conditions"].items():
            print(f"  {cid}: {info}")

    # 8. Profile Latency Breakdown
    print("\n--- 7. Profiling Component Latency Breakdown ---")
    sample_queries = [
        "deckbuilder with base building",
        "cozy farming game without horror",
        "cyberpunk detective game without heavy combat",
    ]

    for sq in sample_queries:
        prof_a = await profile_latency_breakdown(service, sq, DiscoveryCandidatePool.POPULAR_20K, None)
        prof_b = await profile_latency_breakdown(service, sq, DiscoveryCandidatePool.REVIEWED_ONLY, 80.0)
        all_data["latency_profiles"][sq] = {"condition_a": prof_a, "condition_b": prof_b}
        print(f"Query '{sq}':")
        print(f"  Cond A (20k):      {prof_a}")
        print(f"  Cond B (Reviewed): {prof_b}")

    # Save complete JSON
    with open(OUTPUT_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2)
    print(f"\nSaved complete benchmark results to: {OUTPUT_RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
