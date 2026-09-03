import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

with open(BACKEND_DIR / "tests" / "data" / "discovery_benchmark.json", "r", encoding="utf-8") as f:
    std_bench = json.load(f)["queries"]

with open(BACKEND_DIR / "data" / "discover_review_floor_experiment_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

with open(BACKEND_DIR / "data" / "processed" / "games_catalog.json", "r", encoding="utf-8") as f:
    cat_list = json.load(f)
catalog_meta = {str(g["id"]): g for g in cat_list}

runs_a = d["standard_30_benchmark"]["condition_a"]["per_query_runs"]
runs_c = d["standard_30_benchmark"]["condition_c"]["per_query_runs"]

def normalize_string(s: str) -> str:
    import re
    return re.sub(r'[^a-z0-9]', '', s.lower())

def score_canonical(runs, queries):
    p5_scores = []
    for q, run in zip(queries, runs):
        must_include = q.get("must_include_titles", [])
        acceptable_g = {g.lower() for g in q.get("acceptable_genres", [])}
        rel_in_top5 = 0
        for cand in run["top5_deconstructed"]:
            title_norm = normalize_string(cand["title"])
            sc = cand["calibrated_score"]
            g_obj = catalog_meta.get(str(cand.get("id")), {})
            g_meta = {g.lower() for g in g_obj.get("genres", [])}

            if must_include:
                if any(normalize_string(mi) in title_norm for mi in must_include):
                    rel_in_top5 += 1
            elif acceptable_g:
                if acceptable_g.intersection(g_meta) or sc >= 0.70:
                    rel_in_top5 += 1
            else:
                if sc >= 0.65:
                    rel_in_top5 += 1
        p5 = rel_in_top5 / 5.0
        p5_scores.append(p5)
    return sum(p5_scores) / len(p5_scores)

def score_fixed_threshold(runs, threshold):
    rel_slots = sum(
        1 for r in runs for cand in r["top5_deconstructed"] if cand["calibrated_score"] >= threshold
    )
    return rel_slots / (len(runs) * 5.0)

print("=== PRECISION RECONCILIATION FOR STANDARD 30 BENCHMARK ===")
print("Condition A (No Floor):")
print(f"  Strict score >= 0.70:    {score_fixed_threshold(runs_a, 0.70):.4f}")
print(f"  Threshold score >= 0.65: {score_fixed_threshold(runs_a, 0.65):.4f}")
print(f"  Canonical Benchmark P@5: {score_canonical(runs_a, std_bench):.4f}")

print("\nCondition C (80% Floor):")
print(f"  Strict score >= 0.70:    {score_fixed_threshold(runs_c, 0.70):.4f}")
print(f"  Threshold score >= 0.65: {score_fixed_threshold(runs_c, 0.65):.4f}")
print(f"  Canonical Benchmark P@5: {score_canonical(runs_c, std_bench):.4f}")
