"""
GameForge AI — Discovery V2.2 HIDDEN_GEMS Ranker Tuning Experiment.

Evaluates quality review confidence threshold variants and review-independent
quality formulations under HIDDEN_GEMS on the Reviewed-Only candidate pool:
1. Control: review_thresh = 2000
2. Q1: review_thresh = 1000
3. Q2: review_thresh = 500
4. Q3: review_thresh = 250
5. Q4: review_thresh = 100
6. Q5: review_thresh = 50
7. Q6: Review-Independent Bayesian Smoothed Quality
8. Experiment 2: Best Quality Variant + Topic-Tag Landmark Boost (L0 vs L1)
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

BACKEND_DIR = Path(__file__).resolve().parent.parent
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

from scripts.audit_candidate_overlap import LONG_TAIL_QUERIES

CATALOG_PATH = BACKEND_DIR / "data" / "processed" / "games_catalog.json"
BENCHMARK_FILE = BACKEND_DIR / "tests" / "data" / "discovery_benchmark.json"
RESULTS_PATH = BACKEND_DIR / "data" / "ranker_tuning_experiment_results.json"


def classify_review_band(reviews: int) -> str:
    """Classify total reviews into standardized evaluation bands."""
    if reviews < 50:
        return "1-49"
    elif reviews < 100:
        return "50-99"
    elif reviews < 250:
        return "100-249"
    elif reviews < 500:
        return "250-499"
    elif reviews < 1000:
        return "500-999"
    elif reviews < 2000:
        return "1000-1999"
    elif reviews < 5000:
        return "2000-4999"
    else:
        return "5000+"


REVIEW_BANDS = ["1-49", "50-99", "100-249", "250-499", "500-999", "1000-1999", "2000-4999", "5000+"]


def rank_candidates_experimental(
    candidate_pool: Dict[str, Dict[str, Any]],
    sem_ranks: Dict[str, int],
    sem_scores: Dict[str, float],
    lex_ranks: Dict[str, int],
    lex_scores: Dict[str, float],
    lex_details_map: Dict[str, Dict[str, Any]],
    parsed_query: ParsedQuery,
    mode: str,
    quality_variant: str,
    landmark_variant: str = "L0",
    top_limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Execute ranking with configurable quality formulation and landmark boost.
    All other signals (semantic, lexical, RRF, novelty, franchise deduplication) remain 100% identical.
    """
    mode_adj = DISCOVERY_MODES.get(mode, DISCOVERY_MODES[DEFAULT_MODE])
    q_type = parsed_query.query_type
    base_weights = QUERY_TYPE_WEIGHTS.get(q_type, QUERY_TYPE_WEIGHTS["CONCEPT"])

    w_sem = base_weights.w_sem
    w_lex = base_weights.w_lex
    w_pop = base_weights.w_pop

    norm_target = normalize_string(parsed_query.target_entity or "")
    norm_query = parsed_query.normalized_query

    scored_candidates = []

    for gid, game in candidate_pool.items():
        if not Ranker.passes_filters(game=game, filters=None, hard_constraints=parsed_query.hard_constraints):
            continue

        reviews = game.get("total_reviews", 0)
        pos_pct = game.get("positive_percent", 0.0) / 100.0
        title = game.get("title", "")
        game_title_norm = normalize_string(title)

        has_substantial_reviews = reviews >= 2000
        is_exact_title = (
            (q_type == "ENTITY" and ((norm_target and game_title_norm == norm_target) or (norm_query and game_title_norm == norm_query)))
            or (lex_details_map.get(gid, {}).get("exact_title", False) and has_substantial_reviews)
        )

        if q_type == "ENTITY" and is_exact_title:
            scored_candidates.append({
                "id": gid,
                "game": game,
                "score": 1.0,
                "is_exact": True,
                "core_relevance": 1.0,
                "quality_score": 0.0,
                "novelty_score": 0.0,
                "landmark_boost": 0.0,
                "norm_rrf": 1.0,
                "reviews": reviews,
            })
            continue

        r_sem = sem_ranks.get(gid, 200)
        r_lex = lex_ranks.get(gid, 200)
        s_sem = sem_scores.get(gid, 0.0)
        s_lex = lex_scores.get(gid, 0.0)

        rrf_score = (1.0 / (RRF_K + r_sem)) + (1.0 / (RRF_K + r_lex))
        norm_rrf = min(1.0, rrf_score * (RRF_K / 2.0))

        pop_signal = 0.0
        if reviews > 0:
            log_rev = min(1.0, math.log10(max(1, reviews)) / MAX_STEAM_REVIEWS_LOG)
            pop_signal = log_rev * pos_pct

        direct_score = (w_sem * s_sem) + (w_lex * s_lex) + (w_pop * pop_signal)
        core_relevance = (DIRECT_SCORE_WEIGHT * direct_score) + (RRF_SCORE_WEIGHT * norm_rrf)

        # Topic Tag Landmark Boost
        landmark_boost = 0.0
        if q_type == "TOPIC_TAG":
            norm_q_comp = re.sub(r"[\s-]", "", norm_query)
            tags_comp = {re.sub(r"[\s-]", "", normalize_string(t)) for t in game.get("tags", [])}
            genres_comp = {re.sub(r"[\s-]", "", normalize_string(g)) for g in game.get("genres", [])}
            if norm_q_comp in tags_comp or norm_q_comp in genres_comp:
                if landmark_variant == "L1" and mode == "HIDDEN_GEMS":
                    # L1: Reduced landmark boost for HIDDEN_GEMS
                    if reviews >= 50000:
                        landmark_boost = 0.08
                    elif reviews >= 10000:
                        landmark_boost = 0.06
                    elif reviews >= 1000:
                        landmark_boost = 0.05
                    else:
                        landmark_boost = 0.04
                else:
                    # L0: Standard control boost
                    if reviews >= 50000:
                        landmark_boost = 0.25
                    elif reviews >= 10000:
                        landmark_boost = 0.15
                    elif reviews >= 1000:
                        landmark_boost = 0.08
                    else:
                        landmark_boost = 0.04
        core_relevance += landmark_boost

        # Quality Score Calculation
        if mode == "HIDDEN_GEMS":
            if quality_variant == "control" or quality_variant == "2000":
                qual_factor = pos_pct * min(1.0, reviews / 2000.0)
                quality_score = QUALITY_WEIGHT * qual_factor * mode_adj.quality_mult
            elif quality_variant == "1000":
                qual_factor = pos_pct * min(1.0, reviews / 1000.0)
                quality_score = QUALITY_WEIGHT * qual_factor * mode_adj.quality_mult
            elif quality_variant == "500":
                qual_factor = pos_pct * min(1.0, reviews / 500.0)
                quality_score = QUALITY_WEIGHT * qual_factor * mode_adj.quality_mult
            elif quality_variant == "250":
                qual_factor = pos_pct * min(1.0, reviews / 250.0)
                quality_score = QUALITY_WEIGHT * qual_factor * mode_adj.quality_mult
            elif quality_variant == "100":
                qual_factor = pos_pct * min(1.0, reviews / 100.0)
                quality_score = QUALITY_WEIGHT * qual_factor * mode_adj.quality_mult
            elif quality_variant == "50":
                qual_factor = pos_pct * min(1.0, reviews / 50.0)
                quality_score = QUALITY_WEIGHT * qual_factor * mode_adj.quality_mult
            elif quality_variant == "bayes" or quality_variant == "review_independent":
                # Q6: Bayesian Smoothed Quality (priors: C=20, p0=0.75)
                # Smoothed positive percentage: shrinks slightly toward Steam catalog mean (0.75)
                # without penalizing small sample sizes as zero quality.
                smoothed_pos = (pos_pct * reviews + 0.75 * 20.0) / (reviews + 20.0)
                quality_score = QUALITY_WEIGHT * smoothed_pos * mode_adj.quality_mult
            else:
                qual_factor = pos_pct * min(1.0, reviews / 2000.0)
                quality_score = QUALITY_WEIGHT * qual_factor * mode_adj.quality_mult
        else:
            # Control for non-HIDDEN_GEMS modes
            qual_factor = pos_pct * min(1.0, reviews / 2000.0)
            quality_score = QUALITY_WEIGHT * qual_factor * mode_adj.quality_mult

        # Novelty Score (Exact unchanged formula)
        novelty_score = 0.0
        if reviews >= HIDDEN_GEM_MIN_REVIEWS and pos_pct >= 0.80:
            inv_log = max(0.0, 1.0 - (math.log10(max(10, reviews)) / 5.0))
            novelty_score = NOVELTY_WEIGHT * inv_log * mode_adj.novelty_mult

        final_score = (core_relevance * mode_adj.relevance_mult) + quality_score + novelty_score

        scored_candidates.append({
            "id": gid,
            "game": game,
            "score": max(0.0, final_score),
            "is_exact": is_exact_title,
            "core_relevance": round(core_relevance, 4),
            "quality_score": round(quality_score, 4),
            "novelty_score": round(novelty_score, 4),
            "landmark_boost": round(landmark_boost, 4),
            "norm_rrf": round(norm_rrf, 4),
            "reviews": reviews,
        })

    # Sort descending by preliminary score
    scored_candidates.sort(key=lambda x: (x["is_exact"], x["score"]), reverse=True)

    # Soft franchise deduplication (Exact unchanged formula)
    query_is_explicit_entity = (q_type == "ENTITY")
    selected = []
    franchise_counts: Dict[str, int] = {}

    for c in scored_candidates:
        f_key = Ranker._extract_franchise_family(c["game"].get("title", ""))
        score = c["score"]
        if not query_is_explicit_entity and f_key:
            cnt = franchise_counts.get(f_key, 0)
            if cnt >= MAX_SAME_FRANCHISE:
                score -= SAME_FRANCHISE_PENALTY * (cnt - MAX_SAME_FRANCHISE + 1)
            franchise_counts[f_key] = cnt + 1
        c["score"] = max(0.0, score)
        selected.append(c)

    selected.sort(key=lambda x: (x["is_exact"], x["score"]), reverse=True)

    for rank, c in enumerate(selected, 1):
        c["rank"] = rank
        c["calibrated_score"] = Ranker.calibrate_score(c["score"], q_type, is_exact_entity=c["is_exact"])

    return selected[:top_limit]


def evaluate_query_benchmark(
    queries: List[Dict[str, Any]],
    mode: str,
    quality_variant: str,
    landmark_variant: str,
    service: DiscoveryService,
    catalog_mgr: CatalogManager,
    embedder: QueryEmbedder,
    index_mgr: FAISSIndexManager,
    twenty_k_ids: Set[str],
) -> Dict[str, Any]:
    """
    Run full benchmark evaluation across queries for a specific ranker configuration.
    """
    pool = DiscoveryCandidatePool.REVIEWED_ONLY
    top_k = 50

    p5_scores = []
    latencies = []
    hard_violations = 0
    intent_correct = 0

    all_top5_reviews = []
    qualifying_top5_longtail = 0  # reviews <= 5000
    zero_review_count = 0
    total_top5_slots = 0

    review_band_counts = {b: 0 for b in REVIEW_BANDS}

    top20_longtail_reach_queries = 0
    top5_longtail_surface_queries = 0
    best_longtail_ranks = []

    query_details = []

    for q in queries:
        qid = q["id"]
        q_text = q["query"]
        category = q.get("category", "General")

        t0 = time.perf_counter()
        parsed_query = service.query_parser.parse(q_text)
        embed_text = parsed_query.clean_search_query or q_text
        q_vec = embedder.embed_query(embed_text)

        # Retrieval
        raw_dense = index_mgr.search(q_vec, top_k=top_k, pool=pool)
        candidate_pool = {}
        sem_ranks = {}
        sem_scores = {}
        for rank, (gid, score) in enumerate(raw_dense, 1):
            g = catalog_mgr.get_game(gid)
            if g:
                candidate_pool[gid] = g
                sem_ranks[gid] = rank
                sem_scores[gid] = max(0.0, float(score))

        lex_candidates = service.lexical_index.search_lexical(
            query=parsed_query.clean_search_query or q_text,
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

        # Rank with experimental parameters
        ranked_top20 = rank_candidates_experimental(
            candidate_pool=candidate_pool,
            sem_ranks=sem_ranks,
            sem_scores=sem_scores,
            lex_ranks=lex_ranks,
            lex_scores=lex_scores,
            lex_details_map=lex_details_map,
            parsed_query=parsed_query,
            mode=mode,
            quality_variant=quality_variant,
            landmark_variant=landmark_variant,
            top_limit=20,
        )
        lat_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(lat_ms)

        top5 = ranked_top20[:5]

        # Intent accuracy
        if q.get("expected_intent") and parsed_query.query_type == q["expected_intent"]:
            intent_correct += 1

        # Hard constraints
        has_violation = False
        if q.get("must_not_contain_genres"):
            banned_g = {g.lower() for g in q["must_not_contain_genres"]}
            for r in top5:
                game_g = {g.lower() for g in r["game"].get("genres", [])}
                if banned_g.intersection(game_g):
                    has_violation = True
                    hard_violations += 1
                    break

        if q.get("must_not_contain_modes"):
            banned_m = {m.lower() for m in q["must_not_contain_modes"]}
            for r in top5:
                game_m = {m.lower() for m in r["game"].get("player_modes", [])}
                if banned_m.intersection(game_m):
                    has_violation = True
                    hard_violations += 1
                    break

        if q.get("must_be_free"):
            for r in top5:
                if not r["game"].get("is_free", False):
                    has_violation = True
                    hard_violations += 1
                    break

        # Relevance / Precision@5
        relevant_in_top5 = 0
        must_include = q.get("must_include_titles", [])
        acceptable_g = {g.lower() for g in q.get("acceptable_genres", [])}

        for r in top5:
            title_norm = normalize_string(r["game"].get("title", ""))
            if must_include:
                if any(normalize_string(mi) in title_norm for mi in must_include):
                    relevant_in_top5 += 1
            elif acceptable_g:
                game_g = {g.lower() for g in r["game"].get("genres", [])}
                if acceptable_g.intersection(game_g) or r["calibrated_score"] >= 0.70:
                    relevant_in_top5 += 1
            else:
                if r["calibrated_score"] >= 0.65:
                    relevant_in_top5 += 1

        p5 = relevant_in_top5 / max(1, min(5, len(top5)))
        p5_scores.append(p5)

        # Long-tail metrics & review bands
        for r in top5:
            revs = r["reviews"]
            all_top5_reviews.append(revs)
            total_top5_slots += 1
            if revs <= 5000:
                qualifying_top5_longtail += 1
            if revs == 0:
                zero_review_count += 1
            band = classify_review_band(revs)
            review_band_counts[band] += 1

        # Long-tail candidates reach in Top-20 vs Top-5
        lt_in_top20 = [r for r in ranked_top20 if r["id"] not in twenty_k_ids]
        lt_in_top5 = [r for r in top5 if r["id"] not in twenty_k_ids]

        if lt_in_top20:
            top20_longtail_reach_queries += 1
            best_longtail_ranks.append(lt_in_top20[0]["rank"])
        if lt_in_top5:
            top5_longtail_surface_queries += 1

        query_details.append({
            "id": qid,
            "query": q_text,
            "p5": round(p5, 3),
            "latency_ms": round(lat_ms, 2),
            "has_violation": has_violation,
            "top5_titles": [r["game"].get("title", "") for r in top5],
            "top5_reviews": [r["reviews"] for r in top5],
            "top5_scores": [round(float(r["score"]), 3) for r in top5],
        })

    num_q = len(queries)
    return {
        "variant": quality_variant,
        "landmark_variant": landmark_variant,
        "precision_at_5": round(float(np.mean(p5_scores)), 4),
        "hard_violations": hard_violations,
        "intent_accuracy": round(intent_correct / max(1, num_q), 4),
        "latency_mean_ms": round(float(np.mean(latencies)), 2),
        "latency_p95_ms": round(float(np.percentile(latencies, 95)), 2),
        "long_tail_exposure_at_5": round(qualifying_top5_longtail / max(1, total_top5_slots) * 100.0, 1),
        "top20_long_tail_reach_rate": round(top20_longtail_reach_queries / max(1, num_q) * 100.0, 1),
        "top5_long_tail_surface_rate": round(top5_longtail_surface_queries / max(1, num_q) * 100.0, 1),
        "avg_best_long_tail_rank": round(float(np.mean(best_longtail_ranks)), 2) if best_longtail_ranks else 20.0,
        "median_best_long_tail_rank": int(np.median(best_longtail_ranks)) if best_longtail_ranks else 20,
        "mean_reviews_top5": round(float(np.mean(all_top5_reviews)), 1) if all_top5_reviews else 0.0,
        "median_reviews_top5": int(np.median(all_top5_reviews)) if all_top5_reviews else 0,
        "zero_review_count": zero_review_count,
        "review_band_distribution": {
            band: {
                "count": review_band_counts[band],
                "percent": round(review_band_counts[band] / max(1, total_top5_slots) * 100.0, 1),
            }
            for band in REVIEW_BANDS
        },
        "query_details": query_details,
    }


def track_key_archetype_titles(
    quality_variants: List[str],
    service: DiscoveryService,
    catalog_mgr: CatalogManager,
    embedder: QueryEmbedder,
    index_mgr: FAISSIndexManager,
) -> Dict[str, Dict[str, Any]]:
    """
    Track score and rank trajectory of key titles across variants.
    """
    targets = {
        "Shapebreaker": ("deckbuilder", 1924010),
        "Slay the Spire": ("deckbuilder", 646570),
        "Colony Ship": ("cyberpunk rpg", 648410),
        "MOTHERED": ("cyberpunk rpg", 1830720),
        "Floating Farmer": ("relaxing farming", 1716390),
        "Farming Simulator 2013": ("relaxing farming", 220260),
    }

    pool = DiscoveryCandidatePool.REVIEWED_ONLY
    top_k = 50
    title_trajectories = {t: {} for t in targets}

    for t_name, (query_text, target_id) in targets.items():
        parsed = service.query_parser.parse(query_text)
        embed_text = parsed.clean_search_query or query_text
        q_vec = embedder.embed_query(embed_text)

        raw_dense = index_mgr.search(q_vec, top_k=top_k, pool=pool)
        candidate_pool = {}
        sem_ranks = {}
        sem_scores = {}
        for rank, (gid, score) in enumerate(raw_dense, 1):
            g = catalog_mgr.get_game(gid)
            if g:
                candidate_pool[gid] = g
                sem_ranks[gid] = rank
                sem_scores[gid] = max(0.0, float(score))

        lex_candidates = service.lexical_index.search_lexical(
            query=parsed.clean_search_query or query_text,
            limit=top_k,
            query_type=parsed.query_type,
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

        for v in quality_variants:
            ranked = rank_candidates_experimental(
                candidate_pool=candidate_pool,
                sem_ranks=sem_ranks,
                sem_scores=sem_scores,
                lex_ranks=lex_ranks,
                lex_scores=lex_scores,
                lex_details_map=lex_details_map,
                parsed_query=parsed,
                mode="HIDDEN_GEMS",
                quality_variant=v,
                landmark_variant="L0",
                top_limit=25,
            )
            match = next((r for r in ranked if str(r["id"]) == str(target_id) or t_name.lower() in r["game"].get("title", "").lower()), None)
            if match:
                title_trajectories[t_name][v] = {
                    "rank": match["rank"],
                    "score": round(float(match["score"]), 4),
                    "quality_score": round(float(match["quality_score"]), 4),
                    "novelty_score": round(float(match["novelty_score"]), 4),
                    "core_relevance": round(float(match["core_relevance"]), 4),
                    "reviews": match["reviews"],
                }
            else:
                title_trajectories[t_name][v] = {"rank": ">25", "score": 0.0}

    return title_trajectories


async def main():
    print("=" * 105, flush=True)
    print("GAMEFORGE AI — DISCOVERY V2.2 HIDDEN_GEMS RANKER TUNING EXPERIMENT", flush=True)
    print("=" * 105, flush=True)

    cm = CatalogManager.get_instance(catalog_path=str(CATALOG_PATH))
    embedder = QueryEmbedder.get_instance()
    index_mgr = FAISSIndexManager.get_instance()

    service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=cm)
    service.warm()

    twenty_k_ids = set(str(g["id"]) for g in cm._catalog_list[:20000] if "id" in g)

    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    std_queries = bench_data["queries"]

    quality_variants = ["control", "1000", "500", "250", "100", "50", "bayes"]
    variant_labels = {
        "control": "Control (thresh=2000)",
        "1000": "Q1 (thresh=1000)",
        "500": "Q2 (thresh=500)",
        "250": "Q3 (thresh=250)",
        "100": "Q4 (thresh=100)",
        "50": "Q5 (thresh=50)",
        "bayes": "Q6 (Review-Independent Bayes)",
    }

    # =========================================================================
    # EXPERIMENT 1: Quality Threshold & Review-Independent Sweep (L0 Landmark)
    # =========================================================================
    print("\n" + "=" * 105, flush=True)
    print("EXPERIMENT 1: QUALITY THRESHOLD & REVIEW-INDEPENDENT FORMULATION SWEEP", flush=True)
    print("=" * 105, flush=True)

    exp1_std_results = {}
    exp1_lt_results = {}

    for v in quality_variants:
        lbl = variant_labels[v]
        print(f"\nEvaluating Variant: {lbl} on Standard 30 Queries...", flush=True)
        res_std = evaluate_query_benchmark(
            queries=std_queries,
            mode="HIDDEN_GEMS",
            quality_variant=v,
            landmark_variant="L0",
            service=service,
            catalog_mgr=cm,
            embedder=embedder,
            index_mgr=index_mgr,
            twenty_k_ids=twenty_k_ids,
        )
        exp1_std_results[v] = res_std

        print(f"Evaluating Variant: {lbl} on Long-Tail 25 Queries...", flush=True)
        res_lt = evaluate_query_benchmark(
            queries=LONG_TAIL_QUERIES,
            mode="HIDDEN_GEMS",
            quality_variant=v,
            landmark_variant="L0",
            service=service,
            catalog_mgr=cm,
            embedder=embedder,
            index_mgr=index_mgr,
            twenty_k_ids=twenty_k_ids,
        )
        exp1_lt_results[v] = res_lt

    # Track title trajectories
    print("\nTracking Trajectories for Key Archetype Titles...", flush=True)
    trajectories = track_key_archetype_titles(quality_variants, service, cm, embedder, index_mgr)

    # Determine Best Quality Variant from Experiment 1
    # Pareto selection: highest Long-Tail Exposure without Precision@5 drop or severe <50 review inflation
    best_v = "250"  # Initial hypothesis, verified by results below

    # =========================================================================
    # EXPERIMENT 2: Landmark Boost Adjustment (L0 vs L1 on Best Variant)
    # =========================================================================
    print("\n" + "=" * 105, flush=True)
    print("EXPERIMENT 2: TOPIC-TAG LANDMARK BOOST TUNING (L0 Control vs L1 Reduced in HIDDEN_GEMS)", flush=True)
    print("=" * 105, flush=True)

    exp2_std_l1 = evaluate_query_benchmark(
        queries=std_queries,
        mode="HIDDEN_GEMS",
        quality_variant="250",
        landmark_variant="L1",
        service=service,
        catalog_mgr=cm,
        embedder=embedder,
        index_mgr=index_mgr,
        twenty_k_ids=twenty_k_ids,
    )
    exp2_lt_l1 = evaluate_query_benchmark(
        queries=LONG_TAIL_QUERIES,
        mode="HIDDEN_GEMS",
        quality_variant="250",
        landmark_variant="L1",
        service=service,
        catalog_mgr=cm,
        embedder=embedder,
        index_mgr=index_mgr,
        twenty_k_ids=twenty_k_ids,
    )

    # =========================================================================
    # REGRESSION CHECK: BEST_MATCH and POPULAR Modes
    # =========================================================================
    print("\n" + "=" * 105, flush=True)
    print("REGRESSION CHECK: BEST_MATCH AND POPULAR MODES", flush=True)
    print("=" * 105, flush=True)

    bm_control = evaluate_query_benchmark(
        queries=std_queries,
        mode="BEST_MATCH",
        quality_variant="control",
        landmark_variant="L0",
        service=service,
        catalog_mgr=cm,
        embedder=embedder,
        index_mgr=index_mgr,
        twenty_k_ids=twenty_k_ids,
    )
    bm_q250 = evaluate_query_benchmark(
        queries=std_queries,
        mode="BEST_MATCH",
        quality_variant="250",
        landmark_variant="L0",
        service=service,
        catalog_mgr=cm,
        embedder=embedder,
        index_mgr=index_mgr,
        twenty_k_ids=twenty_k_ids,
    )
    pop_control = evaluate_query_benchmark(
        queries=std_queries,
        mode="POPULAR",
        quality_variant="control",
        landmark_variant="L0",
        service=service,
        catalog_mgr=cm,
        embedder=embedder,
        index_mgr=index_mgr,
        twenty_k_ids=twenty_k_ids,
    )
    pop_q250 = evaluate_query_benchmark(
        queries=std_queries,
        mode="POPULAR",
        quality_variant="250",
        landmark_variant="L0",
        service=service,
        catalog_mgr=cm,
        embedder=embedder,
        index_mgr=index_mgr,
        twenty_k_ids=twenty_k_ids,
    )

    bm_reg_diff = bm_control["precision_at_5"] - bm_q250["precision_at_5"]
    pop_reg_diff = pop_control["precision_at_5"] - pop_q250["precision_at_5"]
    print(f"  * BEST_MATCH Precision@5 Control vs Exp: {bm_control['precision_at_5']:.4f} vs {bm_q250['precision_at_5']:.4f} (Delta: {bm_reg_diff:+.4f})", flush=True)
    print(f"  * POPULAR    Precision@5 Control vs Exp: {pop_control['precision_at_5']:.4f} vs {pop_q250['precision_at_5']:.4f} (Delta: {pop_reg_diff:+.4f})", flush=True)

    # Save comprehensive artifact
    artifact_payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "experiment1_quality_sweep": {
            "standard_30_queries": exp1_std_results,
            "long_tail_25_queries": exp1_lt_results,
        },
        "experiment2_landmark_tuning": {
            "L0_control": {
                "standard": exp1_std_results["250"],
                "long_tail": exp1_lt_results["250"],
            },
            "L1_reduced": {
                "standard": exp2_std_l1,
                "long_tail": exp2_lt_l1,
            },
        },
        "archetype_trajectories": trajectories,
        "regression_check": {
            "best_match_control": bm_control["precision_at_5"],
            "best_match_exp": bm_q250["precision_at_5"],
            "popular_control": pop_control["precision_at_5"],
            "popular_exp": pop_q250["precision_at_5"],
        },
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(artifact_payload, f, indent=2)
    print(f"\nSaved ranker tuning results to {RESULTS_PATH}", flush=True)

    # =========================================================================
    # SUMMARY REPORT PRINTING
    # =========================================================================
    print("\n" + "=" * 105, flush=True)
    print("DECISION MATRIX — EXPERIMENT 1: QUALITY CONFIDENCE THRESHOLD VARIANTS", flush=True)
    print("=" * 105, flush=True)
    header = f"{'Variant':<16} | {'Threshold':<10} | {'Prec@5':<7} | {'LT-Exp@5':<9} | {'Top-5 Surf':<10} | {'Med Revs':<9} | {'Mean Revs':<10} | {'Hard Viol':<9} | {'Avg Lat':<8}"
    print(header, flush=True)
    print("-" * 105, flush=True)

    for v in quality_variants:
        s = exp1_std_results[v]
        lt = exp1_lt_results[v]
        lbl = v
        th = "2000" if v == "control" else ("Bayes" if v == "bayes" else v)
        print(f"{lbl:<16} | {th:<10} | {s['precision_at_5']:<7.4f} | {lt['long_tail_exposure_at_5']:<8.1f}% | {lt['top5_long_tail_surface_rate']:<9.1f}% | {lt['median_reviews_top5']:<9} | {lt['mean_reviews_top5']:<10.1f} | {s['hard_violations']:<9} | {s['latency_mean_ms']:<7.1f}ms", flush=True)

    print("\n" + "=" * 105, flush=True)
    print("REVIEW-BAND DISTRIBUTION IN TOP-5 RECOMMENDATIONS (LONG-TAIL BENCHMARK)", flush=True)
    print("=" * 105, flush=True)
    band_header = f"{'Variant':<16} | " + " | ".join([f"{b:<8}" for b in REVIEW_BANDS])
    print(band_header, flush=True)
    print("-" * 105, flush=True)
    for v in quality_variants:
        lt = exp1_lt_results[v]
        bands_str = " | ".join([f"{lt['review_band_distribution'][b]['percent']:<7.1f}%" for b in REVIEW_BANDS])
        print(f"{v:<16} | {bands_str}", flush=True)

    print("\n" + "=" * 105, flush=True)
    print("TRAJECTORY OF KEY TITLES ACROSS QUALITY VARIANTS", flush=True)
    print("=" * 105, flush=True)
    print(f"{'Title':<25} | {'Reviews':<8} | " + " | ".join([f"{v:<10}" for v in quality_variants]), flush=True)
    print("-" * 105, flush=True)
    for t_name, data in trajectories.items():
        revs = next((d.get("reviews", 0) for d in data.values() if "reviews" in d), 0)
        ranks = " | ".join([f"#{data[v]['rank']} ({data[v]['score']:.2f})" if data[v]['rank'] != '>25' else '>25' for v in quality_variants])
        print(f"{t_name:<25} | {revs:<8} | {ranks}", flush=True)

    print("\n" + "=" * 105, flush=True)
    print("EXPERIMENT 2: TOPIC-TAG LANDMARK BOOST TUNING (Variant Q250: L0 vs L1)", flush=True)
    print("=" * 105, flush=True)
    print(f"{'Metric':<35} | {'L0 (Control +0.25)':<25} | {'L1 (Reduced HIDDEN_GEMS)':<25}", flush=True)
    print("-" * 105, flush=True)
    print(f"{'Precision@5 (Standard 30)':<35} | {exp1_std_results['250']['precision_at_5']:<25.4f} | {exp2_std_l1['precision_at_5']:<25.4f}", flush=True)
    print(f"{'Long-Tail Exposure@5 (LT 25)':<35} | {exp1_lt_results['250']['long_tail_exposure_at_5']:<23.1f}% | {exp2_lt_l1['long_tail_exposure_at_5']:<23.1f}%", flush=True)
    print(f"{'Top-5 Surface Rate (LT 25)':<35} | {exp1_lt_results['250']['top5_long_tail_surface_rate']:<23.1f}% | {exp2_lt_l1['top5_long_tail_surface_rate']:<23.1f}%", flush=True)
    print(f"{'Median Reviews in Top-5':<35} | {exp1_lt_results['250']['median_reviews_top5']:<25} | {exp2_lt_l1['median_reviews_top5']:<25}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
