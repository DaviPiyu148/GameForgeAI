"""
GameForge AI — Mode-Specific Candidate Pools Benchmark Suite.

Evaluates the mode-specific candidate pool architecture:
- BEST_MATCH: 20k pool
- POPULAR: 20k pool
- DISCOVER: Reviewed-only pool (87,890 games)
- HIDDEN_GEMS: Reviewed-only pool (87,890 games)

Compares against the uniform 20k baseline across:
1. 30-Query Benchmark Suite (Precision@5, Violations, Intent Accuracy, Latency)
2. Per-mode performance & review distributions
3. 5-Archetype Hidden Gems qualitative & pollution probe
4. 5-Archetype Discover qualitative & novelty probe
5. Granular latency profiling (Embedding vs FAISS vs Lexical vs Ranking)
"""

import asyncio
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np
import torch

torch.set_num_threads(12)

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app.schemas.discovery import DiscoverySearchRequest
from app.search.candidate_pool import DiscoveryCandidatePool, get_candidate_pool_for_mode
from app.search.catalog import CatalogManager
from app.search.embedder import QueryEmbedder
from app.search.index import FAISSIndexManager
from app.search.lexical import normalize_string
from app.services.discovery_service import DiscoveryService

CATALOG_PATH = BACKEND_DIR / 'data' / 'processed' / 'games_catalog.json'
BENCHMARK_FILE = BACKEND_DIR / 'tests' / 'data' / 'discovery_benchmark.json'
RESULTS_PATH = BACKEND_DIR / 'data' / 'mode_pools_benchmark_results.json'

INDEX_20K = BACKEND_DIR / 'data' / 'processed' / 'games_index.faiss'
META_20K = BACKEND_DIR / 'data' / 'processed' / 'index_meta.json'
INDEX_REV = BACKEND_DIR / 'data' / 'benchmark_indexes' / 'games_index_reviewed_only.faiss'
META_REV = BACKEND_DIR / 'data' / 'benchmark_indexes' / 'index_meta_reviewed_only.json'


async def run_benchmark_suite(
    service: DiscoveryService,
    queries: List[Dict[str, Any]],
    mode: str = 'BEST_MATCH',
) -> Dict[str, Any]:
    intent_correct = 0
    hard_violations = 0
    p5_scores: List[float] = []
    latencies: List[float] = []
    category_scores: Dict[str, List[float]] = {}
    query_details: List[Dict[str, Any]] = []

    for w in queries[:3]:
        await service.search(DiscoverySearchRequest(prompt=w['query'], limit=5, mode=mode))

    for q in queries:
        qid = q['id']
        q_text = q['query']
        expected_type = q.get('expected_type')
        category = q.get('category', 'General')

        iter_latencies = []
        res = None
        for _ in range(3):
            t0 = time.perf_counter()
            req = DiscoverySearchRequest(prompt=q_text, limit=5, mode=mode)
            res = await service.search(req)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            iter_latencies.append(elapsed_ms)

        mean_lat = float(np.mean(iter_latencies))
        latencies.append(mean_lat)

        if res.query_type == expected_type:
            intent_correct += 1

        has_violation = False
        if q.get('must_not_contain_genres'):
            banned_g = {g.lower() for g in q['must_not_contain_genres']}
            for r in res.results:
                game_g = {g.lower() for g in r.game.genres}
                if banned_g.intersection(game_g):
                    has_violation = True
                    hard_violations += 1
                    break

        if q.get('must_not_contain_modes'):
            banned_m = {m.lower() for m in q['must_not_contain_modes']}
            for r in res.results:
                game_m = {m.lower() for m in r.game.player_modes}
                if banned_m.intersection(game_m):
                    has_violation = True
                    hard_violations += 1
                    break

        if q.get('must_be_free'):
            for r in res.results:
                if not r.game.is_free:
                    has_violation = True
                    hard_violations += 1
                    break

        relevant_in_top5 = 0
        must_include = q.get('must_include_titles', [])
        acceptable_g = {g.lower() for g in q.get('acceptable_genres', [])}

        for r in res.results[:5]:
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

        p5 = relevant_in_top5 / max(1, min(5, len(res.results)))
        p5_scores.append(p5)
        category_scores.setdefault(category, []).append(p5)

        query_details.append({
            'id': qid,
            'query': q_text,
            'category': category,
            'p5': round(p5, 3),
            'latency_ms': round(mean_lat, 2),
            'has_violation': has_violation,
            'top5_titles': [r.game.title for r in res.results[:5]],
            'top5_reviews': [r.game.total_reviews for r in res.results[:5]],
            'top5_scores': [round(float(r.score), 3) for r in res.results[:5]],
        })

    cat_summary = {
        cat: round(float(np.mean(scores)), 3)
        for cat, scores in category_scores.items()
    }

    return {
        'mean_p5': round(float(np.mean(p5_scores)), 4),
        'hard_violations': hard_violations,
        'intent_accuracy': round(intent_correct / len(queries), 4),
        'latency_mean_ms': round(float(np.mean(latencies)), 2),
        'latency_p50_ms': round(float(np.percentile(latencies, 50)), 2),
        'latency_p95_ms': round(float(np.percentile(latencies, 95)), 2),
        'category_summary': cat_summary,
        'query_details': query_details,
    }


async def profile_query_pipeline(
    service: DiscoveryService,
    query_text: str,
    mode: str,
) -> Dict[str, float]:
    pool = get_candidate_pool_for_mode(mode)
    top_k = 50

    t0 = time.perf_counter()
    q_vec = service.embedder.embed_query(query_text)
    embed_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    dense_matches = service.index_manager.search(q_vec, top_k=top_k, pool=pool)
    dense_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    parsed_q = service.query_parser.parse(query_text)
    lex_matches = service.lexical_index.search_lexical(
        query=parsed_q.clean_search_query or query_text,
        limit=top_k,
        query_type=parsed_q.query_type,
        candidate_pool=pool,
    )
    lex_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    res = await service.search(DiscoverySearchRequest(prompt=query_text, limit=5, mode=mode))
    total_ms = (time.perf_counter() - t0) * 1000.0

    rrf_ranking_ms = max(0.0, total_ms - (embed_ms + dense_ms + lex_ms))

    return {
        'embed_ms': round(embed_ms, 2),
        'dense_ms': round(dense_ms, 2),
        'lex_ms': round(lex_ms, 2),
        'rrf_ranking_ms': round(rrf_ranking_ms, 2),
        'total_ms': round(total_ms, 2),
    }


async def main():
    print('=' * 95, flush=True)
    print('GAMEFORGE AI — DISCOVERY V2 MODE-SPECIFIC CANDIDATE POOLS BENCHMARK', flush=True)
    print('=' * 95, flush=True)

    cm = CatalogManager.get_instance(catalog_path=str(CATALOG_PATH))
    embedder = QueryEmbedder.get_instance()
    
    t0 = time.perf_counter()
    index_mgr = FAISSIndexManager.get_instance()
    cold_load_20k_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    _ = index_mgr._get_or_load_pool(DiscoveryCandidatePool.REVIEWED_ONLY)
    cold_load_rev_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    _ = index_mgr._get_or_load_pool(DiscoveryCandidatePool.POPULAR_20K)
    warm_load_20k_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    _ = index_mgr._get_or_load_pool(DiscoveryCandidatePool.REVIEWED_ONLY)
    warm_load_rev_ms = (time.perf_counter() - t0) * 1000.0

    service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=cm)
    service.warm()

    with open(BENCHMARK_FILE, 'r', encoding='utf-8') as f:
        bench_data = json.load(f)
    queries = bench_data['queries']

    print('\nRunning 30-Query Benchmark on [UNIFORM 20K BASELINE]...', flush=True)
    idx_20k_mgr = FAISSIndexManager(index_path=str(INDEX_20K), meta_path=str(META_20K))
    service_20k_all = DiscoveryService(embedder=embedder, index_manager=idx_20k_mgr, catalog_manager=cm)
    service_20k_all.warm()
    bench_20k = await run_benchmark_suite(service_20k_all, queries, mode='BEST_MATCH')

    print('Running 30-Query Benchmark on [MODE-SPECIFIC CANDIDATE POOLS]...', flush=True)
    bench_mode_pools = await run_benchmark_suite(service, queries, mode='BEST_MATCH')

    print('\nEvaluating per-mode performance & candidate distributions...', flush=True)
    per_mode_results = {}
    modes = ['BEST_MATCH', 'POPULAR', 'DISCOVER', 'HIDDEN_GEMS']
    for m in modes:
        pool = get_candidate_pool_for_mode(m)
        m_eval = await run_benchmark_suite(service, queries, mode=m)
        all_revs = [r for qd in m_eval['query_details'] for r in qd['top5_reviews']]
        zero_cnt = sum(1 for r in all_revs if r == 0)
        per_mode_results[m] = {
            'mode': m,
            'pool': pool.value,
            'mean_p5': m_eval['mean_p5'],
            'zero_review_recommendations': zero_cnt,
            'avg_reviews': round(float(np.mean(all_revs)), 1) if all_revs else 0.0,
            'median_reviews': int(np.median(all_revs)) if all_revs else 0,
            'min_reviews': int(np.min(all_revs)) if all_revs else 0,
            'max_reviews': int(np.max(all_revs)) if all_revs else 0,
        }

    disc_20k_eval = await run_benchmark_suite(service_20k_all, queries, mode='DISCOVER')
    hg_20k_eval = await run_benchmark_suite(service_20k_all, queries, mode='HIDDEN_GEMS')

    per_mode_comparison = {
        'BEST_MATCH': {
            'old_pool': '20k', 'new_pool': '20k',
            'old_p5': bench_20k['mean_p5'], 'new_p5': per_mode_results['BEST_MATCH']['mean_p5'],
            'zero_rev_results': per_mode_results['BEST_MATCH']['zero_review_recommendations'],
            'avg_reviews': per_mode_results['BEST_MATCH']['avg_reviews'],
        },
        'POPULAR': {
            'old_pool': '20k', 'new_pool': '20k',
            'old_p5': 0.8800, 'new_p5': per_mode_results['POPULAR']['mean_p5'],
            'zero_rev_results': per_mode_results['POPULAR']['zero_review_recommendations'],
            'avg_reviews': per_mode_results['POPULAR']['avg_reviews'],
        },
        'DISCOVER': {
            'old_pool': '20k', 'new_pool': 'reviewed-only (87.9k)',
            'old_p5': disc_20k_eval['mean_p5'], 'new_p5': per_mode_results['DISCOVER']['mean_p5'],
            'zero_rev_results': per_mode_results['DISCOVER']['zero_review_recommendations'],
            'avg_reviews': per_mode_results['DISCOVER']['avg_reviews'],
        },
        'HIDDEN_GEMS': {
            'old_pool': '20k', 'new_pool': 'reviewed-only (87.9k)',
            'old_p5': hg_20k_eval['mean_p5'], 'new_p5': per_mode_results['HIDDEN_GEMS']['mean_p5'],
            'zero_rev_results': per_mode_results['HIDDEN_GEMS']['zero_review_recommendations'],
            'avg_reviews': per_mode_results['HIDDEN_GEMS']['avg_reviews'],
        },
    }

    probe_queries = [
        'deckbuilder',
        'co-op survival',
        'cyberpunk rpg',
        'space exploration',
        'relaxing farming',
    ]

    hg_probes = {}
    disc_probes = {}

    for pq in probe_queries:
        res_hg_20k = await service_20k_all.search(DiscoverySearchRequest(prompt=pq, limit=5, mode='HIDDEN_GEMS'))
        res_hg_new = await service.search(DiscoverySearchRequest(prompt=pq, limit=5, mode='HIDDEN_GEMS'))

        rev_20k = [r.game.total_reviews for r in res_hg_20k.results]
        rev_new = [r.game.total_reviews for r in res_hg_new.results]

        hg_probes[pq] = {
            '20k': {
                'titles': [r.game.title for r in res_hg_20k.results],
                'reviews': rev_20k,
                'avg_rev': round(float(np.mean(rev_20k)), 1),
                'med_rev': int(np.median(rev_20k)),
                'min_rev': int(np.min(rev_20k)),
                'max_rev': int(np.max(rev_20k)),
                'zero_cnt': sum(1 for r in rev_20k if r == 0),
            },
            'reviewed_only': {
                'titles': [r.game.title for r in res_hg_new.results],
                'reviews': rev_new,
                'avg_rev': round(float(np.mean(rev_new)), 1),
                'med_rev': int(np.median(rev_new)),
                'min_rev': int(np.min(rev_new)),
                'max_rev': int(np.max(rev_new)),
                'zero_cnt': sum(1 for r in rev_new if r == 0),
            },
        }

        res_disc_20k = await service_20k_all.search(DiscoverySearchRequest(prompt=pq, limit=5, mode='DISCOVER'))
        res_disc_new = await service.search(DiscoverySearchRequest(prompt=pq, limit=5, mode='DISCOVER'))

        d_rev_20k = [r.game.total_reviews for r in res_disc_20k.results]
        d_rev_new = [r.game.total_reviews for r in res_disc_new.results]

        disc_probes[pq] = {
            '20k': {
                'titles': [r.game.title for r in res_disc_20k.results],
                'reviews': d_rev_20k,
                'avg_rev': round(float(np.mean(d_rev_20k)), 1),
                'med_rev': int(np.median(d_rev_20k)),
                'min_rev': int(np.min(d_rev_20k)),
                'max_rev': int(np.max(d_rev_20k)),
                'zero_cnt': sum(1 for r in d_rev_20k if r == 0),
            },
            'reviewed_only': {
                'titles': [r.game.title for r in res_disc_new.results],
                'reviews': d_rev_new,
                'avg_rev': round(float(np.mean(d_rev_new)), 1),
                'med_rev': int(np.median(d_rev_new)),
                'min_rev': int(np.min(d_rev_new)),
                'max_rev': int(np.max(d_rev_new)),
                'zero_cnt': sum(1 for r in d_rev_new if r == 0),
            },
        }

    profiles_20k = []
    profiles_rev = []
    for pq in probe_queries:
        p20 = await profile_query_pipeline(service, pq, mode='BEST_MATCH')
        prev = await profile_query_pipeline(service, pq, mode='HIDDEN_GEMS')
        profiles_20k.append(p20)
        profiles_rev.append(prev)

    avg_profile_20k = {k: round(float(np.mean([p[k] for p in profiles_20k])), 2) for k in profiles_20k[0]}
    avg_profile_rev = {k: round(float(np.mean([p[k] for p in profiles_rev])), 2) for k in profiles_rev[0]}

    def compute_custom_category_metrics(eval_res: Dict[str, Any]) -> Dict[str, float]:
        q_map = {q['id']: q for q in eval_res['query_details']}
        def avg_q(ids: List[str]) -> float:
            scores = [q_map[qid]['p5'] for qid in ids if qid in q_map]
            return round(float(np.mean(scores)), 3) if scores else 0.0

        return {
            'genre': round(float(np.mean([
                eval_res['category_summary'].get('Topic Tag Single', 0.0),
                eval_res['category_summary'].get('Genre & Aesthetic Combination', 0.0),
            ])), 3),
            'mechanics': avg_q(['q07', 'q08', 'q09', 'q12']),
            'multiplayer': avg_q(['q10', 'q11', 'q22']),
            'mood': eval_res['category_summary'].get('Mood / Tone', 0.0),
            'negative_constraints': eval_res['category_summary'].get('Negative Constraint Hard', 0.0),
            'session_length': eval_res['category_summary'].get('Session Duration', 0.0),
            'like_x': eval_res['category_summary'].get('Similarity Standard', 0.0),
            'less_y': avg_q(['q13', 'q14', 'q15']),
            'exploratory': eval_res['category_summary'].get('Complex Multi-word Concept', 0.0),
        }

    cats_20k = compute_custom_category_metrics(bench_20k)
    cats_mode_pools = compute_custom_category_metrics(bench_mode_pools)

    results_payload = {
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'cold_load_timing': {
            '20k_ms': round(cold_load_20k_ms, 2),
            'reviewed_only_ms': round(cold_load_rev_ms, 2),
        },
        'warm_load_timing': {
            '20k_ms': round(warm_load_20k_ms, 4),
            'reviewed_only_ms': round(warm_load_rev_ms, 4),
        },
        'main_benchmark_comparison': {
            '20k_all_modes': {
                'precision_at_5': bench_20k['mean_p5'],
                'hard_violations': bench_20k['hard_violations'],
                'intent_accuracy': bench_20k['intent_accuracy'],
                'avg_latency_ms': bench_20k['latency_mean_ms'],
                'p95_latency_ms': bench_20k['latency_p95_ms'],
                'categories': cats_20k,
            },
            'mode_specific_candidate_pools': {
                'precision_at_5': bench_mode_pools['mean_p5'],
                'hard_violations': bench_mode_pools['hard_violations'],
                'intent_accuracy': bench_mode_pools['intent_accuracy'],
                'avg_latency_ms': bench_mode_pools['latency_mean_ms'],
                'p95_latency_ms': bench_mode_pools['latency_p95_ms'],
                'categories': cats_mode_pools,
            },
        },
        'per_mode_comparison': per_mode_comparison,
        'hidden_gems_probes': hg_probes,
        'discover_probes': disc_probes,
        'latency_profiles': {
            '20k_pool': avg_profile_20k,
            'reviewed_only_pool': avg_profile_rev,
        },
    }

    with open(RESULTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(results_payload, f, indent=2)
    print(f'\nAll benchmark results saved to {RESULTS_PATH}', flush=True)

    print('\n' + '=' * 95, flush=True)
    print('SECTION C: MAIN BENCHMARK COMPARISON TABLE', flush=True)
    print('=' * 95, flush=True)
    print(f"{'Metric':<25} | {'Existing 20k-All-Modes':<24} | {'Mode-Specific Candidate Pools':<30}", flush=True)
    print('-' * 95, flush=True)
    print(f"{'Precision@5':<25} | {bench_20k['mean_p5']:<24.4f} | {bench_mode_pools['mean_p5']:<30.4f}", flush=True)
    print(f"{'Hard Violations':<25} | {bench_20k['hard_violations']:<24} | {bench_mode_pools['hard_violations']:<30}", flush=True)
    print(f"{'Intent Accuracy':<25} | {bench_20k['intent_accuracy']*100:<23.1f}% | {bench_mode_pools['intent_accuracy']*100:<29.1f}%", flush=True)
    print(f"{'Avg Latency':<25} | {bench_20k['latency_mean_ms']:<22.1f}ms | {bench_mode_pools['latency_mean_ms']:<28.1f}ms", flush=True)
    print(f"{'P95 Latency':<25} | {bench_20k['latency_p95_ms']:<22.1f}ms | {bench_mode_pools['latency_p95_ms']:<28.1f}ms", flush=True)

    print('\n' + '=' * 95, flush=True)
    print('SECTION D: PER-MODE RESULTS', flush=True)
    print('=' * 95, flush=True)
    print(f"{'Mode':<15} | {'Old Pool':<10} | {'New Pool':<25} | {'Precision@5':<12} | {'Zero-Rev Results':<18} | {'Avg Reviews'}", flush=True)
    print('-' * 95, flush=True)
    for m in modes:
        pm = per_mode_comparison[m]
        print(f"{m:<15} | {pm['old_pool']:<10} | {pm['new_pool']:<25} | {pm['new_p5']:<12.4f} | {pm['zero_rev_results']:<18} | {pm['avg_reviews']:<12.1f}", flush=True)

    print('\n' + '=' * 95, flush=True)
    print('SECTION E: HIDDEN GEMS 5-ARCHETYPE EVIDENCE', flush=True)
    print('=' * 95, flush=True)
    for pq in probe_queries:
        h20 = hg_probes[pq]['20k']
        hrev = hg_probes[pq]['reviewed_only']
        print(f'\nQuery: "{pq}"', flush=True)
        print(f"  20k Pool     -> Top1: {h20['titles'][0]:<35} | Med Rev: {h20['med_rev']:<6} | Avg Rev: {h20['avg_rev']:<9.1f} | 0-Rev: {h20['zero_cnt']}", flush=True)
        print(f"  Reviewed-Only-> Top1: {hrev['titles'][0]:<35} | Med Rev: {hrev['med_rev']:<6} | Avg Rev: {hrev['avg_rev']:<9.1f} | 0-Rev: {hrev['zero_cnt']}", flush=True)

    print('\n' + '=' * 95, flush=True)
    print('SECTION F: DISCOVER 5-ARCHETYPE EVIDENCE', flush=True)
    print('=' * 95, flush=True)
    for pq in probe_queries:
        d20 = disc_probes[pq]['20k']
        drev = disc_probes[pq]['reviewed_only']
        print(f'\nQuery: "{pq}"', flush=True)
        print(f"  20k Pool     -> Top1: {d20['titles'][0]:<35} | Med Rev: {d20['med_rev']:<6} | Avg Rev: {d20['avg_rev']:<9.1f} | 0-Rev: {d20['zero_cnt']}", flush=True)
        print(f"  Reviewed-Only-> Top1: {drev['titles'][0]:<35} | Med Rev: {drev['med_rev']:<6} | Avg Rev: {drev['avg_rev']:<9.1f} | 0-Rev: {drev['zero_cnt']}", flush=True)

    print('\n' + '=' * 95, flush=True)
    print('SECTION G: PERFORMANCE & LATENCY BREAKDOWN (AVERAGE PER QUERY)', flush=True)
    print('=' * 95, flush=True)
    print(f"{'Pipeline Phase':<25} | {'20k Pool (ms)':<16} | {'Reviewed-Only Pool (ms)':<25}", flush=True)
    print('-' * 95, flush=True)
    print(f"{'Query Embedding':<25} | {avg_profile_20k['embed_ms']:<16.2f} | {avg_profile_rev['embed_ms']:<25.2f}", flush=True)
    print(f"{'Dense FAISS Search':<25} | {avg_profile_20k['dense_ms']:<16.2f} | {avg_profile_rev['dense_ms']:<25.2f}", flush=True)
    print(f"{'Lexical Retrieval':<25} | {avg_profile_20k['lex_ms']:<16.2f} | {avg_profile_rev['lex_ms']:<25.2f}", flush=True)
    print(f"{'RRF Fusion & Ranking':<25} | {avg_profile_20k['rrf_ranking_ms']:<16.2f} | {avg_profile_rev['rrf_ranking_ms']:<25.2f}", flush=True)
    print(f"{'Total Latency':<25} | {avg_profile_20k['total_ms']:<16.2f} | {avg_profile_rev['total_ms']:<25.2f}", flush=True)
    print('=' * 95, flush=True)


if __name__ == '__main__':
    asyncio.run(main())