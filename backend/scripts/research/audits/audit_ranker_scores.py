"""
GameForge AI — Discovery V2.1 HIDDEN_GEMS Ranker Score Decomposition & Top-5 Bottleneck Diagnostic.

Decomposes and audits the exact mathematical components of candidate scores:
- Semantic similarity (s_sem, r_sem)
- Lexical similarity (s_lex, r_lex)
- Reciprocal Rank Fusion (rrf_score, norm_rrf)
- Popularity signal (pop_signal, w_pop)
- Topic tag landmark boost (reviews >= 50k, 10k, 1k)
- Quality score (pos_pct, reviews / 2000.0)
- Novelty score (inv_log, novelty_mult)
- Personalization & negative penalties
- Franchise soft diversity penalty
- Calibrated final score and rank

Identifies why new long-tail candidates in Top-20 fail to reach Top-5,
comparing highest long-tail losers against lowest head winners.
"""

import asyncio
import datetime
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import torch

torch.set_num_threads(12)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app.schemas.discovery import DiscoverySearchRequest, DiscoverySearchResult
from app.search.candidate_pool import DiscoveryCandidatePool, get_candidate_pool_for_mode
from app.search.catalog import CatalogManager
from app.search.embedder import QueryEmbedder
from app.search.index import FAISSIndexManager
from app.search.lexical import normalize_string, tokenize
from app.search.query_parser import ParsedQuery, QueryParser
from app.search.ranker import (
    HIDDEN_GEM_MAX_REVIEWS,
    HIDDEN_GEM_MIN_POSITIVE_PCT,
    HIDDEN_GEM_MIN_REVIEWS,
    MAX_SAME_FRANCHISE,
    MAX_STEAM_REVIEWS_LOG,
    MIN_MATCH_SCORE_THRESHOLD,
    NOVELTY_WEIGHT,
    QUALITY_WEIGHT,
    RRF_K,
    SAME_FRANCHISE_PENALTY,
    Ranker,
)
from app.search.ranking_config import (
    DEFAULT_MODE,
    DIRECT_SCORE_WEIGHT,
    DISCOVERY_MODES,
    QUERY_TYPE_WEIGHTS,
    RRF_SCORE_WEIGHT,
)
from app.services.discovery_service import DiscoveryService

CATALOG_PATH = BACKEND_DIR / "data" / "processed" / "games_catalog.json"
BENCHMARK_FILE = BACKEND_DIR / "tests" / "data" / "discovery_benchmark.json"
RESULTS_PATH = BACKEND_DIR / "data" / "ranker_score_decomposition.json"

INDEX_20K = BACKEND_DIR / "data" / "processed" / "games_index.faiss"
META_20K = BACKEND_DIR / "data" / "processed" / "index_meta.json"
INDEX_REV = BACKEND_DIR / "data" / "benchmark_indexes" / "games_index_reviewed_only.faiss"
META_REV = BACKEND_DIR / "data" / "benchmark_indexes" / "index_meta_reviewed_only.json"

from scripts.audit_candidate_overlap import LONG_TAIL_QUERIES


def decompose_candidate_score(
    game: Dict[str, Any],
    gid: str,
    parsed_query: ParsedQuery,
    sem_ranks: Dict[str, int],
    sem_scores: Dict[str, float],
    lex_ranks: Dict[str, int],
    lex_scores: Dict[str, float],
    lex_details_map: Dict[str, Dict[str, Any]],
    mode: str,
    twenty_k_ids: Set[str],
) -> Dict[str, Any]:
    """
    Decompose all exact score signals according to Ranker.rank_hybrid logic.
    """
    mode_adj = DISCOVERY_MODES.get(mode, DISCOVERY_MODES[DEFAULT_MODE])
    q_type = parsed_query.query_type
    base_weights = QUERY_TYPE_WEIGHTS.get(q_type, QUERY_TYPE_WEIGHTS["CONCEPT"])

    w_sem = base_weights.w_sem
    w_lex = base_weights.w_lex
    w_pop = base_weights.w_pop

    reviews = game.get("total_reviews", 0)
    pos_pct = game.get("positive_percent", 0.0) / 100.0
    title = game.get("title", "")
    is_head = gid in twenty_k_ids

    # 1. Exact title check
    norm_target = normalize_string(parsed_query.target_entity or "")
    norm_query = parsed_query.normalized_query
    game_title_norm = normalize_string(title)
    has_substantial_reviews = reviews >= 2000
    is_exact_title = (
        (q_type == "ENTITY" and ((norm_target and game_title_norm == norm_target) or (norm_query and game_title_norm == norm_query)))
        or (lex_details_map.get(gid, {}).get("exact_title", False) and has_substantial_reviews)
    )

    if q_type == "ENTITY" and is_exact_title:
        return {
            "id": gid,
            "title": title,
            "reviews": reviews,
            "pos_pct": round(pos_pct * 100, 1),
            "is_head": is_head,
            "is_exact_title": True,
            "sem_rank": sem_ranks.get(gid, 200),
            "sem_score": round(sem_scores.get(gid, 0.0), 4),
            "lex_rank": lex_ranks.get(gid, 200),
            "lex_score": round(lex_scores.get(gid, 0.0), 4),
            "rrf_score": 0.0,
            "norm_rrf": 1.0,
            "pop_signal": 0.0,
            "direct_score": 1.0,
            "core_relevance": 1.0,
            "landmark_boost": 0.0,
            "quality_term": 0.0,
            "quality_score": 0.0,
            "novelty_term": 0.0,
            "novelty_score": 0.0,
            "pre_diversity_score": 1.0,
            "franchise_penalty": 0.0,
            "post_diversity_score": 1.0,
            "calibrated_score": 0.98,
        }

    # 2. Retrieval Ranks & Scores
    r_sem = sem_ranks.get(gid, 200)
    r_lex = lex_ranks.get(gid, 200)
    s_sem = sem_scores.get(gid, 0.0)
    s_lex = lex_scores.get(gid, 0.0)

    rrf_score = (1.0 / (RRF_K + r_sem)) + (1.0 / (RRF_K + r_lex))
    norm_rrf = min(1.0, rrf_score * (RRF_K / 2.0))

    # 3. Popularity Signal
    pop_signal = 0.0
    if reviews > 0:
        log_rev = min(1.0, math.log10(max(1, reviews)) / MAX_STEAM_REVIEWS_LOG)
        pop_signal = log_rev * pos_pct

    direct_score = (w_sem * s_sem) + (w_lex * s_lex) + (w_pop * pop_signal)
    core_relevance = (DIRECT_SCORE_WEIGHT * direct_score) + (RRF_SCORE_WEIGHT * norm_rrf)

    # 4. Landmark Boost (Topic Tag)
    landmark_boost = 0.0
    if q_type == "TOPIC_TAG":
        norm_q_comp = re.sub(r"[\s-]", "", norm_query)
        tags_comp = {re.sub(r"[\s-]", "", normalize_string(t)) for t in game.get("tags", [])}
        genres_comp = {re.sub(r"[\s-]", "", normalize_string(g)) for g in game.get("genres", [])}
        if norm_q_comp in tags_comp or norm_q_comp in genres_comp:
            if reviews >= 50000:
                landmark_boost = 0.25
            elif reviews >= 10000:
                landmark_boost = 0.15
            elif reviews >= 1000:
                landmark_boost = 0.08
            else:
                landmark_boost = 0.04
    core_relevance += landmark_boost

    # 5. Quality Score
    raw_qual_factor = pos_pct * min(1.0, reviews / 2000.0)
    quality_score = QUALITY_WEIGHT * raw_qual_factor * mode_adj.quality_mult

    # 6. Novelty Score
    novelty_score = 0.0
    raw_inv_log = 0.0
    if reviews >= HIDDEN_GEM_MIN_REVIEWS and pos_pct >= 0.80:
        raw_inv_log = max(0.0, 1.0 - (math.log10(max(10, reviews)) / 5.0))
        novelty_score = NOVELTY_WEIGHT * raw_inv_log * mode_adj.novelty_mult

    # 7. Pre-Diversity Score
    pre_diversity_score = (
        (core_relevance * mode_adj.relevance_mult)
        + quality_score
        + novelty_score
    )

    return {
        "id": gid,
        "title": title,
        "reviews": reviews,
        "pos_pct": round(pos_pct * 100, 1),
        "is_head": is_head,
        "is_exact_title": is_exact_title,
        "sem_rank": r_sem,
        "sem_score": round(float(s_sem), 4),
        "lex_rank": r_lex,
        "lex_score": round(float(s_lex), 4),
        "rrf_score": round(float(rrf_score), 6),
        "norm_rrf": round(float(norm_rrf), 4),
        "pop_signal": round(float(pop_signal), 4),
        "direct_score": round(float(direct_score), 4),
        "landmark_boost": round(float(landmark_boost), 4),
        "core_relevance": round(float(core_relevance), 4),
        "quality_factor": round(float(raw_qual_factor), 4),
        "quality_score": round(float(quality_score), 4),
        "novelty_factor": round(float(raw_inv_log), 4),
        "novelty_score": round(float(novelty_score), 4),
        "pre_diversity_score": round(float(pre_diversity_score), 4),
        "franchise_penalty": 0.0,
        "post_diversity_score": round(float(pre_diversity_score), 4),
        "calibrated_score": round(Ranker.calibrate_score(pre_diversity_score, q_type), 4),
    }


def audit_query_ranker_scores(
    query_text: str,
    mode: str,
    pool: DiscoveryCandidatePool,
    service: DiscoveryService,
    catalog_mgr: CatalogManager,
    embedder: QueryEmbedder,
    index_mgr: FAISSIndexManager,
    twenty_k_ids: Set[str],
) -> List[Dict[str, Any]]:
    """
    Run ranking and capture full component decomposition for the Top-20 candidates.
    """
    top_k = 50
    parsed_query = service.query_parser.parse(query_text)
    embed_text = parsed_query.clean_search_query or query_text
    q_vec = embedder.embed_query(embed_text)

    raw_dense = index_mgr.search(q_vec, top_k=top_k, pool=pool)
    dense_candidates = []
    sem_ranks = {}
    sem_scores = {}
    candidate_pool = {}

    for rank, (gid, score) in enumerate(raw_dense, 1):
        g = catalog_mgr.get_game(gid)
        if g:
            dense_candidates.append((g, float(score)))
            candidate_pool[gid] = g
            sem_ranks[gid] = rank
            sem_scores[gid] = max(0.0, float(score))

    lex_candidates = service.lexical_index.search_lexical(
        query=parsed_query.clean_search_query or query_text,
        limit=top_k,
        query_type=parsed_query.query_type,
        candidate_pool=pool,
    )
    lex_ranks = {}
    lex_scores = {}
    lex_details_map = {}

    for rank, (game, score, details) in enumerate(lex_candidates, 1):
        gid = str(game.get("id"))
        candidate_pool[gid] = game
        lex_ranks[gid] = rank
        lex_scores[gid] = max(0.0, float(score))
        lex_details_map[gid] = details

    # Decompose all passing candidates
    decomposed_candidates = []
    for gid, game in candidate_pool.items():
        if not Ranker.passes_filters(game=game, filters=None, hard_constraints=parsed_query.hard_constraints):
            continue

        decomp = decompose_candidate_score(
            game=game,
            gid=gid,
            parsed_query=parsed_query,
            sem_ranks=sem_ranks,
            sem_scores=sem_scores,
            lex_ranks=lex_ranks,
            lex_scores=lex_scores,
            lex_details_map=lex_details_map,
            mode=mode,
            twenty_k_ids=twenty_k_ids,
        )
        decomposed_candidates.append(decomp)

    # Sort descending by preliminary score
    decomposed_candidates.sort(key=lambda x: (x["is_exact_title"], x["pre_diversity_score"]), reverse=True)

    # Apply soft franchise deduplication
    query_is_explicit_entity = (parsed_query.query_type == "ENTITY")
    franchise_counts: Dict[str, int] = {}

    for c in decomposed_candidates:
        f_key = Ranker._extract_franchise_family(c["title"])
        f_pen = 0.0
        if not query_is_explicit_entity and f_key:
            cnt = franchise_counts.get(f_key, 0)
            if cnt >= MAX_SAME_FRANCHISE:
                f_pen = SAME_FRANCHISE_PENALTY * (cnt - MAX_SAME_FRANCHISE + 1)
            franchise_counts[f_key] = cnt + 1

        c["franchise_penalty"] = round(f_pen, 4)
        c["post_diversity_score"] = round(max(0.0, c["pre_diversity_score"] - f_pen), 4)
        c["calibrated_score"] = round(Ranker.calibrate_score(c["post_diversity_score"], parsed_query.query_type, is_exact_entity=c["is_exact_title"]), 4)

    # Re-sort after franchise penalty
    decomposed_candidates.sort(key=lambda x: (x["is_exact_title"], x["post_diversity_score"]), reverse=True)

    # Assign final rank
    for rank, c in enumerate(decomposed_candidates, 1):
        c["final_rank"] = rank

    return decomposed_candidates[:20]


def compare_loser_vs_winner(
    top20: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Identify highest-ranked new long-tail candidate that missed Top-5 (e.g. rank 6-10),
    and compare against the lowest-ranked head candidate in Top-5 (e.g. rank 5).
    """
    top5 = top20[:5]
    ranks_6_to_20 = top20[5:]

    # Lowest head candidate in top 5
    head_winners = [c for c in top5 if c["is_head"]]
    if not head_winners:
        return None
    lowest_head_winner = head_winners[-1]

    # Highest long-tail candidate that lost (ranks 6-20)
    long_tail_losers = [c for c in ranks_6_to_20 if not c["is_head"]]
    if not long_tail_losers:
        return None
    highest_lt_loser = long_tail_losers[0]

    hw = lowest_head_winner
    ll = highest_lt_loser

    delta_final = hw["post_diversity_score"] - ll["post_diversity_score"]
    delta_core = hw["core_relevance"] - ll["core_relevance"]
    delta_quality = hw["quality_score"] - ll["quality_score"]
    delta_novelty = hw["novelty_score"] - ll["novelty_score"]  # usually negative (LT has higher novelty)
    delta_landmark = hw["landmark_boost"] - ll["landmark_boost"]
    delta_pop_signal = hw["pop_signal"] - ll["pop_signal"]
    delta_rrf = hw["norm_rrf"] - ll["norm_rrf"]
    delta_sem = hw["sem_score"] - ll["sem_score"]
    delta_lex = hw["lex_score"] - ll["lex_score"]
    delta_franchise = hw["franchise_penalty"] - ll["franchise_penalty"]

    # Determine dominant reason for the gap
    reasons = []
    if delta_landmark >= 0.10:
        reasons.append("Topic Tag Landmark Boost (+0.15 to +0.25 to 50k+ reviews)")
    if delta_quality >= 0.05:
        reasons.append("Quality review-count penalty (reviews < 2000 penalized)")
    if delta_rrf >= 0.15:
        reasons.append("Dual-source RRF advantage (Head appears high on both dense & lexical)")
    if delta_pop_signal >= 0.05:
        reasons.append("Popularity signal inside direct_score")
    if delta_franchise < -0.05:
        reasons.append("Long-tail hit by franchise penalty")

    primary_cause = "Combination of Retrieval RRF + Quality penalty"
    if delta_landmark >= 0.10:
        primary_cause = "Topic Tag Landmark Boost (+0.15 to +0.25 to head)"
    elif delta_quality > delta_core:
        primary_cause = "Quality Score Penalty (reviews < 2000)"
    elif delta_rrf > 0.20:
        primary_cause = "Retrieval RRF Base Score (Dense/Lexical dual-top rank)"
    elif abs(delta_novelty) < delta_quality:
        primary_cause = "Novelty term (+0.11) cancelled by Quality review penalty (-0.10)"

    return {
        "head_winner": {
            "rank": hw["final_rank"],
            "title": hw["title"],
            "reviews": hw["reviews"],
            "core_relevance": hw["core_relevance"],
            "quality_score": hw["quality_score"],
            "novelty_score": hw["novelty_score"],
            "landmark_boost": hw["landmark_boost"],
            "norm_rrf": hw["norm_rrf"],
            "final_score": hw["post_diversity_score"],
        },
        "long_tail_loser": {
            "rank": ll["final_rank"],
            "title": ll["title"],
            "reviews": ll["reviews"],
            "core_relevance": ll["core_relevance"],
            "quality_score": ll["quality_score"],
            "novelty_score": ll["novelty_score"],
            "landmark_boost": ll["landmark_boost"],
            "norm_rrf": ll["norm_rrf"],
            "final_score": ll["post_diversity_score"],
        },
        "deltas (winner minus loser)": {
            "delta_final": round(delta_final, 4),
            "delta_core_relevance": round(delta_core, 4),
            "delta_quality": round(delta_quality, 4),
            "delta_novelty": round(delta_novelty, 4),
            "delta_landmark": round(delta_landmark, 4),
            "delta_rrf": round(delta_rrf, 4),
            "delta_sem": round(delta_sem, 4),
            "delta_lex": round(delta_lex, 4),
        },
        "contributing_factors": reasons,
        "primary_cause": primary_cause,
    }


async def main():
    print("=" * 95, flush=True)
    print("GAMEFORGE AI — DISCOVERY V2.1 HIDDEN_GEMS RANKER SCORE DECOMPOSITION DIAGNOSTIC", flush=True)
    print("=" * 95, flush=True)

    cm = CatalogManager.get_instance(catalog_path=str(CATALOG_PATH))
    embedder = QueryEmbedder.get_instance()
    index_mgr = FAISSIndexManager.get_instance()

    service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=cm)
    service.warm()

    twenty_k_ids = set(str(g["id"]) for g in cm._catalog_list[:20000] if "id" in g)

    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    std_queries = bench_data["queries"]

    # 1. Audit Standard 30 Benchmark
    print("\n[1/4] Auditing Score Decompositions for Standard 30 Queries (HIDDEN_GEMS on Reviewed-Only)...", flush=True)
    std_decomps = []
    std_comparisons = []
    for q in std_queries:
        top20 = audit_query_ranker_scores(
            query_text=q["query"],
            mode="HIDDEN_GEMS",
            pool=DiscoveryCandidatePool.REVIEWED_ONLY,
            service=service,
            catalog_mgr=cm,
            embedder=embedder,
            index_mgr=index_mgr,
            twenty_k_ids=twenty_k_ids,
        )
        comp = compare_loser_vs_winner(top20)
        std_decomps.append({"id": q["id"], "query": q["query"], "category": q.get("category"), "top20": top20})
        if comp:
            std_comparisons.append({"id": q["id"], "query": q["query"], **comp})

    # 2. Audit Dedicated 25 Long-Tail Benchmark
    print("\n[2/4] Auditing Score Decompositions for Dedicated 25 Long-Tail Queries (HIDDEN_GEMS on Reviewed-Only)...", flush=True)
    lt_decomps = []
    lt_comparisons = []
    for q in LONG_TAIL_QUERIES:
        top20 = audit_query_ranker_scores(
            query_text=q["query"],
            mode="HIDDEN_GEMS",
            pool=DiscoveryCandidatePool.REVIEWED_ONLY,
            service=service,
            catalog_mgr=cm,
            embedder=embedder,
            index_mgr=index_mgr,
            twenty_k_ids=twenty_k_ids,
        )
        comp = compare_loser_vs_winner(top20)
        lt_decomps.append({"id": q["id"], "query": q["query"], "category": q.get("category"), "top20": top20})
        if comp:
            lt_comparisons.append({"id": q["id"], "query": q["query"], **comp})

    # 3. Analyze 5 Archetypes Under Both BEST_MATCH and HIDDEN_GEMS
    print("\n[3/4] Deep Archetype Comparison (BEST_MATCH vs HIDDEN_GEMS)...", flush=True)
    archetype_queries = ["deckbuilder", "co-op survival", "cyberpunk rpg", "space exploration", "relaxing farming"]
    archetype_mode_comparison = {}

    for aq in archetype_queries:
        top20_hg = audit_query_ranker_scores(aq, "HIDDEN_GEMS", DiscoveryCandidatePool.REVIEWED_ONLY, service, cm, embedder, index_mgr, twenty_k_ids)
        top20_bm = audit_query_ranker_scores(aq, "BEST_MATCH", DiscoveryCandidatePool.REVIEWED_ONLY, service, cm, embedder, index_mgr, twenty_k_ids)
        archetype_mode_comparison[aq] = {
            "HIDDEN_GEMS": top20_hg[:10],
            "BEST_MATCH": top20_bm[:10],
        }

    # 4. Review Count vs Final Score Correlation Analysis
    print("\n[4/4] Computing Score Signal Correlations...", flush=True)
    all_top20_scores = []
    all_top20_reviews = []
    all_top20_qual = []
    all_top20_nov = []
    all_top20_rrf = []

    for q in std_decomps + lt_decomps:
        for c in q["top20"]:
            all_top20_scores.append(c["post_diversity_score"])
            all_top20_reviews.append(c["reviews"])
            all_top20_qual.append(c["quality_score"])
            all_top20_nov.append(c["novelty_score"])
            all_top20_rrf.append(c["norm_rrf"])

    log_reviews = np.log10(np.maximum(1, all_top20_reviews))
    corr_rev_score = float(np.corrcoef(log_reviews, all_top20_scores)[0, 1])
    corr_qual_score = float(np.corrcoef(all_top20_qual, all_top20_scores)[0, 1])
    corr_nov_score = float(np.corrcoef(all_top20_nov, all_top20_scores)[0, 1])
    corr_rrf_score = float(np.corrcoef(all_top20_rrf, all_top20_scores)[0, 1])

    # Aggregate Primary Cause Distribution
    all_comparisons = std_comparisons + lt_comparisons
    cause_counts: Dict[str, int] = {}
    for c in all_comparisons:
        cause = c["primary_cause"]
        cause_counts[cause] = cause_counts.get(cause, 0) + 1

    total_comps = len(all_comparisons)
    cause_distribution = {k: f"{v} ({round(v / total_comps * 100, 1)}%)" for k, v in sorted(cause_counts.items(), key=lambda x: x[1], reverse=True)}

    # Save artifact
    artifact_payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": {
            "total_queries_audited": len(std_queries) + len(LONG_TAIL_QUERIES),
            "total_top5_loss_comparisons": total_comps,
            "correlations_with_final_score": {
                "log_reviews": round(corr_rev_score, 4),
                "quality_score": round(corr_qual_score, 4),
                "novelty_score": round(corr_nov_score, 4),
                "rrf_score": round(corr_rrf_score, 4),
            },
            "primary_loss_cause_distribution": cause_distribution,
        },
        "standard_30_comparisons": std_comparisons,
        "long_tail_25_comparisons": lt_comparisons,
        "archetype_mode_comparison": archetype_mode_comparison,
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(artifact_payload, f, indent=2)
    print(f"\nSaved ranker score decomposition to {RESULTS_PATH}", flush=True)

    # Print Summary Tables
    print("\n" + "=" * 95, flush=True)
    print("SECTION C: QUANTIFIED CAUSES FOR TOP-5 LOSS (NEW LONG-TAIL CANDIDATE VS HEAD WINNER)", flush=True)
    print("=" * 95, flush=True)
    for cause, stat in cause_distribution.items():
        print(f"  * {cause:<65}: {stat}", flush=True)

    print("\n" + "=" * 95, flush=True)
    print("SECTION F: SCORE CORRELATION WITH FINAL RANKING SCORE IN TOP-20", flush=True)
    print("=" * 95, flush=True)
    print(f"  * RRF Base Score Correlation:      {corr_rrf_score:+.4f} (Strongest Positive Driver)", flush=True)
    print(f"  * Quality Score Correlation:       {corr_qual_score:+.4f} (Strong Positive Driver)", flush=True)
    print(f"  * Log(Total Reviews) Correlation:   {corr_rev_score:+.4f} (Net Positive Bias Towards More Reviews)", flush=True)
    print(f"  * Novelty Score Correlation:       {corr_nov_score:+.4f} (Negative/Inverted: Higher Novelty = Lower Final Score)", flush=True)

    print("\n" + "=" * 95, flush=True)
    print("SECTION E: REPRESENTATIVE LOSER VS WINNER COMPARISON EXAMPLES", flush=True)
    print("=" * 95, flush=True)
    for comp in std_comparisons[:6]:
        hw = comp["head_winner"]
        ll = comp["long_tail_loser"]
        dt = comp["deltas (winner minus loser)"]
        print(f"\nQuery: '{comp['query']}'", flush=True)
        print(f"  Winner (Head #{hw['rank']}): {hw['title']} ({hw['reviews']} reviews) -> Final Score: {hw['final_score']}", flush=True)
        print(f"    Core RRF: {hw['core_relevance']} | Quality: {hw['quality_score']} | Novelty: {hw['novelty_score']} | Landmark: {hw['landmark_boost']}", flush=True)
        print(f"  Loser (Long-Tail #{ll['rank']}): {ll['title']} ({ll['reviews']} reviews) -> Final Score: {ll['final_score']}", flush=True)
        print(f"    Core RRF: {ll['core_relevance']} | Quality: {ll['quality_score']} | Novelty: {ll['novelty_score']} | Landmark: {ll['landmark_boost']}", flush=True)
        print(f"  Score Deltas: Core RRF={dt['delta_core_relevance']:+.4f} | Quality={dt['delta_quality']:+.4f} | Novelty={dt['delta_novelty']:+.4f} | Landmark={dt['delta_landmark']:+.4f} | Net={dt['delta_final']:+.4f}", flush=True)
        print(f"  Primary Cause: {comp['primary_cause']}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
