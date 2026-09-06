import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.schemas.discovery import DiscoverySearchRequest
from app.services.discovery_service import discovery_service


async def test_d2_queries():
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

    print("=" * 75)
    print("DISCOVERY ENGINE 2.0 — QUERY RESULTS AUDIT")
    print("=" * 75)

    for query_str in queries:
        req = DiscoverySearchRequest(prompt=query_str, limit=5)
        res = await discovery_service.search(req)

        print(f"\nQUERY: '{query_str}' -> Parsed: {res.query_type} (Target: {res.target_entity}) | Matches: {res.match_count}")
        for rank, match in enumerate(res.results[:5], 1):
            rev_cnt = f"{match.game.total_reviews//1000}k" if match.game.total_reviews and match.game.total_reviews >= 1000 else f"{match.game.total_reviews}"
            print(f"  #{rank} [{match.score:.2f} | {int(match.score*100)}%] '{match.game.title}' (ID: {match.game.id}, Reviews: {rev_cnt}, Tags: {match.game.tags[:2]})")
            print(f"      Highlights: [{', '.join(match.match_highlights)}]")
            print(f"      Explanation: {match.explanation}")

if __name__ == "__main__":
    asyncio.run(test_d2_queries())
