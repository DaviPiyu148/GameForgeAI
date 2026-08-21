import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.schemas.discovery import DiscoverySearchRequest
from app.services.discovery_service import DiscoveryService


async def evaluate():
    print("=" * 70)
    print("Evaluating GameForge AI Discovery Engine on Evaluation Fixture...")
    print("=" * 70)

    with open("tests/fixtures/discovery_queries.json", "r", encoding="utf-8") as f:
        fixture_queries: List[Dict[str, Any]] = json.load(f)

    service = DiscoveryService()

    total_latency = 0.0
    evaluation_results = []

    for i, q in enumerate(fixture_queries, 1):
        prompt = q["prompt"]
        req = DiscoverySearchRequest(prompt=prompt, limit=5)

        t0 = time.perf_counter()
        resp = await service.search(req)
        dt = (time.perf_counter() - t0) * 1000  # ms
        total_latency += dt

        top_titles = [f"{r.game.title} (score: {r.score:.3f}, tags: {', '.join(r.game.tags[:3])})" for r in resp.results[:3]]

        res_summary = {
            "query_id": q["id"],
            "prompt": prompt,
            "latency_ms": round(dt, 2),
            "match_count": resp.match_count,
            "no_strong_match": resp.no_strong_match,
            "top_matches": top_titles,
        }
        evaluation_results.append(res_summary)

        print(f"\n[{i}/{len(fixture_queries)}] Query: '{prompt}' ({dt:.2f} ms)")
        print(f"    Matches: {resp.match_count} | No Match: {resp.no_strong_match}")
        for rank, match in enumerate(resp.results[:3], 1):
            print(f"    #{rank} {match.game.title} (Score: {match.score:.3f})")
            print(f"       Highlights: {', '.join(match.match_highlights)}")
            print(f"       Explanation: {match.explanation}")

    avg_latency = total_latency / len(fixture_queries)
    print("\n" + "=" * 70)
    print(f"Evaluation Complete! Average Search Latency: {avg_latency:.2f} ms")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(evaluate())
