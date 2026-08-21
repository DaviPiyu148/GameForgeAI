import asyncio
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.discovery import DiscoverySearchRequest
from app.services.discovery_service import discovery_service

TEST_QUERIES = [
    # 1. English concepts targeting games with Russian/Chinese/Spanish descriptions/genres
    {"query": "cozy farming simulator", "type": "EN_CONCEPT", "target": "Stardew Valley"},
    {"query": "2D crafting sandbox survival", "type": "EN_CONCEPT", "target": "Terraria"},
    {"query": "hand drawn 2D metroidvania insect adventure", "type": "EN_CONCEPT", "target": "Hollow Knight"},
    {"query": "dark fantasy action RPG open world", "type": "EN_CONCEPT", "target": "ELDEN RING"},
    {"query": "alien ocean underwater survival", "type": "EN_CONCEPT", "target": "Subnautica"},
    {"query": "cozy simulator", "type": "EN_CONCEPT", "target": "Stardew Valley"},
    {"query": "farming game", "type": "EN_CONCEPT", "target": "Stardew Valley"},
    {"query": "tactical RPG", "type": "EN_CONCEPT", "target": "Cyberpunk 2077 / Witcher"},
    {"query": "relaxing game", "type": "EN_CONCEPT", "target": "Stardew Valley"},
    {"query": "city builder", "type": "EN_CONCEPT", "target": "Factorio / RimWorld"},
    
    # 2. Russian queries
    {"query": "уютный симулятор фермы", "type": "RU_QUERY", "target": "Stardew Valley"},
    {"query": "2D песочница крафтинг выживание", "type": "RU_QUERY", "target": "Terraria"},
    {"query": "ролевая игра открытый мир", "type": "RU_QUERY", "target": "Cyberpunk 2077 / Elden Ring"},
    {"query": "метроидвания жуки", "type": "RU_QUERY", "target": "Hollow Knight"},
    {"query": "кооперативный рогалик", "type": "RU_QUERY", "target": "Dead Cells / Risk of Rain"},
    
    # 3. Mixed language queries
    {"query": "cozy ферма game", "type": "MIXED_QUERY", "target": "Stardew Valley"},
    {"query": "2D выживание building", "type": "MIXED_QUERY", "target": "Terraria"},
    {"query": "open world экшен RPG", "type": "MIXED_QUERY", "target": "Cyberpunk 2077"},
    {"query": "space симулятор фабрика", "type": "MIXED_QUERY", "target": "Factorio"}
]

async def run_baseline_tests():
    service = discovery_service
    results = []
    
    print("=" * 80)
    print("RUNNING CROSS-LANGUAGE BASELINE RETRIEVAL TESTS (Discovery 2.0)")
    print("=" * 80)
    
    for item in TEST_QUERIES:
        q = item["query"]
        q_type = item["type"]
        expected_target = item["target"]
        
        req = DiscoverySearchRequest(prompt=q, limit=10)
        t0 = time.perf_counter()
        resp = await service.search(req)
        latency_ms = (time.perf_counter() - t0) * 1000
        
        top_games = []
        for rank, r in enumerate(resp.results[:5], 1):
            top_games.append({
                "rank": rank,
                "title": r.game.title,
                "score": round(r.score, 4),
                "highlights": r.match_highlights,
                "explanation": r.explanation,
                "genres": r.game.genres,
            })
            
        res_entry = {
            "query": q,
            "type": q_type,
            "expected_target": expected_target,
            "latency_ms": round(latency_ms, 2),
            "match_count": resp.match_count,
            "query_type": resp.query_type,
            "target_entity": resp.target_entity,
            "top_5": top_games
        }
        results.append(res_entry)
        
        top_titles_str = ", ".join([f"#{g['rank']} {g['title']} ({g['score']:.0%})" for g in top_games[:3]])
        print(f"\n[{q_type}] '{q}' ({latency_ms:.1f}ms) -> {top_titles_str}")
        
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "cross_language_baseline_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"\nBaseline results saved to {out_path}")

if __name__ == "__main__":
    asyncio.run(run_baseline_tests())
