"""
GameForge AI — Discovery V2.3 HIDDEN_GEMS Fine-Grained Quality Threshold Sweep.

Performs a fine-grained sweep across quality confidence thresholds between 100 and 250 reviews:
- T2000 = 2000 (Control)
- T250 = 250
- T200 = 200
- T175 = 175
- T150 = 150
- T125 = 125
- T100 = 100

Evaluates:
- Standard 30-Query Benchmark (Precision@5, Hard Violations, Latency)
- Dedicated 25-Query Long-Tail Benchmark (Long-Tail Exposure@5, Surface Rate, Reach Rate, Mean/Median Reviews)
- 12 Fine-Grained Review Bands
- Cumulative Low-Review Concentration (<100, <125, <150, <200, <250) vs Mid-Tail Concentration (100-1999)
- Top-20 to Top-5 score margin analysis
- Trajectories of key archetype titles (Shapebreaker, MOTHERED, Floating Farmer, Colony Ship, Slay the Spire, Farming Sim 2013)
- Knee point identification
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
RESULTS_PATH = BACKEND_DIR / "data" / "fine_threshold_sweep_results.json"

FINE_BANDS = [
    ("1-49", 1, 49),
    ("50-99", 50, 99),
    ("100-124", 100, 124),
    ("125-149", 125, 149),
    ("150-174", 150, 174),
    ("175-199", 175, 199),
    ("200-249", 200, 249),
    ("250-499", 250, 499),
    ("500-999", 500, 999),
    ("1000-1999", 1000, 1999),
    ("2000-4999", 2000, 4999),
    ("5000+", 5000, 1000000000),
]


def classify_fine_band(reviews: int) -> str:
    for name, low, high in FINE_BANDS:
        if low <= reviews <= high:
            return name
    return "5000+"


def rank_with_threshold(
    candidate_pool: Dict[str, Dict[str, Any]],
    sem_ranks: Dict[str, int],
    sem_scores: Dict[str, float],
    lex_ranks: Dict[str, int],
    lex_scores: Dict[str, float],
    lex_details_map: Dict[str, Dict[str, Any]],
    parsed_query: ParsedQuery,
    mode: str,
    threshold: float,
    top_limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Rank candidates using exact production formulas, substituting only quality threshold in HIDDEN_GEMS.
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

        # Topic Tag Landmark Boost (Standard Fixed L0)
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

        # Quality Score Calculation
        if mode == "HIDDEN_GEMS":
            qual_factor = pos_pct * min(1.0, reviews / threshold)
            quality_score = QUALITY_WEIGHT * qual_factor * mode_adj.quality_mult
        else:
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

    # Soft franchise deduplication
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


def evaluate_threshold_suite(
    queries: List[Dict[str, Any]],
    threshold: float,
    mode: str,
    service: DiscoveryService,
    catalog_mgr: CatalogManager,
    embedder: QueryEmbedder,
    index_mgr: FAISSIndexManager,
    twenty_k_ids: Set[str],
) -> Dict[str, Any]:
    """
    Run evaluation across query set for a specific threshold value.
    """
    pool = DiscoveryCandidatePool.REVIEWED_ONLY
    top_k = 50

    p5_scores = []
    latencies = []
    hard_violations = 0
    intent_correct = 0

    all_top5_reviews = []
    qualifying_top5_longtail = 0  # <= 5000 reviews
    zero_review_count = 0
    total_top5_slots = 0

    band_counts = {b[0]: 0 for b in FINE_BANDS}

    top20_longtail_reach = 0
    top5_longtail_surface = 0
    best_longtail_ranks = []
    margins = []

    for q in queries:
        qid = q["id"]
        q_text = q["query"]

        t0 = time.perf_counter()
        parsed_query = service.query_parser.parse(q_text)
        embed_text = parsed_query.clean_search_query or q_text
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

        ranked_top20 = rank_with_threshold(
            candidate_pool=candidate_pool,
            sem_ranks=sem_ranks,
            sem_scores=sem_scores,
            lex_ranks=lex_ranks,
            lex_scores=lex_scores,
            lex_details_map=lex_details_map,
            parsed_query=parsed_query,
            mode=mode,
            threshold=threshold,
            top_limit=20,
        )
        lat_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(lat_ms)

        top5 = ranked_top20[:5]
        ranks_6_to_20 = ranked_top20[5:]

        # Intent accuracy
        if q.get("expected_intent") and parsed_query.query_type == q["expected_intent"]:
            intent_correct += 1

        # Hard constraints
        if q.get("must_not_contain_genres"):
            banned_g = {g.lower() for g in q["must_not_contain_genres"]}
            for r in top5:
                game_g = {g.lower() for g in r["game"].get("genres", [])}
                if banned_g.intersection(game_g):
                    hard_violations += 1
                    break

        if q.get("must_not_contain_modes"):
            banned_m = {m.lower() for m in q["must_not_contain_modes"]}
            for r in top5:
                game_m = {m.lower() for m in r["game"].get("player_modes", [])}
                if banned_m.intersection(game_m):
                    hard_violations += 1
                    break

        if q.get("must_be_free"):
            for r in top5:
                if not r["game"].get("is_free", False):
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

        # Reviews & bands
        for r in top5:
            revs = r["reviews"]
            all_top5_reviews.append(revs)
            total_top5_slots += 1
            if revs <= 5000:
                qualifying_top5_longtail += 1
            if revs == 0:
                zero_review_count += 1
            band = classify_fine_band(revs)
            band_counts[band] += 1

        # Long-tail candidate tracking
        lt_in_top20 = [r for r in ranked_top20 if r["id"] not in twenty_k_ids]
        lt_in_top5 = [r for r in top5 if r["id"] not in twenty_k_ids]

        if lt_in_top20:
            top20_longtail_reach += 1
            best_longtail_ranks.append(lt_in_top20[0]["rank"])
        if lt_in_top5:
            top5_longtail_surface += 1

        # Top-20 to Top-5 score margin
        lt_outside_top5 = [r for r in ranks_6_to_20 if r["id"] not in twenty_k_ids]
        if lt_outside_top5 and top5:
            lowest_top5_score = top5[-1]["score"]
            highest_loser_score = lt_outside_top5[0]["score"]
            margin = lowest_top5_score - highest_loser_score
            margins.append(margin)

    num_q = len(queries)
    slots = max(1, total_top5_slots)

    # Cumulative Review Band Concentrations
    lt_100 = sum(band_counts[b[0]] for b in FINE_BANDS if b[2] < 100) / slots * 100.0
    lt_125 = sum(band_counts[b[0]] for b in FINE_BANDS if b[2] < 125) / slots * 100.0
    lt_150 = sum(band_counts[b[0]] for b in FINE_BANDS if b[2] < 150) / slots * 100.0
    lt_200 = sum(band_counts[b[0]] for b in FINE_BANDS if b[2] < 200) / slots * 100.0
    lt_250 = sum(band_counts[b[0]] for b in FINE_BANDS if b[2] < 250) / slots * 100.0
    mid_tail = sum(band_counts[b[0]] for b in FINE_BANDS if 100 <= b[1] and b[2] < 2000) / slots * 100.0

    return {
        "threshold": threshold,
        "precision_at_5": round(float(np.mean(p5_scores)), 4),
        "hard_violations": hard_violations,
        "intent_accuracy": round(intent_correct / max(1, num_q), 4),
        "latency_mean_ms": round(float(np.mean(latencies)), 2),
        "latency_p95_ms": round(float(np.percentile(latencies, 95)), 2),
        "long_tail_exposure_at_5": round(qualifying_top5_longtail / slots * 100.0, 1),
        "top20_long_tail_reach_rate": round(top20_longtail_reach / max(1, num_q) * 100.0, 1),
        "top5_long_tail_surface_rate": round(top5_longtail_surface / max(1, num_q) * 100.0, 1),
        "avg_best_long_tail_rank": round(float(np.mean(best_longtail_ranks)), 2) if best_longtail_ranks else 20.0,
        "median_best_long_tail_rank": int(np.median(best_longtail_ranks)) if best_longtail_ranks else 20,
        "mean_reviews_top5": round(float(np.mean(all_top5_reviews)), 1) if all_top5_reviews else 0.0,
        "median_reviews_top5": int(np.median(all_top5_reviews)) if all_top5_reviews else 0,
        "zero_review_count": zero_review_count,
        "fine_band_distribution": {
            b[0]: {
                "count": band_counts[b[0]],
                "percent": round(band_counts[b[0]] / slots * 100.0, 1),
            }
            for b in FINE_BANDS
        },
        "cumulative_concentrations": {
            "lt_100": round(lt_100, 1),
            "lt_125": round(lt_125, 1),
            "lt_150": round(lt_150, 1),
            "lt_200": round(lt_200, 1),
            "lt_250": round(lt_250, 1),
            "mid_tail_100_1999": round(mid_tail, 1),
        },
        "score_margins": {
            "mean": round(float(np.mean(margins)), 4) if margins else 0.0,
            "median": round(float(np.median(margins)), 4) if margins else 0.0,
            "min": round(float(np.min(margins)), 4) if margins else 0.0,
            "max": round(float(np.max(margins)), 4) if margins else 0.0,
        },
    }


def track_titles_fine_sweep(
    thresholds: List[float],
    service: DiscoveryService,
    catalog_mgr: CatalogManager,
    embedder: QueryEmbedder,
    index_mgr: FAISSIndexManager,
) -> Dict[str, Dict[str, Any]]:
    """
    Track key title trajectories across the fine sweep.
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
    trajectories = {t: {} for t in targets}

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

        for th in thresholds:
            lbl = f"T{int(th)}"
            ranked = rank_with_threshold(
                candidate_pool=candidate_pool,
                sem_ranks=sem_ranks,
                sem_scores=sem_scores,
                lex_ranks=lex_ranks,
                lex_scores=lex_scores,
                lex_details_map=lex_details_map,
                parsed_query=parsed,
                mode="HIDDEN_GEMS",
                threshold=th,
                top_limit=25,
            )
            match = next((r for r in ranked if str(r["id"]) == str(target_id) or t_name.lower() in r["game"].get("title", "").lower()), None)
            if match:
                trajectories[t_name][lbl] = {
                    "rank": match["rank"],
                    "score": round(float(match["score"]), 4),
                    "quality_score": round(float(match["quality_score"]), 4),
                    "novelty_score": round(float(match["novelty_score"]), 4),
                    "core_relevance": round(float(match["core_relevance"]), 4),
                    "reviews": match["reviews"],
                }
            else:
                trajectories[t_name][lbl] = {"rank": ">25", "score": 0.0}

    return trajectories


async def main():
    print("=" * 115, flush=True)
    print("GAMEFORGE AI — DISCOVERY V2.3 HIDDEN_GEMS FINE-GRAINED QUALITY THRESHOLD SWEEP", flush=True)
    print("=" * 115, flush=True)

    cm = CatalogManager.get_instance(catalog_path=str(CATALOG_PATH))
    embedder = QueryEmbedder.get_instance()
    index_mgr = FAISSIndexManager.get_instance()

    service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=cm)
    service.warm()

    twenty_k_ids = set(str(g["id"]) for g in cm._catalog_list[:20000] if "id" in g)

    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    std_queries = bench_data["queries"]

    thresholds = [2000.0, 250.0, 200.0, 175.0, 150.0, 125.0, 100.0]
    thresh_labels = [f"T{int(t)}" for t in thresholds]

    std_results = {}
    lt_results = {}

    for th in thresholds:
        lbl = f"T{int(th)}"
        print(f"\nRunning Threshold {lbl} on Standard 30 Queries...", flush=True)
        res_std = evaluate_threshold_suite(
            queries=std_queries,
            threshold=th,
            mode="HIDDEN_GEMS",
            service=service,
            catalog_mgr=cm,
            embedder=embedder,
            index_mgr=index_mgr,
            twenty_k_ids=twenty_k_ids,
        )
        std_results[lbl] = res_std

        print(f"Running Threshold {lbl} on Long-Tail 25 Queries...", flush=True)
        res_lt = evaluate_threshold_suite(
            queries=LONG_TAIL_QUERIES,
            threshold=th,
            mode="HIDDEN_GEMS",
            service=service,
            catalog_mgr=cm,
            embedder=embedder,
            index_mgr=index_mgr,
            twenty_k_ids=twenty_k_ids,
        )
        lt_results[lbl] = res_lt

    # Track title trajectories
    print("\nTracking Trajectories for Key Archetype Titles...", flush=True)
    trajectories = track_titles_fine_sweep(thresholds, service, cm, embedder, index_mgr)

    # Regression check on BEST_MATCH and POPULAR
    print("\nVerifying Regression on BEST_MATCH and POPULAR...", flush=True)
    bm_control = evaluate_threshold_suite(std_queries, 2000.0, "BEST_MATCH", service, cm, embedder, index_mgr, twenty_k_ids)
    bm_t150 = evaluate_threshold_suite(std_queries, 150.0, "BEST_MATCH", service, cm, embedder, index_mgr, twenty_k_ids)
    pop_control = evaluate_threshold_suite(std_queries, 2000.0, "POPULAR", service, cm, embedder, index_mgr, twenty_k_ids)
    pop_t150 = evaluate_threshold_suite(std_queries, 150.0, "POPULAR", service, cm, embedder, index_mgr, twenty_k_ids)

    print(f"  * BEST_MATCH Precision@5 Control vs T150: {bm_control['precision_at_5']:.4f} vs {bm_t150['precision_at_5']:.4f} (Delta: {bm_control['precision_at_5'] - bm_t150['precision_at_5']:+.4f})", flush=True)
    print(f"  * POPULAR    Precision@5 Control vs T150: {pop_control['precision_at_5']:.4f} vs {pop_t150['precision_at_5']:.4f} (Delta: {pop_control['precision_at_5'] - pop_t150['precision_at_5']:+.4f})", flush=True)

    # Save artifact
    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "thresholds_tested": thresholds,
        "standard_30_results": std_results,
        "long_tail_25_results": lt_results,
        "title_trajectories": trajectories,
        "regression_check": {
            "bm_control": bm_control["precision_at_5"],
            "bm_t150": bm_t150["precision_at_5"],
            "pop_control": pop_control["precision_at_5"],
            "pop_t150": pop_t150["precision_at_5"],
        },
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved fine threshold sweep results to {RESULTS_PATH}", flush=True)

    # =========================================================================
    # SECTION A: THRESHOLD SWEEP TABLE
    # =========================================================================
    print("\n" + "=" * 115, flush=True)
    print("SECTION A: FINE-GRAINED THRESHOLD SWEEP DECISION MATRIX", flush=True)
    print("=" * 115, flush=True)
    header = f"{'Threshold':<11} | {'Prec@5':<7} | {'LT-Exp@5':<9} | {'Top5 Surf':<9} | {'<100 Rev':<9} | {'100-1999':<9} | {'Med Revs':<8} | {'Mean Revs':<9} | {'Avg Margin':<10} | {'Viol':<5} | {'Avg Lat':<7}"
    print(header, flush=True)
    print("-" * 115, flush=True)

    for th in thresholds:
        lbl = f"T{int(th)}"
        s = std_results[lbl]
        lt = lt_results[lbl]
        c = lt["cumulative_concentrations"]
        m = lt["score_margins"]
        print(f"{lbl:<11} | {s['precision_at_5']:<7.4f} | {lt['long_tail_exposure_at_5']:<8.1f}% | {lt['top5_long_tail_surface_rate']:<8.1f}% | {c['lt_100']:<8.1f}% | {c['mid_tail_100_1999']:<8.1f}% | {lt['median_reviews_top5']:<8} | {lt['mean_reviews_top5']:<9.1f} | {m['mean']:<10.4f} | {s['hard_violations']:<5} | {s['latency_mean_ms']:<6.1f}ms", flush=True)

    # =========================================================================
    # SECTION B: 12 FINE REVIEW BANDS
    # =========================================================================
    print("\n" + "=" * 115, flush=True)
    print("SECTION B: 12 FINE REVIEW BANDS (% OF ALL TOP-5 RECOMMENDATIONS IN LONG-TAIL BENCHMARK)", flush=True)
    print("=" * 115, flush=True)
    b_header = f"{'Threshold':<11} | " + " | ".join([f"{b[0]:<7}" for b in FINE_BANDS])
    print(b_header, flush=True)
    print("-" * 115, flush=True)
    for th in thresholds:
        lbl = f"T{int(th)}"
        lt = lt_results[lbl]
        row = " | ".join([f"{lt['fine_band_distribution'][b[0]]['percent']:<6.1f}%" for b in FINE_BANDS])
        print(f"{lbl:<11} | {row}", flush=True)

    # =========================================================================
    # SECTION C: CUMULATIVE CONCENTRATIONS
    # =========================================================================
    print("\n" + "=" * 115, flush=True)
    print("SECTION C: CUMULATIVE LOW-REVIEW & MID-TAIL CONCENTRATIONS", flush=True)
    print("=" * 115, flush=True)
    c_header = f"{'Threshold':<11} | {'<100 Rev':<10} | {'<125 Rev':<10} | {'<150 Rev':<10} | {'<200 Rev':<10} | {'<250 Rev':<10} | {'100-1999 (Mid-Tail)':<20}"
    print(c_header, flush=True)
    print("-" * 115, flush=True)
    for th in thresholds:
        lbl = f"T{int(th)}"
        c = lt_results[lbl]["cumulative_concentrations"]
        print(f"{lbl:<11} | {c['lt_100']:<9.1f}% | {c['lt_125']:<9.1f}% | {c['lt_150']:<9.1f}% | {c['lt_200']:<9.1f}% | {c['lt_250']:<9.1f}% | {c['mid_tail_100_1999']:<19.1f}%", flush=True)

    # =========================================================================
    # SECTION E: TITLE TRAJECTORIES
    # =========================================================================
    print("\n" + "=" * 115, flush=True)
    print("SECTION E: REPRESENTATIVE TITLE TRAJECTORIES ACROSS SWEEP", flush=True)
    print("=" * 115, flush=True)
    print(f"{'Title':<25} | {'Reviews':<8} | " + " | ".join([f"{lbl:<9}" for lbl in thresh_labels]), flush=True)
    print("-" * 115, flush=True)
    for t_name, data in trajectories.items():
        revs = next((d.get("reviews", 0) for d in data.values() if "reviews" in d), 0)
        ranks = " | ".join([f"#{data[lbl]['rank']} ({data[lbl]['score']:.2f})" if data[lbl]['rank'] != '>25' else '>25' for lbl in thresh_labels])
        print(f"{t_name:<25} | {revs:<8} | {ranks}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
