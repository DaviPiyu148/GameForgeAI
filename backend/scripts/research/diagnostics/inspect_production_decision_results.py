import sys
sys.stdout.reconfigure(encoding='utf-8')
import json

with open('backend/data/discover_production_decision_benchmark_results.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print('=== STANDARD 30 BENCHMARK ===')
for cid, m in d['standard_30_benchmark'].items():
    p5 = m['canonical_precision_at_5']
    intent = m['intent_accuracy']
    viols = m['hard_violations']
    lat = m['avg_latency_ms']
    p95 = m['p95_latency_ms']
    sc_lex = m['single_channel_lex_count']
    print(f"{cid}: P@5={p5:.4f} | Intent={intent*100:.1f}% | Violations={viols} | AvgLat={lat:.1f}ms | P95={p95:.1f}ms | SCLex={sc_lex}")

print('\n=== EXPLORATORY 25 BENCHMARK ===')
for cid, m in d['exploratory_25_benchmark'].items():
    p5 = m['precision_at_5']
    ue = m['useful_exploratory_share']
    lte = m['long_tail_exposure_at_5']
    lts = m['top5_long_tail_share']
    reach = m['top5_reach']
    abr = m['avg_best_long_tail_rank']
    mbr = m['median_best_long_tail_rank']
    zr = m['zero_review_count']
    print(f"{cid}: P@5={p5:.4f} | UsefulExp={ue*100:.1f}% | LTExp={lte*100:.1f}% | LTShare={lts*100:.1f}% | Reach={reach*100:.1f}% | AvgBestRank={abr} | MedRank={mbr} | ZeroRev={zr}")

print('\n=== REVIEW DISTRIBUTION (EXPLORATORY 25) ===')
for cid in ['condition_a', 'condition_b']:
    dist = d['review_distribution_exp'][cid]
    c = dist['counts']
    s = dist['shares']
    sm = dist['summary']
    print(f"\n{cid}:")
    print(f"  <50 reviews:       {c['under_50']} ({s['under_50']*100:.1f}%)")
    print(f"  50-99 reviews:     {c['bracket_50_99']} ({s['bracket_50_99']*100:.1f}%)")
    print(f"  <100 reviews:      {c['under_100_total']} ({sm['under_100_share']*100:.1f}%)")
    print(f"  100-249 reviews:   {c['bracket_100_249']} ({s['bracket_100_249']*100:.1f}%)")
    print(f"  250-499 reviews:   {c['bracket_250_499']} ({s['bracket_250_499']*100:.1f}%)")
    print(f"  500-999 reviews:   {c['bracket_500_999']} ({s['bracket_500_999']*100:.1f}%)")
    print(f"  1000-1999 reviews: {c['bracket_1000_1999']} ({s['bracket_1000_1999']*100:.1f}%)")
    print(f"  2000-4999 reviews: {c['bracket_2000_4999']} ({s['bracket_2000_4999']*100:.1f}%)")
    print(f"  5000+ reviews:     {c['bracket_5000_plus']} ({s['bracket_5000_plus']*100:.1f}%)")
    print(f"  Summary: <100={sm['under_100_share']*100:.1f}% | Mid-tail (100-1999)={sm['mid_tail_100_1999_share']*100:.1f}% | Head (5000+)={sm['head_5000_plus_share']*100:.1f}%")

print('\n=== REVIEW DISTRIBUTION (STANDARD 30) ===')
for cid in ['condition_a', 'condition_b']:
    dist = d['review_distribution_std'][cid]
    c = dist['counts']
    s = dist['shares']
    sm = dist['summary']
    print(f"\n{cid}:")
    print(f"  <50 reviews:       {c['under_50']} ({s['under_50']*100:.1f}%)")
    print(f"  50-99 reviews:     {c['bracket_50_99']} ({s['bracket_50_99']*100:.1f}%)")
    print(f"  <100 reviews:      {c['under_100_total']} ({sm['under_100_share']*100:.1f}%)")
    print(f"  100-249 reviews:   {c['bracket_100_249']} ({s['bracket_100_249']*100:.1f}%)")
    print(f"  250-499 reviews:   {c['bracket_250_499']} ({s['bracket_250_499']*100:.1f}%)")
    print(f"  500-999 reviews:   {c['bracket_500_999']} ({s['bracket_500_999']*100:.1f}%)")
    print(f"  1000-1999 reviews: {c['bracket_1000_1999']} ({s['bracket_1000_1999']*100:.1f}%)")
    print(f"  2000-4999 reviews: {c['bracket_2000_4999']} ({s['bracket_2000_4999']*100:.1f}%)")
    print(f"  5000+ reviews:     {c['bracket_5000_plus']} ({s['bracket_5000_plus']*100:.1f}%)")
    print(f"  Summary: <100={sm['under_100_share']*100:.1f}% | Mid-tail (100-1999)={sm['mid_tail_100_1999_share']*100:.1f}% | Head (5000+)={sm['head_5000_plus_share']*100:.1f}%")

print('\n=== QUERY LEVEL SHIFTS (STANDARD 30) ===')
shifts = d['query_level_shifts']
print(f"Total changed queries: {len(shifts)} / 30")
beneficial = sum(1 for s in shifts if s['classification'] == 'beneficial')
neutral = sum(1 for s in shifts if s['classification'] == 'neutral')
harmful = sum(1 for s in shifts if s['classification'] == 'harmful')
print(f"Classification: Beneficial={beneficial}, Neutral={neutral}, Harmful={harmful}")

print('\n=== USEFUL EXPLORATORY AUDIT ===')
audit = d['useful_exploratory_audit']
print(f"Total new long-tail candidates in B Top-5: {len(audit)}")
c_useful = sum(1 for a in audit if a['classification'] == 'highly relevant')
c_border = sum(1 for a in audit if a['classification'] == 'borderline')
c_poor = sum(1 for a in audit if a['classification'] == 'poor')
print(f"Audit: Highly Relevant={c_useful}, Borderline={c_border}, Poor={c_poor}")
