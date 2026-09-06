import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.schemas.discovery import DiscoverySearchRequest
from app.services.discovery_service import DiscoveryService
from app.search.index import FAISSIndexManager
from app.search.embedder import QueryEmbedder
from app.search.catalog import CatalogManager

async def test_baseline_queries():
    queries = [
        "cyberpunk",
        "cyberpunk 2077",
        "cozy simulator",
        "cozy farming game",
        "games like Stardew Valley",
        "farming game",
        "soulslike",
        "space survival",
        "co-op roguelike",
    ]
    
    embedder = QueryEmbedder.get_instance()
    index_mgr = FAISSIndexManager.get_instance(
        index_path="backend/data/processed/games_index.faiss",
        meta_path="backend/data/processed/index_meta.json"
    )
    catalog_mgr = CatalogManager.get_instance(
        catalog_path="backend/data/processed/games_catalog.json"
    )
    service = DiscoveryService(embedder=embedder, index_manager=index_mgr, catalog_manager=catalog_mgr)
    
    print("=" * 70)
    print("CURRENT BASELINE SEARCH BEHAVIOR INVESTIGATION")
    print("=" * 70)
    
    for q in queries:
        req = DiscoverySearchRequest(prompt=q, limit=10)
        res = await service.search(req)
        
        # Also inspect raw FAISS retrieval
        q_vec = embedder.embed_query(q)
        raw_faiss = index_mgr.search(q_vec, top_k=20)
        
        print(f"\nQUERY: '{q}' (returned {res.match_count} results, no_strong_match={res.no_strong_match})")
        print("  Top 5 Ranked Results:")
        for idx, item in enumerate(res.results[:5], 1):
            print(f"    #{idx} [{item.score:.4f}] '{item.game.title}' (ID: {item.game.id}, Tags: {item.game.tags[:3]}, Highlights: {item.match_highlights})")
            
        # Check where Cyberpunk 2077 or Stardew Valley appear in raw FAISS
        for rank, (gid, score) in enumerate(raw_faiss, 1):
            game = catalog_mgr.get_game(gid)
            title = game.get("title", "") if game else ""
            if "cyberpunk 2077" in title.lower() or "stardew" in title.lower():
                print(f"  --> Landmark '{title}' is FAISS rank #{rank} with raw score {score:.4f}")

if __name__ == "__main__":
    asyncio.run(test_baseline_queries())
