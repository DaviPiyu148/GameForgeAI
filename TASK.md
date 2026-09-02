# GameForge AI — Task Execution Ledger

## Task
Discovery V2.4 — Promote HIDDEN_GEMS Threshold 150

## Status
COMPLETE

## Objective
Promote ONLY the validated HIDDEN_GEMS quality-confidence threshold from 2000 to 150:
1. Update `backend/app/search/ranking_config.py` and `backend/app/search/ranker.py`:
   - `DEFAULT_QUALITY_REVIEW_THRESHOLD = 2000.0`
   - `HIDDEN_GEMS_QUALITY_REVIEW_THRESHOLD = 150.0`
   - Use `review_thresh = HIDDEN_GEMS_QUALITY_REVIEW_THRESHOLD if mode == "HIDDEN_GEMS" else DEFAULT_QUALITY_REVIEW_THRESHOLD`
2. Preserve all other ranking logic strictly unchanged (landmark boost, RRF, novelty, candidate pools, BEST_MATCH, POPULAR, DISCOVER).
3. Add regression tests in `backend/tests/test_discovery_ranker.py` covering formula behavior at 50, 100, 150, 151, 250, 500, 2000, 5000 reviews and verifying strict isolation to HIDDEN_GEMS.
4. Verify key titles (*Shapebreaker*, *MOTHERED*, *Floating Farmer*, *Colony Ship*, *Farming Simulator 2013*).
5. Address and clarify the Farming Simulator 2013 report artifact.
6. Re-run production benchmarks (Standard 30 + Long-Tail 25) using the production ranker.
7. Run full regression test suite (`pytest`, `tsc`, `build`) and execute Git checkpoint.
8. Zero Gemini AI calls / 0 runtime LLM dependency.

## Started
2026-09-02

---

## 1. Production Code Implementation

- [x] Update `backend/app/search/ranking_config.py` with `DEFAULT_QUALITY_REVIEW_THRESHOLD = 2000.0` and `HIDDEN_GEMS_QUALITY_REVIEW_THRESHOLD = 150.0`
- [x] Update `backend/app/search/ranker.py` to use `review_thresh = 150.0` in `HIDDEN_GEMS` mode
- [x] Ensure non-HIDDEN_GEMS modes maintain `review_thresh = 2000.0`
- [x] Keep landmark boost and novelty completely unchanged

### Evidence
- `backend/app/search/ranking_config.py`: Defined constants `DEFAULT_QUALITY_REVIEW_THRESHOLD = 2000.0` and `HIDDEN_GEMS_QUALITY_REVIEW_THRESHOLD = 150.0`.
- `backend/app/search/ranker.py`: In `Ranker.rank_hybrid()`, quality score calculation dynamically branches:
  `review_thresh = HIDDEN_GEMS_QUALITY_REVIEW_THRESHOLD if mode == "HIDDEN_GEMS" else DEFAULT_QUALITY_REVIEW_THRESHOLD`.

---

## 2. Regression Tests & Verification

- [x] Add unit tests for quality score formula across 8 review count checkpoints
- [x] Verify mode isolation (BEST_MATCH, POPULAR, DISCOVER vs HIDDEN_GEMS)
- [x] Verify key title trajectories in production ranker
- [x] Run benchmark validation script comparing Before (2000) vs After (150)
- [x] Verify Farming Simulator 2013 report artifact resolution

### Evidence
- `backend/tests/test_discovery_ranker.py`: Added 3 tests (`test_quality_review_threshold_constants`, `test_quality_factor_at_review_checkpoints`, `test_rank_hybrid_mode_threshold_isolation`). All passed in 0.11s.
- `backend/scripts/verify_production_promotion.py`: Evaluated live `DiscoveryService.search()` on Standard 30 & Long-Tail 25.
  - Standard 30 Precision@5: **0.9067** (vs Before: 0.8733)
  - Long-Tail Exposure@5: **72.8%** (vs Before: 64.8%)
  - Top-5 Surface Rate: **52.0%** (vs Before: 40.0%)
  - <100 Reviews Share: **11.2%** (controlled, zero spam)
  - Mid-Tail Share (100–1,999 reviews): **48.0%** (vs Before: 32.0%)
  - Hard Violations: **0**
  - Non-HIDDEN_GEMS regression: BEST_MATCH = **0.9067**, POPULAR = **0.9200**, DISCOVER = **0.8867** (0 violations).
- Farming Simulator 2013 report artifact: Verified in `backend/data/fine_threshold_sweep_results.json` that data was always `Q:0.1035, N:0.0452`. The `N:0.104` was a typographical error in the previous markdown table cell.

---

## 3. Full Suite & Git Checkpoint

- [x] `pytest tests/ -q`: 440 passed in 147.30s
- [x] `npx tsc --noEmit`: Clean (exit code 0)
- [x] `npm run build`: Vite build clean in 1.13s
- [x] Review `git diff`, `git diff --stat`, and `git status`
- [x] Commit created
- [x] Working tree clean

### Evidence
- 440 pytest passed.
- Frontend builds cleanly with zero TypeScript errors.


---

## 1. Experimental Design & Fine-Grained Harness

- [x] Implement fine-grained threshold runner `backend/scripts/sweep_fine_quality_thresholds.py`
- [x] Define 12 fine review bands and cumulative low-review metrics (<100, <125, <150, <200, <250)
- [x] Measure margin distribution between Top-5 winner and Top-20 long-tail loser
- [x] Keep novelty formula and all other ranking terms strictly identical
- [x] Track archetypal title trajectories (*Shapebreaker*, *MOTHERED*, *Floating Farmer*, *Colony Ship*, *Slay the Spire*, *Farming Simulator 2013*)
- [x] Run regression checks on BEST_MATCH and POPULAR modes

### Evidence
- `backend/scripts/sweep_fine_quality_thresholds.py`: Swept across T2000, T250, T200, T175, T150, T125, and T100 across 55 queries each (385 total query runs).
- Full dataset saved to `backend/data/fine_threshold_sweep_results.json`.
- `backend/scripts/inspect_low_review_top5.py`: Qualitative signal check of <100 review titles entering Top-5.
- Pytest suite: 14 passed in 35.02s (`pytest backend/tests/test_mode_candidate_pools.py backend/tests/test_discovery_ranker.py backend/tests/test_discovery_api.py -q`).

---

## 2. Key Findings & Knee Point Analysis

### Decision Matrix Summary:
- **T2000 (Control)**: Prec@5: **0.8733** | LT-Exp@5: **64.8%** | Surface: **40.0%** | <100 Rev: **12.0%** | Mid-Tail (100-1999): **32.0%** | Med Revs: **2,379** | Margin: **0.0585**
- **T250**: Prec@5: **0.9000** | LT-Exp@5: **74.4%** | Surface: **44.0%** | <100 Rev: **11.2%** | Mid-Tail (100-1999): **47.2%** | Med Revs: **1,368** | Margin: **0.0571**
- **T200**: Prec@5: **0.9000** | LT-Exp@5: **75.2%** | Surface: **44.0%** | <100 Rev: **11.2%** | Mid-Tail (100-1999): **49.6%** | Med Revs: **1,189** | Margin: **0.0512**
- **T175**: Prec@5: **0.9000** | LT-Exp@5: **75.2%** | Surface: **44.0%** | <100 Rev: **11.2%** | Mid-Tail (100-1999): **50.4%** | Med Revs: **1,164** | Margin: **0.0482**
- **T150 (Knee Point / Optimal Balance)**: Prec@5: **0.9000** | LT-Exp@5: **76.0%** | Surface: **48.0%** | <100 Rev: **12.8%** | Mid-Tail (100-1999): **49.6%** | Med Revs: **1,119** | Margin: **0.0453**
- **T125**: Prec@5: **0.9000** | LT-Exp@5: **77.6%** | Surface: **56.0%** | <100 Rev: **13.6%** | Mid-Tail (100-1999): **51.2%** | Med Revs: **1,049** | Margin: **0.0400**
- **T100**: Prec@5: **0.9067** | LT-Exp@5: **77.6%** | Surface: **60.0%** | <100 Rev: **16.0%** | Mid-Tail (100-1999): **48.8%** | Med Revs: **1,049** | Margin: **0.0374**

### Critical Knee Point Identification:
1. **Long-Tail Exposure Flattens**: Going from T125 to T100, Long-Tail Exposure@5 is completely flat at **77.6%** (0.0% gain).
2. **Mid-Tail Cannibalization at T100**: In T100, the validated mid-tail (100-1,999 reviews) **drops** from 51.2% to 48.8%, while <100-review games surge from 13.6% to 16.0% (and <125 reviews reaches 19.2%).
3. **Quality Signal Breakdown**: Qualitative audit reveals that in T100, weakly relevant titles (e.g., *Love Colors* with SemRank #200 and *Path of Ra* with SemRank #200) infiltrate the Top-5 purely due to lexical artifacts, whereas in T150–T175, only games with top-tier semantic alignment (*Spaceport Trading Company*, *Medieval Blacksmith*, *Toy Trains*) surface.
4. **Conclusion**: **T150** (or **T175**) is the true knee point where long-tail surfacing is maximized while preserving strict resistance to low-confidence lexical noise.


---

## 1. Experimental Design & Quality Formulation

- [x] Design bounded Review-Independent Quality variant (Q6) using Bayesian shrinkage: `smoothed_pos = (pos_pct * reviews + 0.75 * 20.0) / (reviews + 20.0)`
- [x] Implement standalone experiment runner `backend/scripts/experiment_ranker_tuning.py`
- [x] Implement review band classifier (8 bands from 1-49 to 5000+) and multi-variant evaluation harness
- [x] Keep novelty formula and all other ranking terms strictly identical

### Evidence
- `backend/scripts/experiment_ranker_tuning.py`: Evaluates all 7 variants across 55 total queries per variant (385 query evaluations).
- Evaluated both Standard 30 Benchmark and Dedicated 25 Long-Tail Benchmark.
- Saved full dataset to `backend/data/ranker_tuning_experiment_results.json`.

---

## 2. Benchmark Results & Decision Matrix

- [x] Standard 30-Query Benchmark: Precision@5, Hard Violations, Latency
- [x] Dedicated 25-Query Long-Tail Benchmark: Exposure@5, Reach, Median/Mean reviews
- [x] Review-Band Distribution across 8 buckets
- [x] Key Title Trajectories (*Shapebreaker*, *MOTHERED*, *Floating Farmer*, *Colony Ship*, *Slay the Spire*, *Farming Simulator 2013*)
- [x] Experiment 2: Topic-Tag Landmark Boost (L0 vs L1)
- [x] Regression Check: BEST_MATCH and POPULAR

### Results & Findings
- **Decision Matrix (Quality Thresholds)**:
  - Control (thresh=2000): Prec@5: **0.8733** | LT-Exp@5: **64.8%** | Surface: **40.0%** | Median Revs: **2379** | Hard Viol: **0**
  - Q1 (thresh=1000): Prec@5: **0.8867** | LT-Exp@5: **67.2%** | Surface: **36.0%** | Median Revs: **2143** | Hard Viol: **0**
  - Q2 (thresh=500): Prec@5: **0.8933** | LT-Exp@5: **71.2%** | Surface: **40.0%** | Median Revs: **1665** | Hard Viol: **0**
  - **Q3 (thresh=250)**: Prec@5: **0.9000** | LT-Exp@5: **74.4%** | Surface: **44.0%** | Median Revs: **1368** | Hard Viol: **0** (Pareto Optimal!)
  - Q4 (thresh=100): Prec@5: **0.9067** | LT-Exp@5: **77.6%** | Surface: **60.0%** | Median Revs: **1049** | Hard Viol: **0**
  - Q5 (thresh=50): Prec@5: **0.9067** | LT-Exp@5: **80.0%** | Surface: **76.0%** | Median Revs: **655** | Hard Viol: **0** (Overcorrection into <100 revs)
  - Q6 (Bayes): Prec@5: **0.9067** | LT-Exp@5: **80.0%** | Surface: **72.0%** | Median Revs: **629** | Hard Viol: **0** (Overcorrection into <100 revs)
- **Overcorrection Analysis**:
  - In Q5 and Q6, games with <100 reviews jump from 12% to **23.2%–24.8%** of all Top-5 recommendations, crowding out established indie titles.
  - In **Q3 (thresh=250)**, games with <100 reviews remain at a healthy **11.2%**, while indie mid-tail (100–1999 reviews) expands from 32.0% to **47.2%**, achieving a smooth, balanced discovery distribution.
- **Key Title Trajectories**:
  - *MOTHERED* (287 revs): Moves from #4 (score 0.56) in Control $\to$ **#1 (score 0.65)** in Q250.
  - *Shapebreaker* (50 revs): Consistently holds **#1** across all variants (0.74 $\to$ 0.76 in Q250 $\to$ 0.83 in Q50).
  - *Floating Farmer* (62 revs): Holds **#5** (0.66 $\to$ 0.68 in Q250) without artificially displacing higher-relevance titles.
  - *Slay the Spire* (166k revs): Drops gracefully from #2 to **#4**, remaining a relevant landmark while opening top slots.
- **Experiment 2 (Landmark Boost L0 vs L1 on Q250)**:
  - Precision@5: 0.9000 (L0) vs 0.9000 (L1)
  - Long-Tail Exposure@5: 74.4% (L0) vs 74.4% (L1)
  - Landmark boost does not affect multi-concept queries, but L1 provides a safer cap for tag-based queries.
- **Regression Check**:
  - BEST_MATCH Precision@5: 0.8933 vs 0.8933 (Delta: +0.0000)
  - POPULAR Precision@5: 0.9067 vs 0.9067 (Delta: +0.0000)
  - Zero regression confirmed across non-HIDDEN_GEMS modes.


---

## 1. Ranker Codebase Audit & Score Pipeline Reconstruction

- [x] Audit `backend/app/search/ranker.py` and `backend/app/search/ranking_config.py`
- [x] Document exact equations for RRF, direct score, quality multiplier, novelty multiplier, landmark boost, and diversity adjustment
- [x] Investigate MMR diversity implementation: revealed that vector MMR is NOT implemented in `ranker.py`; only soft franchise name deduplication exists
- [x] Construct standalone score decomposition diagnostic script `backend/scripts/audit_ranker_scores.py`

### Evidence
- Audited `Ranker.rank_hybrid()` lines 360–575.
- Identified that `final_score = (core_relevance * relevance_mult) + quality_score + novelty_score + personalization - negative_penalty`.
- Found that `quality_score = 0.08 * (pos_pct * min(1.0, reviews / 2000.0)) * 1.4` heavily penalizes games under 2,000 reviews by up to $-0.109$.
- Found that `novelty_score` tops out at $+0.116$ for 50-review games, creating an almost exact cancellation ($+0.1162 - 0.1092 = +0.0070$), neutralizing the novelty treatment.

---

## 2. Quantitative Diagnostic & Bottleneck Analysis

- [x] Evaluated all 30 Standard Benchmark queries and 25 Long-Tail Benchmark queries
- [x] Computed component-by-component winner vs loser deltas across 32 Top-5 loss events
- [x] Saved comprehensive audit artifact to `backend/data/ranker_score_decomposition.json`
- [x] Computed correlation between score signals and final ranking score in Top-20

### Results & Findings
- **Primary Cause of Top-5 Loss**:
  - Quality Score Penalty (`reviews < 2000`): **65.6%** (21/32)
  - Novelty cancelled by Quality review penalty: **12.5%** (4/32)
  - Retrieval RRF Base Score advantage: **12.5%** (4/32)
  - Combination of RRF + Quality penalty: **6.2%** (2/32)
  - Topic Tag Landmark Boost (+0.15 to +0.25 to head): **3.1%** (1/32)
  - MMR / Diversity penalty: **0.0%** (0/32)
- **Signal Correlation with Final Score in Top-20**:
  - RRF Base Score: **+0.6628**
  - Quality Score: **+0.1047**
  - Log(Total Reviews): **+0.1718** (Net positive bias towards higher review counts despite HIDDEN_GEMS mode)
  - Novelty Score: **-0.1659** (Inverted: higher novelty correlates with lower final ranking)
- **Quality/Novelty Sweet Spot**:
  - Mid-tier titles with 1,000–5,000 reviews (*Colony Ship*, *Farming Simulator 2013*, *Space Haven*) receive BOTH the maximum quality score (~0.10) and a moderate novelty score (~0.05), beating genuine low-review hidden gems (<500 reviews) every time.

---

## 3. Regression & Production State Verification

- [x] Run full discovery regression test suite: 14 passed in 38.94s
- [x] Zero Gemini calls (100% local deterministic pipeline)
- [x] Production index and ranking weights untouched (`PRODUCTION CHANGE: NOT APPLIED`)

- [x] Inspect existing Discovery runtime pipeline from query to final top-K
- [x] Investigate the earlier experiment discrepancy (*Shapebreaker* / *Colony Ship* presence in 20k index vs Reviewed-Only index)
- [x] Verify index identity and metadata for 20k (`data/processed/games_index.faiss`) vs Reviewed-Only (`data/benchmark_indexes/games_index_reviewed_only.faiss`)
- [x] Design non-invasive diagnostic instrument (`backend/scripts/audit_candidate_overlap.py`) to trace candidates per stage

### Evidence
- **Discrepancy Explained**:
  - In `games_catalog.json`: *Colony Ship: A Post-Earth Role Playing Game* (2,567 reviews) is at catalog position **4,083** (already inside the 20k head!). In `HIDDEN_GEMS` mode, its low review count (<15k) gives it a max novelty multiplier (2.2x), so it was already the top pick on the 20k index.
  - *Shapebreaker - Tower Defense Deckbuilder* (50 reviews) is at catalog position **32,174** (outside 20k head). In the previous benchmark script `benchmark_mode_candidate_pools.py`, `service_20k_all.search(mode="HIDDEN_GEMS")` was routed dynamically to `REVIEWED_ONLY` inside `DiscoveryService.search()`, causing both columns to query the Reviewed-Only pool. When properly restricted to 20k, 20k returns *Slay the Spire* / *Cobalt Core*, while Reviewed-Only returns *Shapebreaker*!
- **Index Identity Verified**:
  - 20k Index: `ntotal = 20,000`, `dim = 384`, `model = all-MiniLM-L6-v2`, 0 zero-review records.
  - Reviewed-Only Index: `ntotal = 87,890`, `dim = 384`, `model = all-MiniLM-L6-v2`, 0 zero-review records.
  - Set overlap: 20k is a strict subset of Reviewed-Only (`True`), exactly 67,890 additional non-zero review records.

---

## 2. Candidate Overlap & Reach Rate Diagnostic

- [x] Create standalone diagnostic script `backend/scripts/audit_candidate_overlap.py`
- [x] Trace candidates across 6 pipeline stages: Dense Top-50, Lexical Top-50, RRF Candidates, Post-Filter Candidates, Post-Ranking Top-20, and Final Top-5
- [x] Calculate stage-by-stage Jaccard similarity and reach rates (% queries adding new long-tail candidates)
- [x] Classify every query into Bottleneck Cases A through F
- [x] Persist diagnostic artifact to `backend/data/candidate_overlap_diagnostic.json`

### Results & Findings
- **Standard 30-Query Benchmark Overlap**:
  - Dense FAISS Top-50 Reach Rate: **100.0%** (avg 38 new candidates per query, Jaccard = 0.1573)
  - Lexical Top-50 Reach Rate: **80.0%** (Jaccard = 0.6310)
  - RRF Fused Candidates Reach Rate: **100.0%** (avg 42 new candidates per query, Jaccard = 0.3329)
  - Post-Hard-Filter Reach Rate: **100.0%**
  - Post-Ranking Top-20 Reach Rate: **100.0%** (avg 12 out of 20 in Top-20 are new long-tail titles, Jaccard = 0.2500)
  - Final Top-5 Recommendations Reach Rate: **30.0%** (9/30 queries surfaced new long-tail titles in Top-5, Jaccard = 0.4818)
  - Bottleneck Distribution: **Case E (Top-20 to Top-5 Drop) = 70.0% (21/30)**, **Case F (Surfaces in Top-5) = 30.0% (9/30)**. Cases A, B, C, D = 0.0%.

---

## 3. Dedicated 25-Query Long-Tail Discovery Benchmark

- [x] Design 25 deterministic, niche, multi-constraint queries from catalog vocabulary
- [x] Evaluate candidate overlap and stage-by-stage reach rates
- [x] Measure Long-Tail Exposure@5 (review threshold $\le 5,000$), review distribution, and zero-review counts

### Results & Findings
- **Long-Tail 25-Query Benchmark Overlap**:
  - Dense FAISS Top-50 Reach Rate: **100.0%** (avg 35 new candidates)
  - Lexical Top-50 Reach Rate: **84.0%**
  - RRF Fused Candidates Reach Rate: **100.0%** (avg 44 new candidates)
  - Post-Ranking Top-20 Reach Rate: **100.0%** (avg 11 out of 20 in Top-20 are new long-tail titles)
  - Final Top-5 Recommendations Reach Rate: **40.0%** (10/25 queries surfaced new long-tail titles in Top-5)
  - Bottleneck Distribution: **Case E = 60.0% (15/25)**, **Case F = 40.0% (10/25)**. Cases A, B, C, D = 0.0%.
- **Long-Tail Exposure@5 ($\le 5,000$ reviews)**:
  - 20k Universe: **59.2%**
  - Reviewed-Only Universe (87.9k): **64.8%** (+5.6% indie long-tail exposure)
  - Zero-Review Games in Top-5: **0 (0.00%)**
  - Median Review Count: **3,305** (20k) $\rightarrow$ **2,379** (Reviewed-Only)

---

## 4. Five Hidden Gems Archetypes Stage-by-Stage Tracing

- [x] Deeply trace `"deckbuilder"`, `"co-op survival"`, `"cyberpunk rpg"`, `"space exploration"`, `"relaxing farming"`
- [x] Compare 20k candidate pool vs Reviewed-Only candidate pool stage by stage

### Evidence
- **"deckbuilder"**:
  - Dense: 37 new candidates | RRF: 38 new candidates | Top-20: 11 new candidates | Top-5: 1 new candidate (*Shapebreaker* at #1, 50 reviews, Catalog pos 32,174).
  - 20k Top-5: *Slay the Spire*, *Cobalt Core*, *Gordian Quest*, *Neurodeck*, *Nadir*.
  - Rev Top-5: *Shapebreaker*, *Slay the Spire*, *Neurodeck*, *Mahokenshi*, *Cobalt Core*.
- **"cyberpunk rpg"**:
  - Dense: 43 new candidates | RRF: 44 new candidates | Top-20: 12 new candidates | Top-5: 0 new candidates (Head games *Colony Ship* [pos 4083, 2.5k revs], *Fallout*, *Fallout 2*, *MOTHERED*, *VA-11 Hall-A* fill Top-5).
- **"relaxing farming"**:
  - Dense: 29 new candidates | RRF: 35 new candidates | Top-20: 6 new candidates | Top-5: 1 new candidate (*Floating Farmer - Logic Puzzle*, 62 reviews, pos 48,220).
  - 20k Top-5: *Farming Simulator 2013*, *Farmer's Life*, *Farm Together*, *Rusty's Retirement*, *Farming Simulator 15*.
  - Rev Top-5: *Farming Simulator 2013*, *Farm Together*, *Farmer's Life*, *Instant Farmer*, *Floating Farmer*.

---

## 5. Performance, Memory & Regression Verification

- [x] Verify lazy-load isolation: `BEST_MATCH` does not load Reviewed-Only index into RAM
- [x] Verify in-memory caching: `HIDDEN_GEMS` reuses cached index without reloading
- [x] Run full discovery pytest suite: 47 passed in 34.29s
- [x] Run frontend linter: 0 errors on 72 files
- [x] Run frontend build: `tsc -b && vite build` built in 2.31s
- [x] Verify production isolation: `PRODUCTION CHANGE: NOT APPLIED`

---

## Remaining Work
None. Diagnostic is complete and findings ready for presentation.

## Blockers
None.

## Change Log
- 2026-09-02: Created `backend/scripts/audit_candidate_overlap.py` and `backend/scripts/print_diagnostic_summary.py`.
- 2026-09-02: Executed candidate overlap diagnostic on Standard 30 Benchmark and Dedicated 25-Query Long-Tail Benchmark.
- 2026-09-02: Resolved and proved the earlier experiment discrepancy (*Colony Ship* / *Shapebreaker*).
- 2026-09-02: Verified all automated tests, memory isolation, and confirmed `PRODUCTION CHANGE: NOT APPLIED`.

  - `DiscoveryService.search()` workflow
  - Intent classification
  - Dense/FAISS retrieval (`FAISSIndexManager`)
  - Lexical retrieval (`LexicalIndex` / `CatalogManager`)
  - RRF fusion ($k=60$)
  - Hard constraint validation & quality/diversity filtering
  - Mode-specific scoring (`BEST_MATCH`, `DISCOVER`, `HIDDEN_GEMS`, `POPULAR`)
- [x] Determine how candidate pool restriction can be enforced symmetrically on:
  - Dense search (pool-specific FAISS index)
  - Lexical search (pool-restricted search / candidate ID filtering before RRF)
- [x] Verify existing index artifacts (`games_index_20k.faiss`, `games_index_reviewed_only.faiss`)

### Evidence
- Audited `DiscoveryService.search()`, `FAISSIndexManager`, `LexicalIndex`, and `Ranker.rank_hybrid()`.
- Identified that dense retrieval queries FAISS and lexical retrieval queries the inverted index; both candidate lists are passed to `Ranker.rank_hybrid()`.
- Designed symmetric candidate pool enforcement: dense retrieval queries pool-specific index, and lexical retrieval strictly filters candidates against the candidate pool (`_reviewed_game_ids` for `REVIEWED_ONLY` and `_twenty_k_game_ids` for `POPULAR_20K`). Zero-review candidates are 100% prevented from entering RRF.

---

## 2. Implementation & Multi-Pool Architecture

- [x] Define `DiscoveryCandidatePool` policy abstraction (Mode -> Candidate Pool mapping)
- [x] Update `FAISSIndexManager` or provide a Multi-Index Manager with lazy-loading for `20k` vs `reviewed_only`
- [x] Update lexical retrieval to respect candidate pool restriction before RRF fusion
- [x] Maintain exact existing ranking formulas for all 4 modes
- [x] Ensure `BEST_MATCH` and `POPULAR` remain mapped to 20k pool
- [x] Ensure `HIDDEN_GEMS` and `DISCOVER` remain mapped to reviewed-only pool (87,890 games)

### Evidence
- `backend/app/search/candidate_pool.py`: Defined `DiscoveryCandidatePool` enum (`POPULAR_20K`, `REVIEWED_ONLY`, `FULL_CATALOG`), `MODE_CANDIDATE_POOLS` mapping, and `get_candidate_pool_for_mode(mode)`.
- `backend/app/search/index.py`: Enhanced `FAISSIndexManager` with lazy multi-pool loader (`_get_or_load_pool`), supporting `search()`, `get_id_set()`, `get_id_mapping()`, `is_ready(pool=...)`, and caching.
- `backend/app/search/lexical.py`: Added `_twenty_k_game_ids` and `_reviewed_game_ids` sets to `LexicalIndex`. In `search_lexical()`, restricted candidate pool and entity candidates according to `candidate_pool`.
- `backend/app/services/discovery_service.py`: Looked up `candidate_pool` from `mode`, passing it to both `self.index_manager.search(query_vec, top_k=top_k, pool=candidate_pool)` and `self.lexical_index.search_lexical(..., candidate_pool=candidate_pool)`.

---

## 3. Automated Testing & Invariant Verification

- [x] Test candidate pool policy mapping for all modes
- [x] Test reviewed-only invariant (`total_reviews > 0`) for `HIDDEN_GEMS` and `DISCOVER` candidates
- [x] Test retrieval consistency: verify lexical search cannot return zero-review games in reviewed-only mode
- [x] Test lazy-loading and multi-pool memory reuse
- [x] Run full pytest suite (`pytest tests/ -q`)

### Evidence
- Created `backend/tests/test_mode_candidate_pools.py` with 3 test suites:
  1. `test_candidate_pool_mode_mappings`: PASSED
  2. `test_lexical_index_candidate_pool_filtering`: PASSED (verified zero-review isolation in 20k and reviewed-only pools)
  3. `test_multi_pool_discovery_service_invariants`: PASSED (verified end-to-end `BEST_MATCH`, `HIDDEN_GEMS`, and `DISCOVER`)
- Ran `pytest tests\test_discovery_*.py tests\test_mode_candidate_pools.py`: 53 passed in 65.25s.
- Ran full backend test suite: 437 passed in 195s.

---

## 4. Benchmark & Qualitative Probing

- [x] Execute 30-query benchmark comparing `All 20k Baseline` vs `Mode-Specific Candidate Pools`
- [x] Run per-mode benchmark across all 4 modes
- [x] Run 5-archetype Hidden Gems probe (review distributions & title qualitative check)
- [x] Run 5-archetype Discover probe (novelty & title qualitative check)
- [x] Measure latency breakdown (cold load, warm load, embed inference, FAISS search, lexical search, RRF/ranking)

### Results
- Created `backend/scripts/benchmark_mode_candidate_pools.py` and saved artifact to `backend/data/mode_pools_benchmark_results.json`.
- **Main 30-Query Benchmark Results**:
  - `Precision@5`: **0.9000** (Baseline) vs **0.9000** (Mode-Specific Candidate Pools) — 100% parity maintained.
  - `Hard Violations`: **0** vs **0** (Zero constraint violations across all queries).
  - `Intent Accuracy`: **90.0%** vs **90.0%**.
  - `Avg Latency`: 398.4ms (Baseline) vs 428.1ms (Mode-Specific).
  - `P95 Latency`: 838.2ms (Baseline) vs 772.5ms (Mode-Specific).
- **Per-Mode Precision & Quality**:
  - `BEST_MATCH` (20k): Precision@5 = **0.9000**, 0 zero-review results, avg reviews = 95,082.3
  - `POPULAR` (20k): Precision@5 = **0.9200**, 0 zero-review results, avg reviews = 103,401.3
  - `DISCOVER` (Reviewed-Only 87.9k): Precision@5 = **0.8867**, 0 zero-review results, avg reviews = 86,921.6
  - `HIDDEN_GEMS` (Reviewed-Only 87.9k): Precision@5 = **0.8733**, 0 zero-review results, avg reviews = 71,570.9
- **Latency Breakdown**:
  - Embedding Inference: ~11ms
  - Dense FAISS Search (20k): 2.32ms
  - Dense FAISS Search (Reviewed-Only 87.9k): 9.06ms (+6.7ms delta)
  - Lexical Retrieval: ~205-219ms
  - RRF Fusion & Ranking: ~15-19ms
  - Total Query Latency: 237.8ms (20k) vs 255.5ms (Reviewed-Only).

---

## 5. Final Report & Regression Checks

- [x] Run frontend checks: `npx tsc --noEmit`, `npx oxlint`, `npm run build`
- [x] Complete Final Report (Sections A through I)
- [x] Confirm `PRODUCTION CHANGE: NOT APPLIED`
- [x] Mark task `COMPLETE`

### Results
- `npm run build`: `tsc -b && vite build` built in 2.25s, exit code 0.
- `npx oxlint`: 0 warnings, 0 errors across 72 files.
- `pytest tests/`: All backend tests passed.
- Production index `backend/data/processed/games_index.faiss` is 100% UNTOUCHED (`PRODUCTION CHANGE: NOT APPLIED`).

---

## Remaining Work
None.

## Blockers
None.

## Change Log
- 2026-09-02: Completed Mode-Specific Candidate Pools Experiment. All unit tests, invariant tests, benchmark runs, probe evaluations, and frontend checks passed. Task complete.
- 2026-09-02: Completed Previous Experiment: Reviewed-Only Candidate Pool Benchmark (87,890 reviewed vs 33,735 zero-review).


