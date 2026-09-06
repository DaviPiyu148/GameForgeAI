import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.schemas.discovery import DiscoverySearchRequest
from app.services.discovery_service import discovery_service


async def main():
    benchmark_path = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "discovery_benchmark_set.json")
    with open(benchmark_path, "r", encoding="utf-8") as f:
        benchmark_queries = json.load(f)

    print("Loaded queries. Testing queries 25 to 45...", flush=True)
    for i, q in enumerate(benchmark_queries[24:45], 25):
        prompt = q["prompt"]
        t0 = time.perf_counter()
        req = DiscoverySearchRequest(prompt=prompt, limit=12)
        resp = await discovery_service.search(req)
        dt = (time.perf_counter() - t0) * 1000
        print(f"[{i:02d}] '{prompt}' -> {resp.query_type} | {len(resp.results)} matches | {dt:.1f}ms", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
