import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

with open(BACKEND_DIR / "data" / "discover_review_floor_experiment_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

runs_a = d["exploratory_25_benchmark"]["condition_a"]["per_query_runs"]
runs_c = d["exploratory_25_benchmark"]["condition_c"]["per_query_runs"]

print("=== EXPLORATORY 25 TOP-5 CANDIDATE SHIFTS (NO FLOOR vs 80% FLOOR) ===")
total_slots_changed = 0
for i, (ra, rc) in enumerate(zip(runs_a, runs_c)):
    t5_a = ra["top5_deconstructed"]
    t5_c = rc["top5_deconstructed"]
    titles_a = [x["title"] for x in t5_a]
    titles_c = [x["title"] for x in t5_c]

    diff_in_a = [x for x in t5_a if x["title"] not in titles_c]
    diff_in_c = [x for x in t5_c if x["title"] not in titles_a]

    if diff_in_a:
        q = ra["query"]
        total_slots_changed += len(diff_in_a)
        print(f"\nQuery {i+1}: '{q}'")
        for x in diff_in_a:
            print(f"  [-] REMOVED:  '{x['title']}' | {x['reviews']} revs | {x['positive_percent']}% pos | score={x['calibrated_score']}")
        for x in diff_in_c:
            print(f"  [+] REPLACED: '{x['title']}' | {x['reviews']} revs | {x['positive_percent']}% pos | score={x['calibrated_score']}")

print(f"\nTotal Top-5 slots altered across 25 queries: {total_slots_changed} / 125")
