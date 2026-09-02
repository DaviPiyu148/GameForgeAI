import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app.search.candidate_pool import DiscoveryCandidatePool
from app.search.catalog import CatalogManager
from app.search.embedder import QueryEmbedder
from app.search.index import FAISSIndexManager
from app.services.discovery_service import DiscoveryService
from scripts.audit_candidate_overlap import LONG_TAIL_QUERIES
from scripts.sweep_fine_quality_thresholds import rank_with_threshold


def main():
    CATALOG_PATH = BACKEND_DIR / "data" / "processed" / "games_catalog.json"
    BENCHMARK_FILE = BACKEND_DIR / "tests" / "data" / "discovery_benchmark.json"

    cm = CatalogManager.get_instance(catalog_path=str(CATALOG_PATH))
    embedder = QueryEmbedder.get_instance()
    index_mgr = FAISSIndexManager.get_instance()
    service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=cm)

    with open(BENCHMARK_FILE, "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    queries = LONG_TAIL_QUERIES

    pool = DiscoveryCandidatePool.REVIEWED_ONLY
    top_k = 50

    for th in [250.0, 150.0, 125.0, 100.0]:
        print(f"\n{'='*80}\nLOW-REVIEW (<100) GAMES IN TOP-5 FOR THRESHOLD T{int(th)}\n{'='*80}")
        seen_games = {}
        for q in queries:
            parsed_query = service.query_parser.parse(q["query"])
            embed_text = parsed_query.clean_search_query or q["query"]
            q_vec = embedder.embed_query(embed_text)

            raw_dense = index_mgr.search(q_vec, top_k=top_k, pool=pool)
            candidate_pool = {}
            sem_ranks = {}
            sem_scores = {}
            for rank, (gid, score) in enumerate(raw_dense, 1):
                g = cm.get_game(gid)
                if g:
                    candidate_pool[gid] = g
                    sem_ranks[gid] = rank
                    sem_scores[gid] = max(0.0, float(score))

            lex_candidates = service.lexical_index.search_lexical(
                query=parsed_query.clean_search_query or q["query"],
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
                mode="HIDDEN_GEMS",
                threshold=th,
                top_limit=5,
            )

            for r in ranked_top20:
                if r["reviews"] < 100:
                    title = r["game"].get("title", "")
                    seen_games[r["id"]] = {
                        "title": title,
                        "reviews": r["reviews"],
                        "pos_pct": r["game"].get("positive_percent", 0),
                        "score": r["score"],
                        "query": q["query"],
                        "rank": r["rank"],
                        "sem_rank": sem_ranks.get(r["id"], 200),
                        "lex_rank": lex_ranks.get(r["id"], 200),
                    }

        for gid, ginfo in sorted(seen_games.items(), key=lambda x: x[1]["reviews"]):
            print(f"  * #{ginfo['rank']} {ginfo['title']} ({ginfo['reviews']} revs, {ginfo['pos_pct']}% pos) -> Score: {ginfo['score']:.4f} [SemRank: #{ginfo['sem_rank']}, LexRank: #{ginfo['lex_rank']}] for query: '{ginfo['query']}'")


if __name__ == "__main__":
    main()
