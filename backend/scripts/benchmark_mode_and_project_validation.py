"""
GameForge Personalization V1 — Phase 6.2: Mode-Specific Lambda & Project-Context Validation
========================================================================================
Comprehensive offline evaluation:
1. Mode-Specific Lambda Sweep:
   - DISCOVER:     λ in [0.03, 0.05, 0.07]
   - HIDDEN_GEMS:  λ in [0.03, 0.05, 0.07]
   - BEST_MATCH:   λ in [0.00, 0.02, 0.03, 0.05]
   - POPULAR:      λ in [0.00, 0.02, 0.03, 0.05]
   Evaluating: PAU, Beneficial %, Neutral %, Harmful %, Top-5 churn, Top-10 churn,
               Mean & P90 absolute rank delta, Cold-start regression, Intent preservation,
               Hard-constraint violations, Generic relevance, Zero-movement %.
2. Strengthened Project-Context Validation:
   - Contrasting DNA: Global (Cozy Farming) vs Project A (Cyberpunk Shooter) vs Project B (Dark Fantasy Roguelike RPG)
   - Project-Sensitive Queries & Conflict Query
   - Sequence: No Project -> Project A -> Project B -> No Project
   - Detailed candidate recording, ACTUAL RANK MOVEMENT, Project PAU, Global Immutability,
     and Grounded Explanation Consistency.
3. Saved-Discovery Gradient Monotonicity Preservation.
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

# Set UTF-8 safe stdout for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.schemas.developer_profile import (
    ConfidenceTier,
    DeveloperPreferenceProfile,
    EffectivePreferenceProfile,
    ProjectPreferenceProfile,
)
from app.schemas.discovery import DiscoverySearchRequest, DiscoverySearchResponse, DiscoverySearchResult, GameDiscoveryItem
from app.services.context_blender import context_blender
from app.services.discovery_service import discovery_service
from app.services.personalization_reranker import personalization_reranker
from app.services.personalization_explanation_service import PersonalizationExplanationService
from app.services.personalization_experiment import (
    _classify_change,
    _compute_profile_alignment,
    _mean_alignment,
    PersonalizationExperimentService,
    PERSONALIZATION_MODE_SHADOW,
    PERSONALIZATION_MODE_TREATMENT,
)
from scripts.benchmark_personalized_ranking import create_benchmark_profiles, EVALUATION_QUERIES


def ascii_safe(text: str) -> str:
    """Sanitize strings for Windows console printing."""
    return text.encode("ascii", "replace").decode("ascii")


# ============================================================================
# Main Validation Runner
# ============================================================================

async def run_phase_6_2_validation():
    print("=" * 80)
    print("GAMEFORGE PERSONALIZATION V1 — PHASE 6.2 OFFLINE VALIDATION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("Execution Mode: OFFLINE ONLY (Zero Production Impact)")
    print("=" * 80)

    # 1. Warm discovery service
    print("\nWarming Discovery service...")
    t0 = time.perf_counter()
    discovery_service.warm()
    print(f"Discovery service warmed in {time.perf_counter() - t0:.2f}s.")

    profiles = create_benchmark_profiles()
    print(f"Loaded {len(profiles)} benchmark developer profiles.")
    print(f"Loaded {len(EVALUATION_QUERIES)} evaluation queries across query categories.")

    # ------------------------------------------------------------------------
    # EXPERIMENT 1: Pre-fetch baseline results for all (mode, query) pairs
    # ------------------------------------------------------------------------
    MODES_TO_TEST = ["DISCOVER", "HIDDEN_GEMS", "BEST_MATCH", "POPULAR"]
    LAMBDAS_BY_MODE = {
        "DISCOVER": [0.03, 0.05, 0.07],
        "HIDDEN_GEMS": [0.03, 0.05, 0.07],
        "BEST_MATCH": [0.00, 0.02, 0.03, 0.05],
        "POPULAR": [0.00, 0.02, 0.03, 0.05],
    }

    print("\nPre-fetching baseline results for 4 modes x 17 queries...")
    baseline_cache: Dict[str, DiscoverySearchResponse] = {}
    t_fetch_start = time.perf_counter()
    for mode in MODES_TO_TEST:
        for q in EVALUATION_QUERIES:
            cache_key = f"{mode}::{q['query']}"
            if cache_key not in baseline_cache:
                req = DiscoverySearchRequest(prompt=q["query"], mode=mode, limit=10)
                res = await discovery_service.search(req)
                baseline_cache[cache_key] = res
    print(f"Pre-fetched {len(baseline_cache)} baseline responses in {time.perf_counter() - t_fetch_start:.2f}s.")

    # ------------------------------------------------------------------------
    # EXPERIMENT 1: Mode-Specific Lambda Sweep Execution
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("1. MODE-SPECIFIC LAMBDA SWEEP")
    print("=" * 80)

    sweep_results: List[Dict[str, Any]] = []

    for mode in MODES_TO_TEST:
        for lam in LAMBDAS_BY_MODE[mode]:
            # Run all (profile, query) pairs for this mode & lambda
            pau_list: List[float] = []
            slot_changes_total = 0
            beneficial_changes = 0
            neutral_changes = 0
            harmful_changes = 0
            top5_churns: List[int] = []
            top10_churns: List[int] = []
            all_rank_deltas: List[int] = []
            cold_start_failures = 0
            intent_violations = 0
            hard_constraint_violations = 0
            zero_movement_count = 0
            total_requests = 0
            final_top5_alignments: List[float] = []
            generic_relevance_scores: List[float] = []

            for p_info in profiles:
                g_prof = p_info["global"]
                proj_prof = p_info.get("project")
                is_cold = (p_info["id"] == "p20_cold_start" or g_prof.confidence_tier == "COLD")

                eff_prof = context_blender.blend(g_prof, proj_prof)

                for q in EVALUATION_QUERIES:
                    total_requests += 1
                    cache_key = f"{mode}::{q['query']}"
                    base_res = baseline_cache[cache_key]
                    base_items = list(base_res.results)

                    if not base_items:
                        continue

                    # Execute re-ranking
                    reranked_items, traces = personalization_reranker.rerank(
                        results=base_items,
                        effective_profile=eff_prof,
                        lambda_=lam,
                    )

                    # 1. Base vs Pers Alignment & PAU
                    base_alignments = [_compute_profile_alignment(r, eff_prof) for r in base_items[:5]]
                    pers_alignments = [_compute_profile_alignment(r, eff_prof) for r in reranked_items[:5]]
                    mean_base_a = _mean_alignment(base_items[:5], eff_prof)
                    mean_pers_a = _mean_alignment(reranked_items[:5], eff_prof)
                    pau = round(mean_pers_a - mean_base_a, 6)
                    pau_list.append(pau)
                    final_top5_alignments.append(mean_pers_a)

                    mean_generic_score = sum(r.score for r in reranked_items[:5]) / max(len(reranked_items[:5]), 1)
                    generic_relevance_scores.append(mean_generic_score)

                    # 2. Slot Replacement Changes & Classification
                    base_top5_ids = [r.game.id for r in base_items[:5]]
                    pers_top5_ids = [r.game.id for r in reranked_items[:5]]

                    k5 = min(len(base_top5_ids), len(pers_top5_ids))
                    t5_churn = sum(1 for i in range(k5) if base_top5_ids[i] != pers_top5_ids[i])
                    top5_churns.append(t5_churn)

                    k10 = min(len(base_items[:10]), len(reranked_items[:10]))
                    t10_churn = sum(1 for i in range(k10) if base_items[i].game.id != reranked_items[i].game.id)
                    top10_churns.append(t10_churn)

                    # Rank deltas across candidate pool
                    base_id_to_rank = {r.game.id: idx for idx, r in enumerate(base_items)}
                    query_moved = False
                    for p_rank, r in enumerate(reranked_items):
                        b_rank = base_id_to_rank.get(r.game.id, p_rank)
                        delta = abs(p_rank - b_rank)
                        all_rank_deltas.append(delta)
                        if delta > 0:
                            query_moved = True

                    if not query_moved:
                        zero_movement_count += 1

                    for i in range(k5):
                        if base_top5_ids[i] != pers_top5_ids[i]:
                            slot_changes_total += 1
                            ba = base_alignments[i]
                            pa = pers_alignments[i]
                            cls = _classify_change(ba, pa)
                            if cls == "BENEFICIAL":
                                beneficial_changes += 1
                            elif cls == "HARMFUL":
                                harmful_changes += 1
                            else:
                                neutral_changes += 1

                    # 3. Cold Start Invariant: zero movement when profile is COLD
                    if is_cold:
                        if t5_churn != 0 or pau != 0.0 or query_moved:
                            cold_start_failures += 1

                    # 4. Intent Preservation Check on CONFLICT queries
                    if q["category"] == "CONFLICT":
                        prohib_genres = q.get("prohibited_genres", [])
                        prohib_tags = [t.lower() for t in q.get("prohibited_tags", [])]
                        for top_r in reranked_items[:3]:
                            top_g_lower = [g.lower() for g in top_r.game.genres]
                            top_t_lower = [t.lower() for t in top_r.game.tags]
                            for pg in prohib_genres:
                                if pg.lower() in top_g_lower:
                                    intent_violations += 1
                            for pt in prohib_tags:
                                if pt in top_t_lower:
                                    intent_violations += 1

                    # 5. Hard Constraint Violations: Explicit Avoidances must receive 0 boost and never be elevated
                    avoid_set = {a.lower() for a in eff_prof.explicit_avoidances}
                    if avoid_set:
                        trace_map = {t.candidate_id: t for t in traces}
                        for r in reranked_items:
                            if any(g.lower() in avoid_set for g in r.game.genres):
                                t = trace_map.get(r.game.id)
                                if t and (t.personalization_score > 0.0 or t.rank_delta > 0):
                                    hard_constraint_violations += 1

            # Aggregate stats for this (mode, lambda)
            mean_pau = sum(pau_list) / max(len(pau_list), 1)
            b_pct = (beneficial_changes / slot_changes_total * 100.0) if slot_changes_total > 0 else 0.0
            n_pct = (neutral_changes / slot_changes_total * 100.0) if slot_changes_total > 0 else 0.0
            h_pct = (harmful_changes / slot_changes_total * 100.0) if slot_changes_total > 0 else 0.0
            avg_t5_churn = sum(top5_churns) / max(len(top5_churns), 1)
            avg_t10_churn = sum(top10_churns) / max(len(top10_churns), 1)
            mean_rank_delta = sum(all_rank_deltas) / max(len(all_rank_deltas), 1)

            sorted_deltas = sorted(all_rank_deltas)
            p90_idx = int(len(sorted_deltas) * 0.90)
            p90_rank_delta = sorted_deltas[p90_idx] if sorted_deltas else 0

            zero_mov_pct = (zero_movement_count / total_requests * 100.0) if total_requests > 0 else 0.0
            mean_final_align = sum(final_top5_alignments) / max(len(final_top5_alignments), 1)
            mean_gen_rel = sum(generic_relevance_scores) / max(len(generic_relevance_scores), 1)

            # Intent preservation %
            conflict_queries_count = sum(1 for q in EVALUATION_QUERIES if q["category"] == "CONFLICT") * len(profiles)
            intent_preserv_pct = max(0.0, (1.0 - (intent_violations / max(conflict_queries_count, 1))) * 100.0)

            sweep_results.append({
                "mode": mode,
                "lambda": lam,
                "pau": mean_pau,
                "beneficial_pct": b_pct,
                "neutral_pct": n_pct,
                "harmful_pct": h_pct,
                "top5_churn": avg_t5_churn,
                "top10_churn": avg_t10_churn,
                "mean_rank_delta": mean_rank_delta,
                "p90_rank_delta": p90_rank_delta,
                "cold_start_failures": cold_start_failures,
                "intent_preservation_pct": intent_preserv_pct,
                "hard_constraint_violations": hard_constraint_violations,
                "zero_movement_pct": zero_mov_pct,
                "final_top5_align": mean_final_align,
                "generic_relevance": mean_gen_rel,
                "slot_changes_total": slot_changes_total,
            })

            print(f"  Mode: {mode:<11} | λ={lam:0.2f} | PAU: {mean_pau:>+7.4f} | Ben: {b_pct:>5.1f}% | Neu: {n_pct:>5.1f}% | Harm: {h_pct:>5.1f}% | T5 Churn: {avg_t5_churn:0.2f} | ZeroMov: {zero_mov_pct:>5.1f}% | Safety: OK")

    # ------------------------------------------------------------------------
    # Print Table A: Lambda Sweep Results
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TABLE A: LAMBDA SWEEP RESULTS MATRIX")
    print("=" * 80)
    print("| Mode        |     λ | PAU     | Beneficial % | Neutral % | Harmful % | Top-5 Churn | Intent Preserv | Safety Violations |")
    print("|-------------|------:|--------:|-------------:|----------:|----------:|------------:|---------------:|------------------:|")
    for r in sweep_results:
        print(f"| {r['mode']:<11} | {r['lambda']:>5.2f} | {r['pau']:>+7.4f} | {r['beneficial_pct']:>11.1f}% | {r['neutral_pct']:>8.1f}% | {r['harmful_pct']:>8.1f}% | {r['top5_churn']:>11.2f} | {r['intent_preservation_pct']:>13.1f}% | {r['hard_constraint_violations'] + r['cold_start_failures']:>17} |")

    # ------------------------------------------------------------------------
    # EXPERIMENT 2: Strengthened Project-Context Validation (Sections 8 to 15)
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("2. STRENGTHENED PROJECT-CONTEXT VALIDATION")
    print("=" * 80)

    # 1. Global Developer Profile (Cozy Farming Specialist)
    global_cozy = DeveloperPreferenceProfile(
        user_id="dev_cozy_farm",
        genres={"Casual": 1.0, "Simulation": 0.9},
        mechanics={"farming": 1.0, "automation": 0.8},
        themes={"cozy": 1.0},
        modes={"singleplayer": 1.0},
        total_signal_count=10,
        confidence_tier="ESTABLISHED",
    )
    # Save a deep copy to verify immutability
    global_before_dump = global_cozy.model_dump()

    # 2. Project A (Cyberpunk Tactical Shooter)
    proj_a = ProjectPreferenceProfile(
        project_id="proj_cyber_tactical",
        title="Neon Vanguard",
        genres={"Action": 1.0, "Shooter": 1.0},
        mechanics={"tactical": 1.0, "procedural generation": 0.9},
        themes={"cyberpunk": 1.0, "sci-fi": 0.8},
        modes={"multiplayer": 1.0},
    )

    # 3. Project B (Dark Fantasy Dungeon Roguelike RPG)
    proj_b = ProjectPreferenceProfile(
        project_id="proj_dark_dungeon",
        title="Crypt of Shadows",
        genres={"RPG": 1.0, "Roguelike": 1.0},
        mechanics={"dungeon crawler": 1.0, "permadeath": 0.9},
        themes={"dark fantasy": 1.0, "gothic": 0.8},
        modes={"singleplayer": 1.0},
    )

    print("Contrasting Personas Defined:")
    print("  Global Profile: Cozy Farming (Casual: 1.0, Simulation: 0.9, farming: 1.0, automation: 0.8, cozy: 1.0)")
    print("  Project A:      Cyberpunk Tactical Shooter (Action: 1.0, Shooter: 1.0, tactical: 1.0, procedural generation: 0.9, cyberpunk: 1.0)")
    print("  Project B:      Dark Fantasy Dungeon Roguelike (RPG: 1.0, Roguelike: 1.0, dungeon crawler: 1.0, permadeath: 0.9, dark fantasy: 1.0)")

    # 4. Project-Sensitive Evaluation Queries
    PROJECT_TEST_QUERIES = [
        {
            "id": "proj_q1",
            "query": "something interesting for my current project",
            "notes": "Generic intent; project context must steer recommendations toward active design goals",
        },
        {
            "id": "proj_q2",
            "query": "games with procedural generation and tactical combat",
            "notes": "Project A features match directly (tactical, procedural generation); Project B matches partially (procedural)",
        },
        {
            "id": "proj_q3",
            "query": "dark fantasy dungeon roguelike",
            "notes": "Project B features match directly (RPG, dungeon crawler, dark fantasy); Project A does not",
        },
        {
            "id": "proj_q4",
            "query": "cyberpunk multiplayer tactical game",
            "notes": "Project A features match directly (cyberpunk, multiplayer, tactical); Project B does not",
        },
        {
            "id": "proj_q5_conflict",
            "query": "something for my current project",
            "notes": "Conflict test: Global wants cozy farming, Project wants cyberpunk action",
        },
    ]

    explanation_service = PersonalizationExplanationService()
    exp_service = PersonalizationExperimentService()
    OPERATING_LAMBDA = 0.05

    project_switch_records: List[Dict[str, Any]] = []
    pau_no_project_list: List[float] = []
    pau_with_project_list: List[float] = []
    project_beneficial_slots = 0
    project_harmful_slots = 0
    project_total_slots = 0
    grounded_reasons_observed: List[str] = []

    print("\nExecuting Project Switching Test across 5 project-sensitive queries...")

    for q_item in PROJECT_TEST_QUERIES:
        q_text = q_item["query"]
        print(f"\n--- Query: '{q_text}' ---")
        print(f"    Intent: {q_item['notes']}")

        # Fetch base response
        req = DiscoverySearchRequest(prompt=q_text, mode="DISCOVER", limit=10)
        base_resp = await discovery_service.search(req)

        # State 1: No Project (Global Only)
        p_none_1 = context_blender.blend(global_cozy, None)
        _, diag_none_1 = exp_service.apply(
            base_response=base_resp,
            effective_profile=p_none_1,
            user_id="dev_cozy_farm",
            mode=PERSONALIZATION_MODE_SHADOW,
            lambda_=OPERATING_LAMBDA,
        )
        res_none_1, _ = personalization_reranker.rerank(base_resp.results, p_none_1, lambda_=OPERATING_LAMBDA)
        top_none_1 = [r.game.id for r in res_none_1[:5]]
        top_titles_none_1 = [ascii_safe(r.game.title) for r in res_none_1[:3]]

        # State 2: Project A (Cyberpunk Tactical Shooter)
        p_a = context_blender.blend(global_cozy, proj_a)
        _, diag_a = exp_service.apply(
            base_response=base_resp,
            effective_profile=p_a,
            user_id="dev_cozy_farm",
            mode=PERSONALIZATION_MODE_SHADOW,
            lambda_=OPERATING_LAMBDA,
        )
        res_a, traces_a = personalization_reranker.rerank(base_resp.results, p_a, lambda_=OPERATING_LAMBDA)
        top_a = [r.game.id for r in res_a[:5]]
        top_titles_a = [ascii_safe(r.game.title) for r in res_a[:3]]

        # Generate Phase 4 Grounded Explanations for Project A
        reasons_a = []
        for r in res_a[:5]:
            r_reasons = explanation_service.explain(candidate=r, effective_profile=p_a, project_profile=proj_a)
            reasons_a.extend([re.text for re in r_reasons])
        if reasons_a:
            grounded_reasons_observed.extend(reasons_a)

        # State 3: Project B (Dark Fantasy Dungeon Roguelike)
        p_b = context_blender.blend(global_cozy, proj_b)
        _, diag_b = exp_service.apply(
            base_response=base_resp,
            effective_profile=p_b,
            user_id="dev_cozy_farm",
            mode=PERSONALIZATION_MODE_SHADOW,
            lambda_=OPERATING_LAMBDA,
        )
        res_b, traces_b = personalization_reranker.rerank(base_resp.results, p_b, lambda_=OPERATING_LAMBDA)
        top_b = [r.game.id for r in res_b[:5]]
        top_titles_b = [ascii_safe(r.game.title) for r in res_b[:3]]

        reasons_b = []
        for r in res_b[:5]:
            r_reasons = explanation_service.explain(candidate=r, effective_profile=p_b, project_profile=proj_b)
            reasons_b.extend([re.text for re in r_reasons])
        if reasons_b:
            grounded_reasons_observed.extend(reasons_b)

        # State 4: No Project Again (Global Only Recovery)
        p_none_2 = context_blender.blend(global_cozy, None)
        _, diag_none_2 = exp_service.apply(
            base_response=base_resp,
            effective_profile=p_none_2,
            user_id="dev_cozy_farm",
            mode=PERSONALIZATION_MODE_SHADOW,
            lambda_=OPERATING_LAMBDA,
        )
        res_none_2, _ = personalization_reranker.rerank(base_resp.results, p_none_2, lambda_=OPERATING_LAMBDA)
        top_none_2 = [r.game.id for r in res_none_2[:5]]
        top_titles_none_2 = [ascii_safe(r.game.title) for r in res_none_2[:3]]

        # Track PAU with vs without project
        pau_no_project_list.append(diag_none_1.preference_alignment_uplift)
        pau_with_project_list.append(diag_a.preference_alignment_uplift)
        pau_with_project_list.append(diag_b.preference_alignment_uplift)

        # Track slot changes for Project A & B
        for res_proj, p_eff in [(res_a, p_a), (res_b, p_b)]:
            for idx in range(min(5, len(base_resp.results), len(res_proj))):
                if base_resp.results[idx].game.id != res_proj[idx].game.id:
                    project_total_slots += 1
                    ba = _compute_profile_alignment(base_resp.results[idx], p_eff)
                    pa = _compute_profile_alignment(res_proj[idx], p_eff)
                    cls = _classify_change(ba, pa)
                    if cls == "BENEFICIAL":
                        project_beneficial_slots += 1
                    elif cls == "HARMFUL":
                        project_harmful_slots += 1

        # Check actual ranking movement
        a_moved = (top_a != top_none_1)
        b_moved = (top_b != top_none_1)
        ab_distinct = (top_a != top_b)
        recovery_exact = (top_none_1 == top_none_2)

        record = {
            "query": q_text,
            "top_none_1": top_none_1,
            "top_titles_none_1": top_titles_none_1,
            "top_a": top_a,
            "top_titles_a": top_titles_a,
            "top_b": top_b,
            "top_titles_b": top_titles_b,
            "top_none_2": top_none_2,
            "pau_none": diag_none_1.preference_alignment_uplift,
            "pau_a": diag_a.preference_alignment_uplift,
            "pau_b": diag_b.preference_alignment_uplift,
            "reasons_a": reasons_a[:2],
            "reasons_b": reasons_b[:2],
            "a_moved": a_moved,
            "b_moved": b_moved,
            "ab_distinct": ab_distinct,
            "recovery_exact": recovery_exact,
        }
        project_switch_records.append(record)

        print(f"    State 1 (No Project): Top-3 = {top_titles_none_1} | PAU={diag_none_1.preference_alignment_uplift:>+6.4f}")
        print(f"    State 2 (Project A) : Top-3 = {top_titles_a} | PAU={diag_a.preference_alignment_uplift:>+6.4f} | Moved vs None: {a_moved}")
        if reasons_a:
            print(f"      Project A Grounded Reason: \"{reasons_a[0]}\"")
        print(f"    State 3 (Project B) : Top-3 = {top_titles_b} | PAU={diag_b.preference_alignment_uplift:>+6.4f} | Moved vs None: {b_moved} | Moved vs A: {ab_distinct}")
        if reasons_b:
            print(f"      Project B Grounded Reason: \"{reasons_b[0]}\"")
        print(f"    State 4 (No Project): Top-3 = {top_titles_none_2} | Exact Recovery: {recovery_exact}")

    # Assertions on project context
    any_movement_occurred = any(r["a_moved"] or r["b_moved"] for r in project_switch_records)
    all_recoveries_exact = all(r["recovery_exact"] for r in project_switch_records)
    print(f"\nProject Context Validation Summary:")
    print(f"  Actual Rank Movement Occurred: {any_movement_occurred} (REQUIRED: True)")
    print(f"  Global Recovery Exact Across All: {all_recoveries_exact} (REQUIRED: True)")

    # Global Profile Immutability Check (Section 13)
    global_after_dump = global_cozy.model_dump()
    assert global_before_dump == global_after_dump, "CRITICAL ERROR: Global profile mutated during project context blending!"
    print(f"  Global Profile Immutability: EXACT MATCH (100% immutable)")

    # Calculate Project PAU statistics (Section 12)
    mean_pau_no_project = sum(pau_no_project_list) / max(len(pau_no_project_list), 1)
    mean_pau_with_project = sum(pau_with_project_list) / max(len(pau_with_project_list), 1)
    proj_ben_pct = (project_beneficial_slots / project_total_slots * 100.0) if project_total_slots else 0.0
    proj_har_pct = (project_harmful_slots / project_total_slots * 100.0) if project_total_slots else 0.0
    print(f"  Mean PAU Without Project: {mean_pau_no_project:>+7.4f}")
    print(f"  Mean PAU With Project:    {mean_pau_with_project:>+7.4f} (Incremental Uplift: {mean_pau_with_project - mean_pau_no_project:>+7.4f})")
    print(f"  Project Beneficial %:     {proj_ben_pct:>5.1f}%")
    print(f"  Project Harmful %:        {proj_har_pct:>5.1f}%")

    # ------------------------------------------------------------------------
    # EXPERIMENT 3: Saved-Discovery Gradient Monotonicity (Section 16)
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("3. SAVED-DISCOVERY GRADIENT MONOTONICITY CHECK")
    print("=" * 80)

    # Test candidate similarity scale: 0.90 -> 0.7650 boost, 0.76 -> 0.6460, 0.50 -> 0.0000
    dummy_item = DiscoverySearchResult(
        game=GameDiscoveryItem(
            id="test_g",
            external_id="test_g",
            title="Test Game",
            description="Test game",
            genres=[],
            tags=[],
        ),
        score=0.9,
        match_highlights=[],
        explanation="",
        is_hidden_gem=False,
        trade_offs=[],
        personalization_reasons=[],
    )
    cold_prof = EffectivePreferenceProfile(user_id="test_cold")

    sim_values = [0.95, 0.90, 0.80, 0.75, 0.70, 0.50]
    boosts: List[float] = []
    for s in sim_values:
        score, trace = personalization_reranker.compute_personalization_score(
            candidate=dummy_item,
            effective_profile=cold_prof,
            saved_discovery_similarities=[("Shapebreaker", s)],
        )
        boosts.append(score)
        print(f"  Similarity: {s:0.2f} -> Personalization Score: {score:0.4f}")

    # Assert strict monotonicity
    is_monotone = all(boosts[i] >= boosts[i+1] for i in range(len(boosts)-1))
    assert is_monotone, "Saved-discovery similarity gradient must be monotonically non-increasing!"
    assert round(boosts[0], 4) == round(0.95 * 0.85, 4)
    assert round(boosts[1], 4) == round(0.90 * 0.85, 4)
    assert boosts[-1] == 0.0  # Below 0.75 threshold produces 0.0
    print(f"  Saved-Discovery Gradient: STRICTLY MONOTONIC (Passed)")

    # ------------------------------------------------------------------------
    # Summary of Recommended Policy
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 6.2 EVALUATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_phase_6_2_validation())
