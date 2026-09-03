"""
GameForge Discovery V2.6 — DISCOVER Single-Channel RRF Consistency Experiment Runner
Evaluates Condition A (20k), Condition B (Reviewed-Only), and Condition C (Reviewed-Only + 50% Lexical RRF Damping)
across Standard 30 and Exploratory 25 benchmarks.
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

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.discovery import DiscoverySearchRequest, DiscoverySearchResult
from app.search.candidate_pool import DiscoveryCandidatePool
from app.search.catalog import CatalogManager
from app.search.embedder import QueryEmbedder
from app.search.index import FAISSIndexManager
from app.search.lexical import normalize_string
from app.search.query_parser import ParsedQuery, QueryParser
from app.search.ranker import (
    DEFAULT_QUALITY_REVIEW_THRESHOLD,
    DIRECT_SCORE_WEIGHT,
    DISCOVERY_MODES,
    HIDDEN_GEM_MIN_REVIEWS,
    MAX_STEAM_REVIEWS_LOG,
    MAX_TOTAL_NEGATIVE_PENALTY,
    NEGATIVE_VECTOR_PENALTY,
    NOVELTY_WEIGHT,
    QUALITY_WEIGHT,
    QUERY_TYPE_WEIGHTS,
    RRF_K,
    RRF_SCORE_WEIGHT,
    SAME_FRANCHISE_PENALTY,
    SOFT_NEGATIVE_GENRE_PENALTY,
    SOFT_NEGATIVE_TAG_PENALTY,
    Ranker,
)
from app.services.discovery_service import DiscoveryService

STD_BENCHMARK_PATH = BACKEND_DIR / "tests" / "data" / "discovery_benchmark.json"
DISC_BENCHMARK_PATH = BACKEND_DIR / "tests" / "data" / "discover_exploratory_benchmark.json"
OUTPUT_RESULTS_PATH = BACKEND_DIR / "data" / "discover_rrf_damping_experiment_results.json"


def load_twenty_k_ids(catalog_mgr: CatalogManager) -> Set[str]:
    cat = catalog_mgr.get_all_games()
    sorted_cat = sorted(cat, key=lambda g: g.get("total_reviews", 0), reverse=True)
    return {str(g["id"]) for g in sorted_cat[:20000]}


def decompose_candidate_score(
    gid: str,
    game: Dict[str, Any],
    parsed_query: ParsedQuery,
    mode: str,
    sem_ranks: Dict[str, int],
    sem_scores: Dict[str, float],
    lex_ranks: Dict[str, int],
    lex_scores: Dict[str, float],
    twenty_k_ids: Set[str],
    single_channel_damping: float = 0.0,
) -> Dict[str, Any]:
    mode_adj = DISCOVERY_MODES.get(mode, DISCOVERY_MODES["BEST_MATCH"])
    q_type = parsed_query.query_type
    base_weights = QUERY_TYPE_WEIGHTS.get(q_type, QUERY_TYPE_WEIGHTS["CONCEPT"])

    w_sem = base_weights.w_sem
    w_lex = base_weights.w_lex
    w_pop = base_weights.w_pop

    reviews = game.get("total_reviews", 0)
    pos_pct = game.get("positive_percent", 0.0) / 100.0

    r_sem = sem_ranks.get(gid, 200)
    r_lex = lex_ranks.get(gid, 200)
    s_sem = sem_scores.get(gid, 0.0)
    s_lex = lex_scores.get(gid, 0.0)

    # RRF with optional single-channel damping
    lex_rrf_contrib = 1.0 / (RRF_K + r_lex)
    is_single_channel_lex = (gid not in sem_ranks) and (gid in lex_ranks)
    if single_channel_damping > 0.0 and gid not in sem_ranks:
        lex_rrf_contrib *= (1.0 - single_channel_damping)

    rrf_raw = (1.0 / (RRF_K + r_sem)) + lex_rrf_contrib
    norm_rrf = min(1.0, rrf_raw * (RRF_K / 2.0))

    # Popularity
    pop_signal = 0.0
    if reviews > 0:
        log_rev = min(1.0, math.log10(max(1, reviews)) / MAX_STEAM_REVIEWS_LOG)
        pop_signal = log_rev * pos_pct

    # Direct Score & Core Relevance
    direct_score = (w_sem * s_sem) + (w_lex * s_lex) + (w_pop * pop_signal)
    core_relevance = (DIRECT_SCORE_WEIGHT * direct_score) + (RRF_SCORE_WEIGHT * norm_rrf)

    # Quality & Novelty
    review_thresh = DEFAULT_QUALITY_REVIEW_THRESHOLD
    quality_score = QUALITY_WEIGHT * (pos_pct * min(1.0, reviews / review_thresh)) * mode_adj.quality_mult

    novelty_score = 0.0
    if reviews >= HIDDEN_GEM_MIN_REVIEWS and pos_pct >= 0.80:
        inv_log = max(0.0, 1.0 - (math.log10(max(10, reviews)) / 5.0))
        novelty_score = NOVELTY_WEIGHT * inv_log * mode_adj.novelty_mult

    # Negative Penalties
    negative_penalty = 0.0
    game_tags_lower = {t.lower() for t in game.get("tags", [])}
    game_genres = {g.lower() for g in game.get("genres", [])}
    for at in parsed_query.avoid_tags:
        if at.lower() in game_tags_lower:
            negative_penalty += SOFT_NEGATIVE_TAG_PENALTY
    for ag in parsed_query.avoid_genres:
        if ag.lower() in game_genres:
            negative_penalty += SOFT_NEGATIVE_GENRE_PENALTY
    negative_penalty = min(MAX_TOTAL_NEGATIVE_PENALTY, negative_penalty)

    rel_weighted = core_relevance * mode_adj.relevance_mult
    pre_diversity = max(0.0, rel_weighted + quality_score + novelty_score - negative_penalty)

    return {
        "game_id": gid,
        "title": game.get("title", ""),
        "total_reviews": reviews,
        "positive_percent": round(pos_pct * 100.0, 1),
        "is_20k_head": gid in twenty_k_ids,
        "is_single_channel_lex": is_single_channel_lex,
        "sem_rank": r_sem,
        "sem_score": round(s_sem, 4),
        "lex_rank": r_lex,
        "lex_score": round(s_lex, 4),
        "rrf_raw": round(rrf_raw, 6),
        "norm_rrf": round(norm_rrf, 4),
        "pop_signal": round(pop_signal, 4),
        "direct_score": round(direct_score, 4),
        "core_relevance": round(core_relevance, 4),
        "quality_score": round(quality_score, 4),
        "novelty_score": round(novelty_score, 4),
        "negative_penalty": round(negative_penalty, 4),
        "pre_diversity_score": round(pre_diversity, 4),
    }


async def run_single_query(
    query_text: str,
    pool: DiscoveryCandidatePool,
    single_channel_damping: float,
    service: DiscoveryService,
    catalog_mgr: CatalogManager,
    twenty_k_ids: Set[str],
    mode: str = "DISCOVER",
) -> Dict[str, Any]:
    top_k = 50
    t_start = time.perf_counter()

    # 1. Parse
    t0 = time.perf_counter()
    parsed_query = service.query_parser.parse(query_text)
    t_parse = time.perf_counter() - t0

    # 2. Dense
    t0 = time.perf_counter()
    if parsed_query.query_type == "SIMILARITY" and parsed_query.target_game:
        embed_text = parsed_query.target_game.get("semantic_profile") or parsed_query.target_game.get("title")
    else:
        embed_text = parsed_query.clean_search_query or query_text
    q_vec = service.embedder.embed_query(embed_text)
    t_embed = time.perf_counter() - t0

    t0 = time.perf_counter()
    raw_dense = service.index_manager.search(q_vec, top_k=top_k, pool=pool)
    dense_candidates = []
    sem_ranks: Dict[str, int] = {}
    sem_scores: Dict[str, float] = {}
    for rank, (gid, score) in enumerate(raw_dense, 1):
        g = catalog_mgr.get_game(gid)
        if g:
            dense_candidates.append((g, float(score)))
            sem_ranks[gid] = rank
            sem_scores[gid] = float(score)
    t_dense = time.perf_counter() - t0

    # 3. Lexical
    t0 = time.perf_counter()
    raw_lex = service.lexical_index.search_lexical(
        query=parsed_query.clean_search_query or query_text,
        limit=top_k,
        query_type=parsed_query.query_type,
        candidate_pool=pool,
    )
    lex_ranks: Dict[str, int] = {}
    lex_scores: Dict[str, float] = {}
    for rank, (game, score, details) in enumerate(raw_lex, 1):
        gid = str(game.get("id"))
        lex_ranks[gid] = rank
        lex_scores[gid] = float(score)
    t_lex = time.perf_counter() - t0

    # 4. RRF Candidate Funnel tracking
    t0 = time.perf_counter()
    candidate_pool: Dict[str, Dict[str, Any]] = {}
    rrf_map: Dict[str, float] = {}
    for g, _ in dense_candidates:
        gid = str(g.get("id"))
        candidate_pool[gid] = g
        rrf_map[gid] = rrf_map.get(gid, 0.0) + (1.0 / (RRF_K + sem_ranks.get(gid, 200)))

    for g, _, _ in raw_lex:
        gid = str(g.get("id"))
        candidate_pool[gid] = g
        r_l = lex_ranks.get(gid, 200)
        lex_contrib = 1.0 / (RRF_K + r_l)
        if single_channel_damping > 0.0 and gid not in sem_ranks:
            lex_contrib *= (1.0 - single_channel_damping)
        rrf_map[gid] = rrf_map.get(gid, 0.0) + lex_contrib

    sorted_rrf = sorted(rrf_map.items(), key=lambda x: x[1], reverse=True)
    rrf_gids = [gid for gid, _ in sorted_rrf]
    t_rrf = time.perf_counter() - t0

    # 5. Full Search Execution via DiscoveryService
    t0 = time.perf_counter()
    req = DiscoverySearchRequest(prompt=query_text, limit=50, mode=mode)
    search_res = await service.search(
        req,
        candidate_pool_override=pool,
        single_channel_damping=single_channel_damping,
    )
    t_rank = time.perf_counter() - t0
    t_total = time.perf_counter() - t_start

    # Deconstruct top 20 candidates
    top20_deconstructed = []
    for rank, r in enumerate(search_res.results[:20], 1):
        gid = str(r.game.id)
        g = catalog_mgr.get_game(gid) or {}
        decomp = decompose_candidate_score(
            gid=gid,
            game=g,
            parsed_query=parsed_query,
            mode=mode,
            sem_ranks=sem_ranks,
            sem_scores=sem_scores,
            lex_ranks=lex_ranks,
            lex_scores=lex_scores,
            twenty_k_ids=twenty_k_ids,
            single_channel_damping=single_channel_damping,
        )
        decomp["final_rank"] = rank
        decomp["calibrated_score"] = round(float(r.score), 4)
        top20_deconstructed.append(decomp)

    return {
        "query": query_text,
        "query_type": parsed_query.query_type,
        "mode": mode,
        "pool": pool.value,
        "damping": single_channel_damping,
        "dense_gids": [str(g.get("id")) for g, _ in dense_candidates],
        "lex_gids": [str(g.get("id")) for g, _, _ in raw_lex],
        "rrf_gids": rrf_gids,
        "top20_deconstructed": top20_deconstructed,
        "results": search_res.results,
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


def evaluate_query_relevance(
    query_obj: Dict[str, Any],
    results: List[DiscoverySearchResult],
    catalog_mgr: CatalogManager,
    twenty_k_ids: Set[str],
) -> Dict[str, Any]:
    expected_ids = {str(eid) for eid in query_obj.get("expected_ids", [])}
    avoid_tags = [t.lower() for t in query_obj.get("avoid_tags", [])]
    avoid_genres = [g.lower() for g in query_obj.get("avoid_genres", [])]

    top5 = results[:5]
    if not top5:
        return {
            "precision_at_5": 0.0,
            "hard_violations": 0,
            "long_tail_in_top5": 0,
            "useful_exploratory_in_top5": 0,
            "single_channel_lexical_in_top5": 0,
            "best_long_tail_rank": None,
            "zero_review_count": 0,
        }

    relevant_count = 0
    hard_violations = 0
    long_tail_count = 0
    useful_exploratory_count = 0
    single_channel_lex_count = 0
    zero_review_count = 0
    best_lt_rank = None

    for rank, r in enumerate(top5, 1):
        gid = str(r.game.id)
        g = catalog_mgr.get_game(gid) or {}
        reviews = r.game.total_reviews

        if reviews == 0:
            zero_review_count += 1

        is_lt = gid not in twenty_k_ids
        if is_lt:
            long_tail_count += 1
            if best_lt_rank is None:
                best_lt_rank = rank

        # Hard violations check
        has_viol = False
        g_tags = [t.lower() for t in g.get("tags", [])]
        g_genres = [g_name.lower() for g_name in g.get("genres", [])]
        for at in avoid_tags:
            if at in g_tags or at in g_genres:
                has_viol = True
                break
        for ag in avoid_genres:
            if ag in g_genres:
                has_viol = True
                break
        if has_viol:
            hard_violations += 1

        # Relevance scoring
        is_relevant = False
        if gid in expected_ids:
            is_relevant = True
        elif not has_viol and float(r.score) >= 0.70:
            is_relevant = True
        if is_relevant:
            relevant_count += 1

        # Useful exploratory: outside 20k + no violations + calibrated score >= 0.70
        if is_lt and not has_viol and float(r.score) >= 0.70:
            useful_exploratory_count += 1

    return {
        "precision_at_5": relevant_count / len(top5),
        "hard_violations": hard_violations,
        "long_tail_in_top5": long_tail_count,
        "useful_exploratory_in_top5": useful_exploratory_count,
        "single_channel_lexical_in_top5": single_channel_lex_count,
        "best_long_tail_rank": best_lt_rank,
        "zero_review_count": zero_review_count,
    }


async def evaluate_suite(
    suite_queries: List[Dict[str, Any]],
    pool: DiscoveryCandidatePool,
    damping: float,
    service: DiscoveryService,
    catalog_mgr: CatalogManager,
    twenty_k_ids: Set[str],
) -> Dict[str, Any]:
    precisions = []
    violations = []
    latencies = []
    useful_exploratory_counts = []
    long_tail_top5_counts = []
    single_channel_lex_in_top5_total = 0
    zero_review_counts = []
    best_lt_ranks = []
    top20_has_lt = 0
    top5_has_lt = 0

    funnel_new_dense = []
    funnel_new_lex = []
    funnel_new_rrf = []
    funnel_new_top20 = []
    funnel_new_top5 = []

    per_query_traces = []

    for q in suite_queries:
        q_text = q["query"]
        trace = await run_single_query(q_text, pool, damping, service, catalog_mgr, twenty_k_ids)
        rel_metrics = evaluate_query_relevance(q, trace["results"], catalog_mgr, twenty_k_ids)

        precisions.append(rel_metrics["precision_at_5"])
        violations.append(rel_metrics["hard_violations"])
        latencies.append(trace["timings_ms"]["total"])
        useful_exploratory_counts.append(rel_metrics["useful_exploratory_in_top5"])
        long_tail_top5_counts.append(rel_metrics["long_tail_in_top5"])
        zero_review_counts.append(rel_metrics["zero_review_count"])

        if rel_metrics["best_long_tail_rank"] is not None:
            best_lt_ranks.append(rel_metrics["best_long_tail_rank"])

        # Count Single-Channel Lexical in Top-5 (present in lexical, absent from dense Top-50)
        t5_decon = trace["top20_deconstructed"][:5]
        q_sc_lex = sum(1 for c in t5_decon if c["is_single_channel_lex"])
        single_channel_lex_in_top5_total += q_sc_lex

        # Funnel counts for this query
        dense_new = [gid for gid in trace["dense_gids"] if gid not in twenty_k_ids]
        lex_new = [gid for gid in trace["lex_gids"] if gid not in twenty_k_ids]
        rrf_new = [gid for gid in trace["rrf_gids"] if gid not in twenty_k_ids]
        top20_new = [c for c in trace["top20_deconstructed"] if not c["is_20k_head"]]
        top5_new = [c for c in t5_decon if not c["is_20k_head"]]

        funnel_new_dense.append(len(dense_new))
        funnel_new_lex.append(len(lex_new))
        funnel_new_rrf.append(len(rrf_new))
        funnel_new_top20.append(len(top20_new))
        funnel_new_top5.append(len(top5_new))

        if len(top20_new) > 0:
            top20_has_lt += 1
        if len(top5_new) > 0:
            top5_has_lt += 1

        per_query_traces.append({
            "query": q_text,
            "top5_titles": [c["title"] for c in t5_decon],
            "top5_deconstructed": t5_decon,
            "precision": rel_metrics["precision_at_5"],
            "violations": rel_metrics["hard_violations"],
            "useful_exploratory": rel_metrics["useful_exploratory_in_top5"],
            "long_tail_count": rel_metrics["long_tail_in_top5"],
            "single_channel_lex_count": q_sc_lex,
            "best_lt_rank": rel_metrics["best_long_tail_rank"],
        })

    num_q = len(suite_queries)
    total_top5_slots = num_q * 5

    return {
        "precision_at_5": round(float(np.mean(precisions)), 4),
        "hard_violations": int(sum(violations)),
        "avg_latency_ms": round(float(np.mean(latencies)), 2),
        "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
        "useful_exploratory_share": round((sum(useful_exploratory_counts) / total_top5_slots) * 100.0, 2),
        "long_tail_exposure_at_5": round((top5_has_lt / num_q) * 100.0, 2),
        "top5_long_tail_share": round((sum(long_tail_top5_counts) / total_top5_slots) * 100.0, 2),
        "top20_reach_rate": round((top20_has_lt / num_q) * 100.0, 2),
        "top5_reach_rate": round((top5_has_lt / num_q) * 100.0, 2),
        "avg_best_long_tail_rank": round(float(np.mean(best_lt_ranks)), 2) if best_lt_ranks else None,
        "median_best_long_tail_rank": float(np.median(best_lt_ranks)) if best_lt_ranks else None,
        "single_channel_lexical_intrusion_rate": round((single_channel_lex_in_top5_total / total_top5_slots) * 100.0, 2),
        "zero_review_candidates_count": int(sum(zero_review_counts)),
        "funnel": {
            "mean_new_dense": round(float(np.mean(funnel_new_dense)), 1),
            "mean_new_lex": round(float(np.mean(funnel_new_lex)), 1),
            "mean_new_rrf": round(float(np.mean(funnel_new_rrf)), 1),
            "mean_new_top20": round(float(np.mean(funnel_new_top20)), 1),
            "mean_new_top5": round(float(np.mean(funnel_new_top5)), 1),
        },
        "per_query_traces": per_query_traces,
    }


async def main():
    print("=" * 80)
    print("GAMEFORGE DISCOVERY V2.6 — DISCOVER SINGLE-CHANNEL RRF CONSISTENCY EXPERIMENT")
    print("=" * 80)

    service = DiscoveryService()
    await asyncio.to_thread(service.warm)
    catalog_mgr = service.catalog_manager
    twenty_k_ids = load_twenty_k_ids(catalog_mgr)

    with open(STD_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        std_benchmark = json.load(f)
    std_queries = std_benchmark["queries"]

    with open(DISC_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        disc_benchmark = json.load(f)
    disc_queries = disc_benchmark["queries"]

    # 1. Evaluate Condition A: 20k Baseline (damping=0.0)
    print("\nEvaluating Condition A (POPULAR_20K, Damping=0.0)...")
    res_a_std = await evaluate_suite(std_queries, DiscoveryCandidatePool.POPULAR_20K, 0.0, service, catalog_mgr, twenty_k_ids)
    res_a_disc = await evaluate_suite(disc_queries, DiscoveryCandidatePool.POPULAR_20K, 0.0, service, catalog_mgr, twenty_k_ids)

    # 2. Evaluate Condition B: Reviewed-Only (damping=0.0)
    print("Evaluating Condition B (REVIEWED_ONLY, Damping=0.0)...")
    res_b_std = await evaluate_suite(std_queries, DiscoveryCandidatePool.REVIEWED_ONLY, 0.0, service, catalog_mgr, twenty_k_ids)
    res_b_disc = await evaluate_suite(disc_queries, DiscoveryCandidatePool.REVIEWED_ONLY, 0.0, service, catalog_mgr, twenty_k_ids)

    # 3. Evaluate Condition C: Reviewed-Only + 50% Damping (damping=0.50)
    print("Evaluating Condition C (REVIEWED_ONLY, Damping=0.50)...")
    res_c_std = await evaluate_suite(std_queries, DiscoveryCandidatePool.REVIEWED_ONLY, 0.50, service, catalog_mgr, twenty_k_ids)
    res_c_disc = await evaluate_suite(disc_queries, DiscoveryCandidatePool.REVIEWED_ONLY, 0.50, service, catalog_mgr, twenty_k_ids)

    # 4. Critical Failure Case: 'cyberpunk detective game without heavy combat'
    print("\nTracing Critical Failure Case: 'cyberpunk detective game without heavy combat'...")
    fail_q = "cyberpunk detective game without heavy combat"
    trace_a_fail = await run_single_query(fail_q, DiscoveryCandidatePool.POPULAR_20K, 0.0, service, catalog_mgr, twenty_k_ids)
    trace_b_fail = await run_single_query(fail_q, DiscoveryCandidatePool.REVIEWED_ONLY, 0.0, service, catalog_mgr, twenty_k_ids)
    trace_c_fail = await run_single_query(fail_q, DiscoveryCandidatePool.REVIEWED_ONLY, 0.50, service, catalog_mgr, twenty_k_ids)

    jack_a = next((c for c in trace_a_fail["top20_deconstructed"] if "Jack & Detectives" in c["title"]), None)
    jack_b = next((c for c in trace_b_fail["top20_deconstructed"] if "Jack & Detectives" in c["title"]), None)
    jack_c = next((c for c in trace_c_fail["top20_deconstructed"] if "Jack & Detectives" in c["title"]), None)

    obs_a = next((c for c in trace_a_fail["top20_deconstructed"] if "Observer" in c["title"]), None)
    obs_b = next((c for c in trace_b_fail["top20_deconstructed"] if "Observer" in c["title"]), None)
    obs_c = next((c for c in trace_c_fail["top20_deconstructed"] if "Observer" in c["title"]), None)

    failure_case_trace = {
        "query": fail_q,
        "jack_and_detectives": {"A": jack_a, "B": jack_b, "C": jack_c},
        "observer_system_redux": {"A": obs_a, "B": obs_b, "C": obs_c},
        "top5_condition_a": [c["title"] for c in trace_a_fail["top20_deconstructed"][:5]],
        "top5_condition_b": [c["title"] for c in trace_b_fail["top20_deconstructed"][:5]],
        "top5_condition_c": [c["title"] for c in trace_c_fail["top20_deconstructed"][:5]],
    }

    # 5. Critical Success Cases
    print("Tracing Critical Success Cases...")
    success_queries = [
        ("disc05", "deckbuilder with base building", "Shapebreaker"),
        ("disc12", "farming without horror", "A Wholesome Game About Farming"),
        ("disc01", "cozy automation with trains", "RAILGRADE"),
        ("disc25", "games like Stardew Valley but more exploratory", "Stardew Valley"),
    ]
    success_traces = []
    for qid, qtext, expected_title in success_queries:
        tr_a = await run_single_query(qtext, DiscoveryCandidatePool.POPULAR_20K, 0.0, service, catalog_mgr, twenty_k_ids)
        tr_b = await run_single_query(qtext, DiscoveryCandidatePool.REVIEWED_ONLY, 0.0, service, catalog_mgr, twenty_k_ids)
        tr_c = await run_single_query(qtext, DiscoveryCandidatePool.REVIEWED_ONLY, 0.50, service, catalog_mgr, twenty_k_ids)

        tc_a = next((c for c in tr_a["top20_deconstructed"] if expected_title.lower() in c["title"].lower()), None)
        tc_b = next((c for c in tr_b["top20_deconstructed"] if expected_title.lower() in c["title"].lower()), None)
        tc_c = next((c for c in tr_c["top20_deconstructed"] if expected_title.lower() in c["title"].lower()), None)

        success_traces.append({
            "id": qid,
            "query": qtext,
            "expected_title": expected_title,
            "candidate_in_a": tc_a,
            "candidate_in_b": tc_b,
            "candidate_in_c": tc_c,
            "top5_titles_a": [c["title"] for c in tr_a["top20_deconstructed"][:5]],
            "top5_titles_b": [c["title"] for c in tr_b["top20_deconstructed"][:5]],
            "top5_titles_c": [c["title"] for c in tr_c["top20_deconstructed"][:5]],
        })

    # 6. Lexical False-Positive Audit
    print("Performing Deterministic Lexical False-Positive Audit on Condition B and C...")
    audit_cases = []
    for q_b, q_c in zip(res_b_disc["per_query_traces"], res_c_disc["per_query_traces"]):
        qtext = q_b["query"]
        sc_lex_b = [c for c in q_b["top5_deconstructed"] if c["is_single_channel_lex"]]
        sc_lex_c = [c for c in q_c["top5_deconstructed"] if c["is_single_channel_lex"]]

        if sc_lex_b or sc_lex_c:
            audit_cases.append({
                "query": qtext,
                "single_channel_in_b": [
                    {"title": c["title"], "reviews": c["total_reviews"], "pos_pct": c["positive_percent"], "lex_rank": c["lex_rank"], "sem_rank": c["sem_rank"], "final_rank": c["final_rank"], "score": c["calibrated_score"]}
                    for c in sc_lex_b
                ],
                "single_channel_in_c": [
                    {"title": c["title"], "reviews": c["total_reviews"], "pos_pct": c["positive_percent"], "lex_rank": c["lex_rank"], "sem_rank": c["sem_rank"], "final_rank": c["final_rank"], "score": c["calibrated_score"]}
                    for c in sc_lex_c
                ],
            })

    # Assemble Output Dataset
    output_data = {
        "experiment": "Discovery V2.6 — DISCOVER Single-Channel RRF Consistency Experiment",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "conditions": {
            "A": "POPULAR_20K + Current DISCOVER Ranker (Damping=0.0)",
            "B": "REVIEWED_ONLY + Current DISCOVER Ranker (Damping=0.0)",
            "C": "REVIEWED_ONLY + 50% Single-Channel Lexical RRF Damping (Damping=0.50)",
        },
        "standard_30_benchmark": {
            "condition_a": res_a_std,
            "condition_b": res_b_std,
            "condition_c": res_c_std,
        },
        "exploratory_25_benchmark": {
            "condition_a": res_a_disc,
            "condition_b": res_b_disc,
            "condition_c": res_c_disc,
        },
        "critical_failure_case": failure_case_trace,
        "critical_success_cases": success_traces,
        "lexical_false_positive_audit": audit_cases,
    }

    OUTPUT_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print("\n" + "=" * 80)
    print(f"EXPERIMENT V2.6 COMPLETE! Saved results to {OUTPUT_RESULTS_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
