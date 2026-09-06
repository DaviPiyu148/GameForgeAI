import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('backend/data/ranker_score_decomposition.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

targets = ['Shapebreaker', 'Slay the Spire', 'Colony Ship', 'Cyberpunk 2077', 'MOTHERED', 'Floating Farmer', 'Farming Simulator 2013']

for target in targets:
    print('=' * 80)
    print('TARGET:', target)
    for q_name, q_data in data['archetype_mode_comparison'].items():
        for mode in ['HIDDEN_GEMS', 'BEST_MATCH']:
            for c in q_data[mode]:
                if target.lower() in c['title'].lower():
                    t = c['title']
                    rev = c['reviews']
                    pos = c['pos_pct']
                    rk = c['final_rank']
                    fs = c['post_diversity_score']
                    cr = c['core_relevance']
                    nrrf = c['norm_rrf']
                    pop = c['pop_signal']
                    lm = c['landmark_boost']
                    qs = c['quality_score']
                    ns = c['novelty_score']
                    print(f"  [{mode:<11}] Query: '{q_name}' | Rank: #{rk} | Final: {fs}")
                    print(f"     Title: {t} (reviews:{rev}, positive:{pos}%)")
                    print(f"     Core Relevance: {cr} (Norm RRF: {nrrf}, Landmark: {lm}, Pop Signal: {pop})")
                    print(f"     Quality Score:  {qs:<8} | Novelty Score: {ns}")
                    print(f"     Net Quality + Novelty contribution: {round(qs + ns, 4)}")
                    break
