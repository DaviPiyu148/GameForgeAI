import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open("backend/data/candidate_overlap_diagnostic.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("Keys in data:", list(data.keys()))
archs = data.get("archetype_traces", {})

for name, trace in archs.items():
    print("=" * 95)
    print(f"ARCHETYPE: {name.upper()}")
    ov = trace["overlap"]
    for stg in ["dense", "lexical", "rrf", "post_filter", "top20", "top5"]:
        s_data = ov[stg]
        print(f"  {stg.upper():<12} | 20k: {s_data['count_20k']:<3} | Rev: {s_data['count_rev']:<3} | Overlap: {s_data['intersection_count']:<3} | New: {s_data['new_candidates_count']:<3} | Jaccard: {s_data['jaccard_similarity']:<6}")
        if s_data['new_candidates_count'] > 0:
            print(f"               New samples: {s_data['new_candidates_sample'][:2]}")
    print("  --- 20k Top 5 ---")
    for r in trace["20k"]["final_top5"]:
        print(f"    - {r['title']} (ID:{r['id']}, reviews:{r['reviews']}, score:{r['score']})")
    print("  --- Reviewed-Only Top 5 ---")
    for r in trace["reviewed_only"]["final_top5"]:
        print(f"    - {r['title']} (ID:{r['id']}, reviews:{r['reviews']}, score:{r['score']})")
