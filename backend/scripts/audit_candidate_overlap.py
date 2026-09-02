"""
GameForge AI — Discovery V2 Candidate Overlap & Long-Tail Recall Diagnostic.

Instruments and compares the candidate lifecycle between:
A: 20k Candidate Universe (acclaimed head)
B: 87,890 Reviewed-Only Candidate Universe (full non-zero review long tail)

Traces candidates across 6 discrete pipeline stages:
1. Dense Retrieval Top-50 (FAISS)
2. Lexical Retrieval Top-50 (Inverted Index)
3. RRF Candidates (Fused dense + lexical)
4. Post-Hard-Filter Candidates (Passing banned genres, modes, price, match threshold)
5. Post-Ranking Top-20 (After quality, novelty, and mode multipliers)
6. Final Top-5 (After MMR diversification)

Calculates stage-by-stage overlap, new candidate additions, reach rates,
and classifies each query into its exact bottleneck stage (Cases A to F).
"""

import asyncio
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import faiss
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
from app.search.lexical import normalize_string
from app.search.query_parser import ParsedQuery, QueryParser
from app.search.ranker import MIN_MATCH_SCORE_THRESHOLD, Ranker
from app.search.ranking_config import DISCOVERY_MODES, DEFAULT_MODE
from app.services.discovery_service import DiscoveryService

CATALOG_PATH = BACKEND_DIR / 'data' / 'processed' / 'games_catalog.json'
BENCHMARK_FILE = BACKEND_DIR / 'tests' / 'data' / 'discovery_benchmark.json'
RESULTS_PATH = BACKEND_DIR / 'data' / 'candidate_overlap_diagnostic.json'

INDEX_20K = BACKEND_DIR / 'data' / 'processed' / 'games_index.faiss'
META_20K = BACKEND_DIR / 'data' / 'processed' / 'index_meta.json'
INDEX_REV = BACKEND_DIR / 'data' / 'benchmark_indexes' / 'games_index_reviewed_only.faiss'
META_REV = BACKEND_DIR / 'data' / 'benchmark_indexes' / 'index_meta_reviewed_only.json'


# Dedicated 25-Query Long-Tail Discovery Benchmark
LONG_TAIL_QUERIES = [
    {
        "id": "lt01",
        "query": "turn-based submarine survival",
        "category": "Niche Mechanics",
        "description": "Tactical submarine command and survival simulation",
    },
    {
        "id": "lt02",
        "query": "cozy automation game with trains",
        "category": "Aesthetic Automation",
        "description": "Relaxing logistics and train network builder",
    },
    {
        "id": "lt03",
        "query": "cyberpunk detective RPG",
        "category": "Narrative RPG",
        "description": "Investigative noir cyber-sleuth roleplaying",
    },
    {
        "id": "lt04",
        "query": "deckbuilder with city-building",
        "category": "Hybrid Genre",
        "description": "Card-driven urban construction and tile placement",
    },
    {
        "id": "lt05",
        "query": "co-op survival without zombies",
        "category": "Negative Constraint",
        "description": "Wilderness/environmental survival multiplayer without undead",
    },
    {
        "id": "lt06",
        "query": "space trading and exploration",
        "category": "Space Sim",
        "description": "Open-galaxy mercantile exploration and ship upgrades",
    },
    {
        "id": "lt07",
        "query": "relaxing factory management",
        "category": "Chill Logistics",
        "description": "Low-stress conveyor belt assembly line simulator",
    },
    {
        "id": "lt08",
        "query": "tactical RPG with squad customization",
        "category": "Tactics",
        "description": "Grid-based squad turn-based combat with deep loadouts",
    },
    {
        "id": "lt09",
        "query": "story-driven mystery without horror",
        "category": "Narrative Mystery",
        "description": "Thoughtful investigation without jump scares or gore",
    },
    {
        "id": "lt10",
        "query": "indie farming with exploration",
        "category": "Cozy Adventure",
        "description": "Agriculture simulator combined with dungeon or island exploration",
    },
    {
        "id": "lt11",
        "query": "hardcore space mining simulator",
        "category": "Deep Sim",
        "description": "Physics-based asteroid prospecting and salvage",
    },
    {
        "id": "lt12",
        "query": "pixel art metroidvania with parry mechanics",
        "category": "Action Platformer",
        "description": "Challenging 2D exploration with timing-based deflection",
    },
    {
        "id": "lt13",
        "query": "isometric colony builder in snow",
        "category": "Survival Builder",
        "description": "Harsh winter settlement survival management",
    },
    {
        "id": "lt14",
        "query": "stealth puzzle game with hacking",
        "category": "Cyber Stealth",
        "description": "Terminal infiltration and tactical evasion",
    },
    {
        "id": "lt15",
        "query": "physics based puzzle platformer",
        "category": "Physics Puzzle",
        "description": "Mechanics driven kinetic platform navigation",
    },
    {
        "id": "lt16",
        "query": "turn based roguelike dungeon crawler",
        "category": "Classic Roguelike",
        "description": "Grid-step tactical procedurally generated dungeon delve",
    },
    {
        "id": "lt17",
        "query": "underwater base building and craft",
        "category": "Aquatic Craft",
        "description": "Sub-surface habitat construction and resource gathering",
    },
    {
        "id": "lt18",
        "query": "medieval blacksmithing simulation",
        "category": "Crafting Sim",
        "description": "Forging weapons and merchant shop management",
    },
    {
        "id": "lt19",
        "query": "minimalist logic puzzle with ambient music",
        "category": "Zen Puzzle",
        "description": "Clean aesthetic abstract deduction with calm soundscape",
    },
    {
        "id": "lt20",
        "query": "atmospheric post-apocalyptic train journey",
        "category": "Atmospheric Narrative",
        "description": "Locomotive voyage through wasteland with resource upkeep",
    },
    {
        "id": "lt21",
        "query": "roguelike deckbuilder with dice mechanics",
        "category": "Dice / Card Hybrid",
        "description": "Turn-based card battles augmented by stochastic dice rolls",
    },
    {
        "id": "lt22",
        "query": "top-down twin-stick mecha combat",
        "category": "Mech Action",
        "description": "Armored walker shooter with modular chassis upgrades",
    },
    {
        "id": "lt23",
        "query": "village builder with brewing and tavern management",
        "category": "Management Sim",
        "description": "Settlement economy focused on hospitality and brewing",
    },
    {
        "id": "lt24",
        "query": "time loop puzzle adventure",
        "category": "Temporal Mystery",
        "description": "Information-gathering iterative mystery resetting each cycle",
    },
    {
        "id": "lt25",
        "query": "automation programming game",
        "category": "Coding / Logic",
        "description": "Assembly or node-based factory logic and algorithm design",
    },
]


def trace_pipeline_stages(
    query_text: str,
    mode: str,
    pool: DiscoveryCandidatePool,
    service: DiscoveryService,
    catalog_mgr: CatalogManager,
    embedder: QueryEmbedder,
    index_mgr: FAISSIndexManager,
) -> Dict[str, Any]:
    """
    Execute pipeline and instrument each discrete stage, extracting exact ordered candidates.
    """
    top_k = 50
    parsed_query = service.query_parser.parse(query_text)
    
    # 1. Dense Retrieval Top-50
    embed_text = parsed_query.clean_search_query or query_text
    q_vec = embedder.embed_query(embed_text)
    raw_dense = index_mgr.search(q_vec, top_k=top_k, pool=pool)
    
    dense_candidates = []
    for gid, score in raw_dense:
        g = catalog_mgr.get_game(gid)
        if g:
            dense_candidates.append((g, float(score)))

    # 2. Lexical Retrieval Top-50
    lex_candidates = service.lexical_index.search_lexical(
        query=parsed_query.clean_search_query or query_text,
        limit=top_k,
        query_type=parsed_query.query_type,
        candidate_pool=pool,
    )

    # 3. RRF Candidates
    rrf_scores: Dict[str, float] = {}
    candidate_map: Dict[str, Dict[str, Any]] = {}
    k_const = 60.0

    for rank, (game, _) in enumerate(dense_candidates):
        gid = str(game.get("id"))
        rrf_scores[gid] = rrf_scores.get(gid, 0.0) + (1.0 / (k_const + rank + 1))
        candidate_map[gid] = game

    for rank, (game, _, _) in enumerate(lex_candidates):
        gid = str(game.get("id"))
        rrf_scores[gid] = rrf_scores.get(gid, 0.0) + (1.0 / (k_const + rank + 1))
        candidate_map[gid] = game

    sorted_rrf_ids = sorted(rrf_scores.keys(), key=lambda gid: rrf_scores[gid], reverse=True)
    rrf_candidate_list = [(candidate_map[gid], rrf_scores[gid]) for gid in sorted_rrf_ids]

    # 4. Post-Hard-Filter Candidates
    mode_cfg = DISCOVERY_MODES.get(mode, DISCOVERY_MODES["BEST_MATCH"])
    post_filter_candidates = []
    for game, rrf_score in rrf_candidate_list:
        if Ranker.passes_filters(game, filters=None, hard_constraints=parsed_query.hard_constraints):
            post_filter_candidates.append((game, rrf_score))

    # 5. Post-Ranking Top-20 (Scored candidates before MMR diversification)
    scored_candidates = []
    for game, rrf_score in post_filter_candidates:
        match_score = min(1.0, rrf_score * 30.0)
        if match_score >= MIN_MATCH_SCORE_THRESHOLD:
            # Mode quality & novelty adjustments
            rev_cnt = game.get("total_reviews", 0)
            log_rev = np.log10(max(1, rev_cnt))
            
            # Quality & Novelty multipliers from Ranker
            quality_mult = min(1.3, max(0.7, 0.8 + 0.1 * min(5.0, log_rev)))
            novelty_mult = max(0.5, 1.4 - 0.15 * min(6.0, log_rev)) if mode in ["HIDDEN_GEMS", "DISCOVER"] else 1.0
            
            final_score = match_score * quality_mult * novelty_mult
            scored_candidates.append((game, float(final_score)))

    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    post_ranking_top20 = scored_candidates[:20]

    # 6. Final Top-5 (After MMR diversity)
    final_top5_results = Ranker.rank_hybrid(
        semantic_candidates=dense_candidates,
        lexical_candidates=lex_candidates,
        parsed_query=parsed_query,
        limit=5,
        min_threshold=MIN_MATCH_SCORE_THRESHOLD,
        mode=mode,
        index_manager=index_mgr,
    )

    final_top5 = [(r.game, float(r.score)) for r in final_top5_results]

    def format_stage(items: List[Tuple[Any, float]]) -> List[Dict[str, Any]]:
        formatted = []
        for g, score in items:
            if hasattr(g, "id"):
                gid = str(g.id)
                title = str(g.title)
                revs = getattr(g, "total_reviews", 0)
            elif isinstance(g, dict):
                gid = str(g.get("id", ""))
                title = g.get("title", "")
                revs = g.get("total_reviews", 0)
            else:
                gid = str(getattr(g, "id", ""))
                title = str(getattr(g, "title", ""))
                revs = getattr(g, "total_reviews", 0)
            formatted.append({
                "id": gid,
                "title": title,
                "score": round(float(score), 4),
                "reviews": revs,
            })
        return formatted

    return {
        "dense_top50": format_stage(dense_candidates),
        "lexical_top50": format_stage([(g, s) for g, s, _ in lex_candidates]),
        "rrf_candidates": format_stage(rrf_candidate_list),
        "post_filter_candidates": format_stage(post_filter_candidates),
        "post_ranking_top20": format_stage(post_ranking_top20),
        "final_top5": format_stage(final_top5),
    }


def compute_stage_overlap(
    stage_20k: List[Dict[str, Any]],
    stage_rev: List[Dict[str, Any]],
    twenty_k_set: Set[str],
) -> Dict[str, Any]:
    """Compute overlap, Jaccard, and count of genuinely new candidates outside the 20k head."""
    ids_20k = [item["id"] for item in stage_20k]
    ids_rev = [item["id"] for item in stage_rev]
    
    set_20k = set(ids_20k)
    set_rev = set(ids_rev)
    
    inter = set_20k.intersection(set_rev)
    union = set_20k.union(set_rev)
    jaccard = len(inter) / max(1, len(union))
    
    # Genuinely new candidates: records in stage_rev whose IDs were NOT in the 20k catalog head
    new_candidates = [item for item in stage_rev if item["id"] not in twenty_k_set]
    new_ids = [item["id"] for item in new_candidates]

    return {
        "count_20k": len(ids_20k),
        "count_rev": len(ids_rev),
        "intersection_count": len(inter),
        "union_count": len(union),
        "jaccard_similarity": round(jaccard, 4),
        "new_candidates_count": len(new_candidates),
        "new_candidates_sample": [f"{c['title']} (ID:{c['id']}, rev:{c['reviews']})" for c in new_candidates[:3]],
    }


def classify_bottleneck(overlap_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Classify query into Bottleneck Case (A through F).
    """
    new_dense = overlap_data["dense"]["new_candidates_count"]
    new_lex = overlap_data["lexical"]["new_candidates_count"]
    new_rrf = overlap_data["rrf"]["new_candidates_count"]
    new_filter = overlap_data["post_filter"]["new_candidates_count"]
    new_top20 = overlap_data["top20"]["new_candidates_count"]
    new_top5 = overlap_data["top5"]["new_candidates_count"]

    if new_dense == 0 and new_lex == 0:
        return (
            "Case A",
            "Reviewed-only produces no new candidates at retrieval (broader pool did not surface new matches)."
        )
    elif new_rrf == 0:
        return (
            "Case B",
            "Reviewed-only produces new candidates at retrieval, but they disappear before RRF fusion."
        )
    elif new_filter == 0:
        return (
            "Case C",
            "Reviewed-only candidates reach RRF, but disappear during hard constraints / minimum match threshold."
        )
    elif new_top20 == 0:
        return (
            "Case D",
            "Reviewed-only candidates survive hard constraints, but ranking multipliers eliminate them from top-20."
        )
    elif new_top5 == 0:
        return (
            "Case E",
            "Reviewed-only candidates reach top-20, but MMR diversity / final ranking eliminates them from top-5."
        )
    else:
        return (
            "Case F",
            f"Reviewed-only candidates successfully reach final top-5 ({new_top5} new titles)."
        )


async def evaluate_query_diagnostics(
    queries: List[Dict[str, Any]],
    mode: str,
    service: DiscoveryService,
    catalog_mgr: CatalogManager,
    embedder: QueryEmbedder,
    index_mgr: FAISSIndexManager,
    twenty_k_set: Set[str],
) -> List[Dict[str, Any]]:
    results = []

    for q in queries:
        qid = q["id"]
        q_text = q["query"]
        category = q.get("category", "General")

        trace_20k = trace_pipeline_stages(
            query_text=q_text,
            mode=mode,
            pool=DiscoveryCandidatePool.POPULAR_20K,
            service=service,
            catalog_mgr=catalog_mgr,
            embedder=embedder,
            index_mgr=index_mgr,
        )

        trace_rev = trace_pipeline_stages(
            query_text=q_text,
            mode=mode,
            pool=DiscoveryCandidatePool.REVIEWED_ONLY,
            service=service,
            catalog_mgr=catalog_mgr,
            embedder=embedder,
            index_mgr=index_mgr,
        )

        overlap_dense = compute_stage_overlap(trace_20k["dense_top50"], trace_rev["dense_top50"], twenty_k_set)
        overlap_lex = compute_stage_overlap(trace_20k["lexical_top50"], trace_rev["lexical_top50"], twenty_k_set)
        overlap_rrf = compute_stage_overlap(trace_20k["rrf_candidates"], trace_rev["rrf_candidates"], twenty_k_set)
        overlap_filter = compute_stage_overlap(trace_20k["post_filter_candidates"], trace_rev["post_filter_candidates"], twenty_k_set)
        overlap_top20 = compute_stage_overlap(trace_20k["post_ranking_top20"], trace_rev["post_ranking_top20"], twenty_k_set)
        overlap_top5 = compute_stage_overlap(trace_20k["final_top5"], trace_rev["final_top5"], twenty_k_set)

        stage_overlap_dict = {
            "dense": overlap_dense,
            "lexical": overlap_lex,
            "rrf": overlap_rrf,
            "post_filter": overlap_filter,
            "top20": overlap_top20,
            "top5": overlap_top5,
        }

        bottleneck_case, bottleneck_desc = classify_bottleneck(stage_overlap_dict)

        results.append({
            "id": qid,
            "query": q_text,
            "category": category,
            "mode": mode,
            "bottleneck_case": bottleneck_case,
            "bottleneck_description": bottleneck_desc,
            "stage_overlap": stage_overlap_dict,
            "top5_20k": trace_20k["final_top5"],
            "top5_reviewed_only": trace_rev["final_top5"],
        })

    return results


def compute_aggregate_reach_rates(query_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(query_results)
    if n == 0:
        return {}

    has_new_dense = sum(1 for q in query_results if q["stage_overlap"]["dense"]["new_candidates_count"] > 0)
    has_new_lex = sum(1 for q in query_results if q["stage_overlap"]["lexical"]["new_candidates_count"] > 0)
    has_new_retrieval = sum(1 for q in query_results if q["stage_overlap"]["dense"]["new_candidates_count"] > 0 or q["stage_overlap"]["lexical"]["new_candidates_count"] > 0)
    has_new_rrf = sum(1 for q in query_results if q["stage_overlap"]["rrf"]["new_candidates_count"] > 0)
    has_new_filter = sum(1 for q in query_results if q["stage_overlap"]["post_filter"]["new_candidates_count"] > 0)
    has_new_top20 = sum(1 for q in query_results if q["stage_overlap"]["top20"]["new_candidates_count"] > 0)
    has_new_top5 = sum(1 for q in query_results if q["stage_overlap"]["top5"]["new_candidates_count"] > 0)

    avg_jaccard_dense = np.mean([q["stage_overlap"]["dense"]["jaccard_similarity"] for q in query_results])
    avg_jaccard_lex = np.mean([q["stage_overlap"]["lexical"]["jaccard_similarity"] for q in query_results])
    avg_jaccard_rrf = np.mean([q["stage_overlap"]["rrf"]["jaccard_similarity"] for q in query_results])
    avg_jaccard_top5 = np.mean([q["stage_overlap"]["top5"]["jaccard_similarity"] for q in query_results])

    # Case distributions
    case_counts: Dict[str, int] = {}
    for q in query_results:
        c = q["bottleneck_case"]
        case_counts[c] = case_counts.get(c, 0) + 1

    return {
        "total_queries": n,
        "dense_new_candidate_rate": round(has_new_dense / n * 100.0, 1),
        "lexical_new_candidate_rate": round(has_new_lex / n * 100.0, 1),
        "retrieval_new_candidate_rate": round(has_new_retrieval / n * 100.0, 1),
        "rrf_new_candidate_reach_rate": round(has_new_rrf / n * 100.0, 1),
        "post_filter_reach_rate": round(has_new_filter / n * 100.0, 1),
        "top20_reach_rate": round(has_new_top20 / n * 100.0, 1),
        "top5_reach_rate": round(has_new_top5 / n * 100.0, 1),
        "avg_jaccard_dense": round(float(avg_jaccard_dense), 4),
        "avg_jaccard_lexical": round(float(avg_jaccard_lex), 4),
        "avg_jaccard_rrf": round(float(avg_jaccard_rrf), 4),
        "avg_jaccard_top5": round(float(avg_jaccard_top5), 4),
        "case_distribution": {k: f"{v} ({round(v/n*100, 1)}%)" for k, v in sorted(case_counts.items())},
    }


async def main():
    print("=" * 95, flush=True)
    print("GAMEFORGE AI — DISCOVERY V2 CANDIDATE OVERLAP & LONG-TAIL RECALL DIAGNOSTIC", flush=True)
    print("=" * 95, flush=True)

    cm = CatalogManager.get_instance(catalog_path=str(CATALOG_PATH))
    embedder = QueryEmbedder.get_instance()
    index_mgr = FAISSIndexManager.get_instance()

    service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=cm)
    service.warm()

    # Determine exact 20k head ID set
    twenty_k_ids = set(str(g["id"]) for g in cm._catalog_list[:20000] if "id" in g)
    reviewed_ids = set(str(g["id"]) for g in cm._catalog_list if "id" in g and g.get("total_reviews", 0) > 0)
    print(f"Catalog Size: {len(cm._catalog_list)} | 20k Set Size: {len(twenty_k_ids)} | Reviewed Set Size: {len(reviewed_ids)}", flush=True)

    # 1. Run Standard 30-Query Benchmark Diagnostic in HIDDEN_GEMS mode
    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    std_queries = bench_data["queries"]

    print("\n[1/3] Running Candidate Overlap Diagnostic on 30-Query Standard Benchmark (HIDDEN_GEMS mode)...", flush=True)
    std_diag_hg = await evaluate_query_diagnostics(
        queries=std_queries,
        mode="HIDDEN_GEMS",
        service=service,
        catalog_mgr=cm,
        embedder=embedder,
        index_mgr=index_mgr,
        twenty_k_set=twenty_k_ids,
    )
    std_agg_hg = compute_aggregate_reach_rates(std_diag_hg)

    # 2. Run Dedicated 25-Query Long-Tail Discovery Benchmark in HIDDEN_GEMS mode
    print("\n[2/3] Running Long-Tail Candidate Recall Diagnostic on 25 Long-Tail Queries (HIDDEN_GEMS mode)...", flush=True)
    lt_diag_hg = await evaluate_query_diagnostics(
        queries=LONG_TAIL_QUERIES,
        mode="HIDDEN_GEMS",
        service=service,
        catalog_mgr=cm,
        embedder=embedder,
        index_mgr=index_mgr,
        twenty_k_set=twenty_k_ids,
    )
    lt_agg_hg = compute_aggregate_reach_rates(lt_diag_hg)

    # 3. Compute Long-Tail Exposure & Novelty Metrics
    LONG_TAIL_REVIEW_THRESHOLD = 5000  # Games with <= 5k reviews are indie long-tail

    def compute_long_tail_metrics(diag_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_revs_20k = []
        all_revs_rev = []
        qualifying_top5_20k = 0
        qualifying_top5_rev = 0
        total_top5_slots = 0
        zero_cnt_20k = 0
        zero_cnt_rev = 0

        for q in diag_results:
            for r in q["top5_20k"]:
                rev = r["reviews"]
                all_revs_20k.append(rev)
                if rev <= LONG_TAIL_REVIEW_THRESHOLD:
                    qualifying_top5_20k += 1
                if rev == 0:
                    zero_cnt_20k += 1
                total_top5_slots += 1

            for r in q["top5_reviewed_only"]:
                rev = r["reviews"]
                all_revs_rev.append(rev)
                if rev <= LONG_TAIL_REVIEW_THRESHOLD:
                    qualifying_top5_rev += 1
                if rev == 0:
                    zero_cnt_rev += 1

        return {
            "long_tail_threshold": LONG_TAIL_REVIEW_THRESHOLD,
            "exposure_at_5_20k": round(qualifying_top5_20k / max(1, total_top5_slots) * 100.0, 1),
            "exposure_at_5_reviewed_only": round(qualifying_top5_rev / max(1, total_top5_slots) * 100.0, 1),
            "zero_review_count_20k": zero_cnt_20k,
            "zero_review_count_reviewed_only": zero_cnt_rev,
            "reviews_20k": {
                "mean": round(float(np.mean(all_revs_20k)), 1),
                "median": int(np.median(all_revs_20k)),
                "min": int(np.min(all_revs_20k)),
                "max": int(np.max(all_revs_20k)),
            },
            "reviews_reviewed_only": {
                "mean": round(float(np.mean(all_revs_rev)), 1),
                "median": int(np.median(all_revs_rev)),
                "min": int(np.min(all_revs_rev)),
                "max": int(np.max(all_revs_rev)),
            },
        }

    lt_metrics_std = compute_long_tail_metrics(std_diag_hg)
    lt_metrics_niche = compute_long_tail_metrics(lt_diag_hg)

    # 4. Five Archetypes Detailed Stage-by-Stage Trace
    print("\n[3/3] Deep-Tracing 5 Hidden Gems Archetypes...", flush=True)
    archetype_queries = ["deckbuilder", "co-op survival", "cyberpunk rpg", "space exploration", "relaxing farming"]
    archetype_traces = {}
    for aq in archetype_queries:
        t20 = trace_pipeline_stages(aq, "HIDDEN_GEMS", DiscoveryCandidatePool.POPULAR_20K, service, cm, embedder, index_mgr)
        trev = trace_pipeline_stages(aq, "HIDDEN_GEMS", DiscoveryCandidatePool.REVIEWED_ONLY, service, cm, embedder, index_mgr)
        
        archetype_traces[aq] = {
            "query": aq,
            "20k": t20,
            "reviewed_only": trev,
            "overlap": {
                "dense": compute_stage_overlap(t20["dense_top50"], trev["dense_top50"], twenty_k_ids),
                "lexical": compute_stage_overlap(t20["lexical_top50"], trev["lexical_top50"], twenty_k_ids),
                "rrf": compute_stage_overlap(t20["rrf_candidates"], trev["rrf_candidates"], twenty_k_ids),
                "post_filter": compute_stage_overlap(t20["post_filter_candidates"], trev["post_filter_candidates"], twenty_k_ids),
                "top20": compute_stage_overlap(t20["post_ranking_top20"], trev["post_ranking_top20"], twenty_k_ids),
                "top5": compute_stage_overlap(t20["final_top5"], trev["final_top5"], twenty_k_ids),
            }
        }

    # Save complete artifact
    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "standard_30_benchmark": {
            "aggregate": std_agg_hg,
            "long_tail_metrics": lt_metrics_std,
            "query_diagnostics": std_diag_hg,
        },
        "long_tail_25_benchmark": {
            "aggregate": lt_agg_hg,
            "long_tail_metrics": lt_metrics_niche,
            "query_diagnostics": lt_diag_hg,
        },
        "archetype_traces": archetype_traces,
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nAll candidate overlap diagnostics saved to {RESULTS_PATH}", flush=True)

    # Print Formatted Summary Tables
    print("\n" + "=" * 95, flush=True)
    print("SECTION B: AGGREGATE CANDIDATE OVERLAP & REACH RATES", flush=True)
    print("=" * 95, flush=True)
    print(f"{'Pipeline Stage':<30} | {'Standard 30 Queries Reach %':<30} | {'Long-Tail 25 Queries Reach %':<30}", flush=True)
    print("-" * 95, flush=True)
    print(f"{'Dense FAISS Top-50':<30} | {std_agg_hg['dense_new_candidate_rate']:<28.1f}% | {lt_agg_hg['dense_new_candidate_rate']:<28.1f}%", flush=True)
    print(f"{'Lexical Top-50':<30} | {std_agg_hg['lexical_new_candidate_rate']:<28.1f}% | {lt_agg_hg['lexical_new_candidate_rate']:<28.1f}%", flush=True)
    print(f"{'RRF Fused Candidates':<30} | {std_agg_hg['rrf_new_candidate_reach_rate']:<28.1f}% | {lt_agg_hg['rrf_new_candidate_reach_rate']:<28.1f}%", flush=True)
    print(f"{'Post-Filter Candidates':<30} | {std_agg_hg['post_filter_reach_rate']:<28.1f}% | {lt_agg_hg['post_filter_reach_rate']:<28.1f}%", flush=True)
    print(f"{'Post-Ranking Top-20':<30} | {std_agg_hg['top20_reach_rate']:<28.1f}% | {lt_agg_hg['top20_reach_rate']:<28.1f}%", flush=True)
    print(f"{'Final Top-5 Recommendations':<30} | {std_agg_hg['top5_reach_rate']:<28.1f}% | {lt_agg_hg['top5_reach_rate']:<28.1f}%", flush=True)

    print("\n" + "=" * 95, flush=True)
    print("SECTION C: BOTTLENECK CLASSIFICATION DISTRIBUTION", flush=True)
    print("=" * 95, flush=True)
    print("Standard 30 Benchmark Cases:", std_agg_hg["case_distribution"], flush=True)
    print("Long-Tail 25 Benchmark Cases:", lt_agg_hg["case_distribution"], flush=True)

    print("\n" + "=" * 95, flush=True)
    print("STANDARD 30-QUERY BENCHMARK DIAGNOSTIC TABLE", flush=True)
    print("=" * 95, flush=True)
    print(f"{'ID':<5} | {'Query':<30} | {'New Dense':<10} | {'New Lex':<8} | {'New RRF':<8} | {'New Top20':<10} | {'New Top5':<9} | {'Bottleneck'}", flush=True)
    print("-" * 95, flush=True)
    for q in std_diag_hg:
        ov = q["stage_overlap"]
        print(f"{q['id']:<5} | {q['query'][:28]:<30} | {ov['dense']['new_candidates_count']:<10} | {ov['lexical']['new_candidates_count']:<8} | {ov['rrf']['new_candidates_count']:<8} | {ov['top20']['new_candidates_count']:<10} | {ov['top5']['new_candidates_count']:<9} | {q['bottleneck_case']}", flush=True)

    print("\n" + "=" * 95, flush=True)
    print("LONG-TAIL 25-QUERY BENCHMARK DIAGNOSTIC TABLE", flush=True)
    print("=" * 95, flush=True)
    print(f"{'ID':<5} | {'Query':<30} | {'New Dense':<10} | {'New Lex':<8} | {'New RRF':<8} | {'New Top20':<10} | {'New Top5':<9} | {'Bottleneck'}", flush=True)
    print("-" * 95, flush=True)
    for q in lt_diag_hg:
        ov = q["stage_overlap"]
        print(f"{q['id']:<5} | {q['query'][:28]:<30} | {ov['dense']['new_candidates_count']:<10} | {ov['lexical']['new_candidates_count']:<8} | {ov['rrf']['new_candidates_count']:<8} | {ov['top20']['new_candidates_count']:<10} | {ov['top5']['new_candidates_count']:<9} | {q['bottleneck_case']}", flush=True)

    print("\n" + "=" * 95, flush=True)
    print("SECTION E: LONG-TAIL EXPOSURE & REVIEW DISTRIBUTION", flush=True)
    print("=" * 95, flush=True)
    print(f"{'Metric':<35} | {'20k Universe':<20} | {'Reviewed-Only Universe (87.9k)':<30}", flush=True)
    print("-" * 95, flush=True)
    print(f"{'Long-Tail Exposure@5 (<=5k revs)':<35} | {lt_metrics_niche['exposure_at_5_20k']:<18.1f}% | {lt_metrics_niche['exposure_at_5_reviewed_only']:<28.1f}%", flush=True)
    print(f"{'Zero-Review Games in Top-5':<35} | {lt_metrics_niche['zero_review_count_20k']:<20} | {lt_metrics_niche['zero_review_count_reviewed_only']:<30}", flush=True)
    print(f"{'Median Reviews':<35} | {lt_metrics_niche['reviews_20k']['median']:<20} | {lt_metrics_niche['reviews_reviewed_only']['median']:<30}", flush=True)
    print(f"{'Mean Reviews':<35} | {lt_metrics_niche['reviews_20k']['mean']:<20.1f} | {lt_metrics_niche['reviews_reviewed_only']['mean']:<30.1f}", flush=True)
    print(f"{'Min..Max Reviews':<35} | {lt_metrics_niche['reviews_20k']['min']}..{lt_metrics_niche['reviews_20k']['max']:<16} | {lt_metrics_niche['reviews_reviewed_only']['min']}..{lt_metrics_niche['reviews_reviewed_only']['max']}", flush=True)
    print("=" * 95, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
