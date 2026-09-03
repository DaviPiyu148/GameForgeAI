import json

with open("backend/data/discover_review_floor_experiment_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print("=== STANDARD 30 BENCHMARK ===")
for cid, data in d["standard_30_benchmark"].items():
    m = data["metrics"]
    print(f"\nCondition: {data['name']} (floor={data['floor']})")
    print(f"  Precision@5:       {m['precision_at_5']:.4f}")
    print(f"  Intent Accuracy:   {m['intent_accuracy']*100:.1f}%")
    print(f"  Hard Violations:   {m['hard_violations']}")
    print(f"  Avg Latency:       {m['avg_latency_ms']:.2f} ms")
    print(f"  P95 Latency:       {m['p95_latency_ms']:.2f} ms")
    print(f"  Lex Intrusion:     {m['single_channel_lexical_intrusion_rate']*100:.2f}%")
    print(f"  Zero-Review Count: {m['zero_review_count']}")

print("\n=== EXPLORATORY 25 BENCHMARK ===")
for cid, data in d["exploratory_25_benchmark"].items():
    m = data["metrics"]
    print(f"\nCondition: {data['name']} (floor={data['floor']})")
    print(f"  Precision@5:          {m['precision_at_5']:.4f}")
    print(f"  Hard Violations:      {m['hard_violations']}")
    print(f"  Useful Exp Share:     {m['useful_exploratory_share']*100:.2f}%")
    print(f"  Long-Tail Exposure@5: {m['long_tail_exposure_at_5']*100:.2f}%")
    print(f"  Top-5 Long-Tail Share:{m['top5_long_tail_share']*100:.2f}%")
    print(f"  Top-5 Reach:          {m['top5_reach']*100:.2f}%")
    print(f"  Avg Best LT Rank:     {m['avg_best_long_tail_rank']}")
    print(f"  Median Best LT Rank:  {m['median_best_long_tail_rank']}")
    print(f"  Zero-Review Count:    {m['zero_review_count']}")

print("\n=== REVIEW DISTRIBUTION & LOW-REVIEW METRICS (EXPLORATORY 25) ===")
for cid, data in d["exploratory_25_benchmark"].items():
    m = data["metrics"]
    rb = m["review_brackets"]
    fm = m["floor_metrics"]
    print(f"\nCondition: {data['name']} (floor={data['floor']})")
    print(f"  <50 reviews:         {rb['under_50']} ({rb['under_50_share']*100:.1f}%)")
    print(f"  50-99 reviews:       {rb['bracket_50_99']} ({rb['bracket_50_99_share']*100:.1f}%)")
    print(f"  <100 reviews total:  {rb['under_100_total']} ({rb['under_100_share']*100:.1f}%)")
    print(f"  100-249 reviews:     {rb['bracket_100_249']} ({rb['bracket_100_249_share']*100:.1f}%)")
    print(f"  250-499 reviews:     {rb['bracket_250_499']} ({rb['bracket_250_499_share']*100:.1f}%)")
    print(f"  500-999 reviews:     {rb['bracket_500_999']} ({rb['bracket_500_999_share']*100:.1f}%)")
    print(f"  1000+ reviews:       {rb['bracket_1000_plus']} ({rb['bracket_1000_plus_share']*100:.1f}%)")
    print(f"  Low-Rev Intrusion@5: {fm['low_review_intrusion_count']} ({fm['low_review_intrusion_at_5']*100:.1f}%)")
    print(f"  Legitimate Low-Rev:  {fm['legitimate_low_review_preserved_count']} ({fm['legitimate_low_review_share']*100:.1f}%)")

print("\n=== ALL 15 CANDIDATES REMOVED FROM TOP-5 AT 80% FLOOR ===")
rcs = d["false_positive_audit"]["removed_candidates_in_80_floor"]
for i, c in enumerate(rcs, 1):
    q = c["query"]
    t = c["title"]
    rev = c["reviews"]
    pos = c["positive_percent"]
    sc = c["score_in_a"]
    cls = c["classification"]
    print(f"{i:2d}. [{cls.upper()}] '{t}' ({rev} revs, {pos}% pos) | Score={sc} | Query='{q}'")
