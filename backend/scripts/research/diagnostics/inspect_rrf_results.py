import json

with open('backend/data/discover_rrf_damping_experiment_results.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print('=== 5 LEXICAL OVERMATCHING CASES IN CONDITION B vs CONDITION C ===')
titles_to_check = [
    'The Road to Hades',
    'Stealth',
    'Mini Pipes - A Logic Puzzle Pipes Game',
    'Strategy',
    'Time Master'
]

disc_b_traces = d['exploratory_25_benchmark']['condition_b']['per_query_traces']
disc_c_traces = d['exploratory_25_benchmark']['condition_c']['per_query_traces']

for target in titles_to_check:
    print(f'\nGame: {target}')
    # Check in B
    found_b = False
    for tr in disc_b_traces:
        for c in tr['top5_deconstructed']:
            if target.lower() in c['title'].lower():
                print(f" In B: Query='{tr['query']}' -> Rank={c['final_rank']}, Score={c['calibrated_score']}, RRF={c['rrf_raw']}, sem_rank={c['sem_rank']}, lex_rank={c['lex_rank']}")
                found_b = True
    if not found_b:
        print(' In B: Not in Top 5')

    # Check in C
    found_c = False
    for tr in disc_c_traces:
        for c in tr['top5_deconstructed']:
            if target.lower() in c['title'].lower():
                print(f" In C: Query='{tr['query']}' -> Rank={c['final_rank']}, Score={c['calibrated_score']}, RRF={c['rrf_raw']}, sem_rank={c['sem_rank']}, lex_rank={c['lex_rank']}")
                found_c = True
    if not found_c:
        print(' In C: SUPPRESSED! (Dropped out of Top 5)')

print('\n=== CRITICAL SUCCESS CASES TRACE ===')
for sc in d['critical_success_cases']:
    qid = sc['id']
    q = sc['query']
    exp = sc['expected_title']
    print(f"\n[{qid}] Query: '{q}' (Target: {exp})")
    for cond in ['a', 'b', 'c']:
        c = sc[f'candidate_in_{cond}']
        if c:
            r = c['final_rank']
            s = c['calibrated_score']
            sr = c['sem_rank']
            lr = c['lex_rank']
            rrf = c['rrf_raw']
            print(f" Cond {cond.upper()}: Rank={r}, Score={s}, sem_rank={sr}, lex_rank={lr}, RRF={rrf}")
        else:
            print(f" Cond {cond.upper()}: Not in Top 20")
    print(' Top 5 Titles in C:', sc['top5_titles_c'])

print('\n=== LEXICAL FALSE-POSITIVE AUDIT ===')
audit_cases = d['lexical_false_positive_audit']
print(f'Total Queries with Single-Channel Lexical candidates in Top 5: {len(audit_cases)}')
for ac in audit_cases:
    q = ac['query']
    in_b = ac['single_channel_in_b']
    in_c = ac['single_channel_in_c']
    print(f"\nQuery: '{q}'")
    print(f" In B: {[c['title'] + ' (rank ' + str(c['final_rank']) + ', score ' + str(c['score']) + ')' for c in in_b]}")
    print(f" In C: {[c['title'] + ' (rank ' + str(c['final_rank']) + ', score ' + str(c['score']) + ')' for c in in_c]}")
