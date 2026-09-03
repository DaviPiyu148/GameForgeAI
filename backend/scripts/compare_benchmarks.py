import sys
sys.stdout.reconfigure(encoding='utf-8')
import json

with open("backend/data/discover_rrf_damping_experiment_results.json", "r", encoding="utf-8") as f:
    d_rrf = json.load(f)
with open("backend/data/discover_review_floor_experiment_results.json", "r", encoding="utf-8") as f:
    d_flr = json.load(f)

traces_rrf = d_rrf["standard_30_benchmark"]["condition_b"]["per_query_traces"]
runs_flr = d_flr["standard_30_benchmark"]["condition_a"]["per_query_runs"]

print("RRF condition_b precision_at_5:", d_rrf["standard_30_benchmark"]["condition_b"]["precision_at_5"])
print("FLR condition_a precision_at_5:", d_flr["standard_30_benchmark"]["condition_a"]["metrics"]["precision_at_5"])

diff_count = 0
for i, (tr, rf) in enumerate(zip(traces_rrf, runs_flr)):
    t5_rrf = tr["top5_deconstructed"]
    t5_flr = rf["top5_deconstructed"]

    p_rrf = tr["precision"]
    # compute precision in flr exactly as compute_suite_metrics does:
    rel_flr = sum(1 for c in t5_flr if c["calibrated_score"] >= 0.70) / 5.0

    if abs(p_rrf - rel_flr) > 1e-4:
        diff_count += 1
        q = tr["query"]
        print(f"\nQ{i+1}: '{q}'")
        print(f"  RRF: p5={p_rrf}, scores={[c['calibrated_score'] for c in t5_rrf]}, titles={[c['title'] for c in t5_rrf]}")
        print(f"  FLR: p5={rel_flr}, scores={[c['calibrated_score'] for c in t5_flr]}, titles={[c['title'] for c in t5_flr]}")

print(f"\nTotal differing queries: {diff_count} / 30")
