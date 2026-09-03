import sys
sys.stdout.reconfigure(encoding='utf-8')
import json

with open("backend/data/discover_review_floor_experiment_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

runs_a = d["standard_30_benchmark"]["condition_a"]["per_query_runs"]
runs_c = d["standard_30_benchmark"]["condition_c"]["per_query_runs"]

print("=== QUERIES THAT CHANGED BETWEEN CONDITION A (NO FLOOR) AND CONDITION C (80% FLOOR) ===")
changed_count = 0
for i, (ra, rc) in enumerate(zip(runs_a, runs_c)):
    t5_a = ra["top5_deconstructed"]
    t5_c = rc["top5_deconstructed"]
    titles_a = [x["title"] for x in t5_a]
    titles_c = [x["title"] for x in t5_c]
    scores_a = [x["calibrated_score"] for x in t5_a]
    scores_c = [x["calibrated_score"] for x in t5_c]

    rel_a = sum(1 for s in scores_a if s >= 0.70)
    rel_c = sum(1 for s in scores_c if s >= 0.70)

    if titles_a != titles_c or rel_a != rel_c:
        changed_count += 1
        q = ra["query"]
        print(f"\nQuery {i+1}: '{q}'")
        print(f"  Cond A: rel={rel_a}/5, titles={titles_a}")
        print(f"  Cond C: rel={rel_c}/5, titles={titles_c}")
        diff_in_a = [x for x in t5_a if x["title"] not in titles_c]
        diff_in_c = [x for x in t5_c if x["title"] not in titles_a]
        removed_strs = [f"{x['title']} ({x['reviews']} revs, {x['positive_percent']}% pos, score={x['calibrated_score']})" for x in diff_in_a]
        promoted_strs = [f"{x['title']} ({x['reviews']} revs, {x['positive_percent']}% pos, score={x['calibrated_score']})" for x in diff_in_c]
        print(f"  Removed from Top-5: {removed_strs}")
        print(f"  Promoted to Top-5:  {promoted_strs}")

print(f"\nTotal queries with changed Top-5: {changed_count} / 30")
