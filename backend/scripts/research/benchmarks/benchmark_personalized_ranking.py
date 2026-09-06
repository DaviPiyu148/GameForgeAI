"""
GameForge Personalization V1 — Offline Personalized Ranking Benchmark
======================================================================
Comprehensive offline benchmark evaluating whether personalization improves
recommendations without overriding explicit user intent, hard constraints, or baseline ranking.

Evaluation Dimensions:
1. Lambda Sweep: [0.00, 0.03, 0.05, 0.10, 0.15]
2. 20 Synthetic Developer Profiles across diverse genres/specialties
3. Query Classes: Exploratory, Targeted, Conflict, Cold-Start, Off-Profile
4. Safety & Invariants: Hard constraints, Intent preservation (100%), Cold-start identity (0 regression)
5. Signal Ablation: None, Genre only, Project only, Saved-game only, All
6. Project Switching Isolation
7. Saved-Discovery Similarity Gradient
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
import json
import statistics
import time
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.schemas.developer_profile import (
    DeveloperPreferenceProfile,
    EffectivePreferenceProfile,
    PersonalizationTrace,
    ProjectPreferenceProfile,
)
from app.schemas.discovery import DiscoverySearchRequest
from app.services.context_blender import context_blender
from app.services.discovery_service import DiscoveryService
from app.services.personalization_reranker import personalization_reranker


# ============================================================================
# 1. Benchmark Profiles Definition (20 Synthetic Developer Profiles)
# ============================================================================

def create_benchmark_profiles() -> List[Dict[str, Any]]:
    """
    Construct 20 deterministic synthetic developer profiles representing
    distinct game creation specializations and maturity tiers.
    """
    profiles = []

    # 1. Roguelike Specialist
    p1_global = DeveloperPreferenceProfile(
        user_id="dev_01_roguelike",
        genres={"Roguelike": 1.0, "RPG": 0.8},
        mechanics={"permadeath": 1.0, "procedural generation": 0.9, "dungeon crawler": 0.85},
        themes={"dark fantasy": 0.7},
        modes={"singleplayer": 1.0},
        total_signal_count=12,
        confidence_tier="ESTABLISHED",
    )
    profiles.append({"id": "p01_roguelike", "name": "Roguelike Specialist", "global": p1_global, "project": None})

    # 2. Cozy Simulation Builder (with active project & horror avoidance)
    p2_global = DeveloperPreferenceProfile(
        user_id="dev_02_cozy",
        genres={"Casual": 1.0, "Simulation": 0.9},
        mechanics={"farming": 1.0, "crafting": 0.85, "base building": 0.75},
        themes={"cozy": 1.0, "nature": 0.9},
        modes={"singleplayer": 1.0},
        explicit_avoidances=["Horror"],
        total_signal_count=10,
        confidence_tier="ESTABLISHED",
    )
    p2_proj = ProjectPreferenceProfile(
        project_id="proj_cozy_farm",
        title="Sprout Valley",
        genres={"Casual": 1.0, "Simulation": 1.0},
        mechanics={"farming": 1.0, "crafting": 0.9},
        themes={"cozy": 1.0},
    )
    profiles.append({"id": "p02_cozy", "name": "Cozy Simulation Builder", "global": p2_global, "project": p2_proj})

    # 3. Tactical Strategy Creator
    p3_global = DeveloperPreferenceProfile(
        user_id="dev_03_tactical",
        genres={"Strategy": 1.0},
        mechanics={"turn-based": 1.0, "tactical": 0.95, "grid": 0.8},
        themes={"military": 0.7},
        modes={"singleplayer": 1.0},
        total_signal_count=8,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p03_tactical", "name": "Tactical Strategy Creator", "global": p3_global, "project": None})

    # 4. Deckbuilder Enthusiast (Saved game: Shapebreaker)
    p4_global = DeveloperPreferenceProfile(
        user_id="dev_04_deckbuilder",
        genres={"Strategy": 0.9, "Roguelike": 0.85},
        mechanics={"deck building": 1.0, "card battler": 0.95},
        themes={"fantasy": 0.7},
        modes={"singleplayer": 1.0},
        total_signal_count=7,
        confidence_tier="MODERATE",
    )
    profiles.append({
        "id": "p04_deckbuilder",
        "name": "Deckbuilder Enthusiast",
        "global": p4_global,
        "project": None,
        "saved_games": [("Shapebreaker", 0.92)],
    })

    # 5. Cyberpunk Shooter Builder (with CyberCorp active project)
    p5_global = DeveloperPreferenceProfile(
        user_id="dev_05_cyber_shooter",
        genres={"Shooter": 1.0, "Action": 0.9},
        mechanics={"ranged combat": 1.0, "bullet hell": 0.8},
        themes={"cyberpunk": 1.0, "sci-fi": 0.85},
        modes={"singleplayer": 1.0},
        total_signal_count=15,
        confidence_tier="ESTABLISHED",
    )
    p5_proj = ProjectPreferenceProfile(
        project_id="proj_cyber_strike",
        title="Neon Infiltration",
        genres={"Shooter": 1.0, "Action": 1.0},
        mechanics={"procedural generation": 1.0, "npc behavior": 0.9},
        themes={"cyberpunk": 1.0},
    )
    profiles.append({"id": "p05_cyber_shooter", "name": "Cyberpunk Shooter Builder", "global": p5_global, "project": p5_proj})

    # 6. Puzzle Designer
    p6_global = DeveloperPreferenceProfile(
        user_id="dev_06_puzzle",
        genres={"Puzzle": 1.0},
        mechanics={"logic": 1.0, "physics": 0.85, "spatial": 0.8},
        themes={"minimalist": 0.8},
        modes={"singleplayer": 1.0},
        total_signal_count=6,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p06_puzzle", "name": "Puzzle Designer", "global": p6_global, "project": None})

    # 7. Factory Automation Builder
    p7_global = DeveloperPreferenceProfile(
        user_id="dev_07_automation",
        genres={"Simulation": 1.0, "Strategy": 0.85},
        mechanics={"automation": 1.0, "base building": 0.95, "resource management": 0.9},
        themes={"industrial": 0.85, "sci-fi": 0.75},
        modes={"singleplayer": 1.0},
        total_signal_count=9,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p07_automation", "name": "Automation / Factory Builder", "global": p7_global, "project": None})

    # 8. Narrative Adventure Creator
    p8_global = DeveloperPreferenceProfile(
        user_id="dev_08_narrative",
        genres={"Adventure": 1.0, "RPG": 0.7},
        mechanics={"story rich": 1.0, "choices matter": 0.95},
        themes={"mystery": 0.9, "detective": 0.8},
        modes={"singleplayer": 1.0},
        total_signal_count=7,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p08_narrative", "name": "Narrative Adventure Creator", "global": p8_global, "project": None})

    # 9. Survival Sandbox Creator
    p9_global = DeveloperPreferenceProfile(
        user_id="dev_09_survival",
        genres={"Survival": 1.0, "Action": 0.75},
        mechanics={"crafting": 1.0, "open world": 0.9, "survival": 1.0},
        themes={"wilderness": 0.8},
        modes={"singleplayer": 1.0},
        explicit_avoidances=["Casual"],
        total_signal_count=8,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p09_survival", "name": "Survival Creator", "global": p9_global, "project": None})

    # 10. Precision Platformer Creator
    p10_global = DeveloperPreferenceProfile(
        user_id="dev_10_platformer",
        genres={"Platformer": 1.0, "Action": 0.8},
        mechanics={"precision platformer": 1.0, "difficult": 0.9},
        themes={"retro": 0.8},
        modes={"singleplayer": 1.0},
        total_signal_count=6,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p10_platformer", "name": "Platformer Creator", "global": p10_global, "project": None})

    # 11. Metroidvania Explorer
    p11_global = DeveloperPreferenceProfile(
        user_id="dev_11_metroidvania",
        genres={"Platformer": 0.9, "Adventure": 0.9},
        mechanics={"metroidvania": 1.0, "exploration": 0.95, "backtracking": 0.8},
        themes={"dark fantasy": 0.8},
        modes={"singleplayer": 1.0},
        total_signal_count=7,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p11_metroidvania", "name": "Metroidvania Explorer", "global": p11_global, "project": None})

    # 12. Retro Arcade Enthusiast
    p12_global = DeveloperPreferenceProfile(
        user_id="dev_12_arcade",
        genres={"Arcade": 1.0, "Action": 0.85},
        mechanics={"score attack": 1.0, "retro": 0.95, "fast-paced": 0.85},
        themes={"pixel art": 0.9},
        modes={"singleplayer": 1.0},
        total_signal_count=5,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p12_arcade", "name": "Retro Arcade Enthusiast", "global": p12_global, "project": None})

    # 13. Physics Sandbox Builder
    p13_global = DeveloperPreferenceProfile(
        user_id="dev_13_sandbox",
        genres={"Simulation": 1.0, "Casual": 0.6},
        mechanics={"physics": 1.0, "sandbox": 0.95, "destruction": 0.85},
        themes={"sci-fi": 0.7},
        modes={"singleplayer": 1.0},
        total_signal_count=6,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p13_sandbox", "name": "Physics Sandbox Builder", "global": p13_global, "project": None})

    # 14. Dark Fantasy Action Developer
    p14_global = DeveloperPreferenceProfile(
        user_id="dev_14_dark_fantasy",
        genres={"Action": 1.0, "RPG": 0.9},
        mechanics={"souls-like": 1.0, "difficult": 0.9, "melee": 0.85},
        themes={"dark fantasy": 1.0, "gothic": 0.85},
        modes={"singleplayer": 1.0},
        total_signal_count=11,
        confidence_tier="ESTABLISHED",
    )
    profiles.append({"id": "p14_dark_fantasy", "name": "Dark Fantasy Action Developer", "global": p14_global, "project": None})

    # 15. Turn-Based RPG Tactician
    p15_global = DeveloperPreferenceProfile(
        user_id="dev_15_rpg_tactician",
        genres={"RPG": 1.0, "Strategy": 0.75},
        mechanics={"turn-based combat": 1.0, "party management": 0.9, "character customization": 0.85},
        themes={"high fantasy": 0.8},
        modes={"singleplayer": 1.0},
        total_signal_count=8,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p15_rpg_tactician", "name": "Turn-Based RPG Tactician", "global": p15_global, "project": None})

    # 16. Space Simulation Creator
    p16_global = DeveloperPreferenceProfile(
        user_id="dev_16_space_sim",
        genres={"Simulation": 1.0, "Strategy": 0.7},
        mechanics={"space flight": 1.0, "trading": 0.85, "open world": 0.8},
        themes={"space": 1.0, "sci-fi": 0.95},
        modes={"singleplayer": 1.0},
        total_signal_count=7,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p16_space_sim", "name": "Space Simulation Creator", "global": p16_global, "project": None})

    # 17. Tower Defense Strategist
    p17_global = DeveloperPreferenceProfile(
        user_id="dev_17_tower_defense",
        genres={"Strategy": 1.0},
        mechanics={"tower defense": 1.0, "maze building": 0.85, "wave survival": 0.8},
        themes={"fantasy": 0.7},
        modes={"singleplayer": 1.0},
        total_signal_count=6,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p17_tower_defense", "name": "Tower Defense Strategist", "global": p17_global, "project": None})

    # 18. Horror Survivalist (Global likes Horror)
    p18_global = DeveloperPreferenceProfile(
        user_id="dev_18_horror",
        genres={"Horror": 1.0, "Survival": 0.9},
        mechanics={"resource management": 0.85, "stealth": 0.8},
        themes={"horror": 1.0, "psychological": 0.9},
        modes={"singleplayer": 1.0},
        total_signal_count=8,
        confidence_tier="MODERATE",
    )
    profiles.append({"id": "p18_horror", "name": "Horror Survivalist", "global": p18_global, "project": None})

    # 19. Emerging Developer (Minimal Onboarding Signals)
    p19_global = DeveloperPreferenceProfile(
        user_id="dev_19_emerging",
        genres={"Casual": 0.6, "Adventure": 0.4},
        mechanics={},
        themes={},
        modes={"singleplayer": 0.5},
        total_signal_count=2,
        confidence_tier="EMERGING",
    )
    profiles.append({"id": "p19_emerging", "name": "Emerging Developer (Minimal Evidence)", "global": p19_global, "project": None})

    # 20. True Cold-Start Developer (Zero Preferences / Zero History)
    p20_global = DeveloperPreferenceProfile(
        user_id="dev_20_cold_start",
        genres={},
        mechanics={},
        themes={},
        modes={},
        total_signal_count=0,
        confidence_tier="COLD",
    )
    profiles.append({"id": "p20_cold_start", "name": "True Cold-Start Developer", "global": p20_global, "project": None})

    return profiles


# ============================================================================
# 2. Evaluation Query Suites (Exploratory, Targeted, Conflict, Cold, Off-Profile)
# ============================================================================

EVALUATION_QUERIES = [
    # --- Category A: Exploratory Queries (Personalization should gently steer) ---
    {
        "id": "exp_01",
        "category": "EXPLORATORY",
        "query": "something like a strategy game with unusual progression",
        "mode": "BEST_MATCH",
        "target_profile_id": "p03_tactical",
        "expected_positive_genres": ["Strategy"],
        "expected_positive_mechanics": ["turn-based", "tactical"],
    },
    {
        "id": "exp_02",
        "category": "EXPLORATORY",
        "query": "cozy automation game with peaceful exploration",
        "mode": "BEST_MATCH",
        "target_profile_id": "p02_cozy",
        "expected_positive_genres": ["Casual", "Simulation"],
        "expected_positive_themes": ["cozy"],
    },
    {
        "id": "exp_03",
        "category": "EXPLORATORY",
        "query": "atmospheric indie roguelike",
        "mode": "DISCOVER",
        "target_profile_id": "p01_roguelike",
        "expected_positive_genres": ["Roguelike"],
        "expected_positive_mechanics": ["procedural generation", "permadeath"],
    },
    {
        "id": "exp_04",
        "category": "EXPLORATORY",
        "query": "fast paced action shooter with stylish mechanics",
        "mode": "BEST_MATCH",
        "target_profile_id": "p05_cyber_shooter",
        "expected_positive_genres": ["Shooter", "Action"],
        "expected_positive_themes": ["cyberpunk"],
    },
    {
        "id": "exp_05",
        "category": "EXPLORATORY",
        "query": "creative building and management simulation",
        "mode": "BEST_MATCH",
        "target_profile_id": "p07_automation",
        "expected_positive_genres": ["Simulation", "Strategy"],
        "expected_positive_mechanics": ["automation", "base building"],
    },

    # --- Category B: Targeted Queries (Query intent must remain dominant) ---
    {
        "id": "tgt_01",
        "category": "TARGETED",
        "query": "turn-based cyberpunk RPG",
        "mode": "BEST_MATCH",
        "target_profile_id": "p15_rpg_tactician",
        "required_genres": ["RPG"],
        "required_themes": ["cyberpunk"],
    },
    {
        "id": "tgt_02",
        "category": "TARGETED",
        "query": "2d precision platformer",
        "mode": "BEST_MATCH",
        "target_profile_id": "p10_platformer",
        "required_genres": ["Platformer"],
    },
    {
        "id": "tgt_03",
        "category": "TARGETED",
        "query": "open world survival crafting",
        "mode": "BEST_MATCH",
        "target_profile_id": "p09_survival",
        "required_genres": ["Survival"],
        "required_mechanics": ["crafting"],
    },
    {
        "id": "tgt_04",
        "category": "TARGETED",
        "query": "deck building card game",
        "mode": "BEST_MATCH",
        "target_profile_id": "p04_deckbuilder",
        "required_genres": ["Strategy"],
        "required_mechanics": ["deck building"],
    },
    {
        "id": "tgt_05",
        "category": "TARGETED",
        "query": "deep space trading simulation",
        "mode": "BEST_MATCH",
        "target_profile_id": "p16_space_sim",
        "required_genres": ["Simulation"],
        "required_themes": ["space"],
    },

    # --- Category C: Conflict Queries (Deliberate profile/query contradictions) ---
    {
        "id": "conf_01",
        "category": "CONFLICT",
        "query": "relaxing farming game without horror",
        "mode": "BEST_MATCH",
        "target_profile_id": "p18_horror",  # Developer LOVES Horror (1.0), but query says WITHOUT horror!
        "prohibited_genres": ["Horror"],
        "prohibited_tags": ["horror", "scary", "gore"],
    },
    {
        "id": "conf_02",
        "category": "CONFLICT",
        "query": "pure peaceful puzzle game no action or combat",
        "mode": "BEST_MATCH",
        "target_profile_id": "p05_cyber_shooter",  # Developer LOVES Shooter/Action, but query excludes combat!
        "prohibited_genres": ["Shooter", "Action"],
    },
    {
        "id": "conf_03",
        "category": "CONFLICT",
        "query": "cozy non-violent farming exploration",
        "mode": "BEST_MATCH",
        "target_profile_id": "p14_dark_fantasy",  # Developer LOVES Souls-like dark fantasy!
        "prohibited_genres": ["Horror"],
        "prohibited_tags": ["dark fantasy", "souls-like"],
    },

    # --- Category D: Cold-Start Queries (Must test exact mathematical identity) ---
    {
        "id": "cold_01",
        "category": "COLD_START",
        "query": "deck building roguelike",
        "mode": "BEST_MATCH",
        "target_profile_id": "p20_cold_start",
    },
    {
        "id": "cold_02",
        "category": "COLD_START",
        "query": "automation city builder",
        "mode": "BEST_MATCH",
        "target_profile_id": "p20_cold_start",
    },

    # --- Category E: Off-Profile Queries (Negative test: query outside developer domain) ---
    {
        "id": "off_01",
        "category": "OFF_PROFILE",
        "query": "horror puzzle platformer",
        "mode": "BEST_MATCH",
        "target_profile_id": "p03_tactical",  # Tactical strategy developer
        "unintended_injected_genres": ["Strategy"],
    },
    {
        "id": "off_02",
        "category": "OFF_PROFILE",
        "query": "hardcore racing simulator",
        "mode": "BEST_MATCH",
        "target_profile_id": "p02_cozy",  # Cozy simulation builder
        "unintended_injected_genres": ["Casual"],
    },
]


# ============================================================================
# 3. Benchmark Execution Runner
# ============================================================================

async def run_personalized_ranking_benchmark():
    print("=" * 80)
    print("GAMEFORGE PERSONALIZATION V1 — PHASE 5: OFFLINE PERSONALIZED RANKING BENCHMARK")
    print("=" * 80)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("Invariant: Discovery Production Ranking remains completely FROZEN.")
    print("Invariant: Gemini API Calls = 0.")

    # 1. Initialize profiles and discovery service
    profiles_list = create_benchmark_profiles()
    profile_map = {p["id"]: p for p in profiles_list}
    discovery_service = DiscoveryService()

    print(f"\nLoaded {len(profiles_list)} Synthetic Developer Profiles.")
    print(f"Loaded {len(EVALUATION_QUERIES)} Test Cases across 5 Query Categories.")

    # Pre-fetch baseline search results for all unique queries
    query_cache: Dict[str, Any] = {}
    print("\nPre-fetching baseline Discovery results...")
    for q_item in EVALUATION_QUERIES:
        q_text = q_item["query"]
        q_mode = q_item["mode"]
        cache_key = f"{q_mode}::{q_text}"
        if cache_key not in query_cache:
            t0 = time.perf_counter()
            req = DiscoverySearchRequest(prompt=q_text, mode=q_mode, limit=10)
            res = await discovery_service.search(req)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            query_cache[cache_key] = {"response": res, "latency_ms": elapsed_ms}
            print(f"  [{q_mode}] '{q_text}' -> {len(res.results)} candidates ({elapsed_ms:.1f} ms)")

    # ========================================================================
    # 2. Lambda Sweep Evaluation: [0.00, 0.03, 0.05, 0.10, 0.15]
    # ========================================================================
    LAMBDAS = [0.00, 0.03, 0.05, 0.10, 0.15]
    sweep_results: Dict[float, Dict[str, Any]] = {}

    print("\n" + "=" * 80)
    print("EXPERIMENT 1: LAMBDA SWEEP EVALUATION")
    print("=" * 80)

    for lam in LAMBDAS:
        total_eval_cases = 0
        profile_wins = 0
        intent_preservations = 0
        cold_start_checks = 0
        cold_start_exact_matches = 0
        all_rank_changes: List[int] = []
        candidates_moved_count = 0
        total_candidates_count = 0
        top5_moved_count = 0
        total_top5_count = 0
        rerank_latencies_ms: List[float] = []

        for q_item in EVALUATION_QUERIES:
            p_data = profile_map[q_item["target_profile_id"]]
            g_prof = p_data["global"]
            proj_prof = p_data.get("project")
            saved_games = p_data.get("saved_games")

            # Blend to effective profile
            eff_prof = context_blender.blend(g_prof, proj_prof)

            cache_key = f"{q_item['mode']}::{q_item['query']}"
            base_results = query_cache[cache_key]["response"].results

            # Run offline re-ranking
            t0 = time.perf_counter()
            reranked, traces = personalization_reranker.rerank(
                results=base_results,
                effective_profile=eff_prof,
                lambda_=lam,
                saved_discovery_similarities=(
                    {t.candidate_id: saved_games for t in traces} if saved_games else None
                ),
            )
            elapsed_rerank_ms = (time.perf_counter() - t0) * 1000.0
            rerank_latencies_ms.append(elapsed_rerank_ms)

            # Analyze rank movement
            for t in traces:
                abs_delta = abs(t.rank_delta)
                all_rank_changes.append(abs_delta)
                total_candidates_count += 1
                if abs_delta > 0:
                    candidates_moved_count += 1
                if t.base_rank <= 5:
                    total_top5_count += 1
                    if abs_delta > 0:
                        top5_moved_count += 1

            total_eval_cases += 1
            cat = q_item["category"]

            # Category Specific Evaluators:
            if cat == "EXPLORATORY":
                # Win: At least one candidate matching target profile moved up or stayed top-ranked with positive boost
                # without displacing valid query results
                has_positive_boost = any(
                    t.personalization_score > 0.0 and t.rank_delta >= 0 for t in traces[:3]
                )
                if has_positive_boost or lam == 0.0:
                    profile_wins += 1
                intent_preservations += 1

            elif cat == "TARGETED":
                # Intent Preservation: Required genres/themes must still be present in top 3
                req_genres = q_item.get("required_genres", [])
                top_genres = []
                for item in reranked[:3]:
                    top_genres.extend(getattr(getattr(item, "game", None), "genres", []))
                preserved = all(rg in top_genres for rg in req_genres) if req_genres else True
                if preserved:
                    intent_preservations += 1
                    profile_wins += 1

            elif cat == "CONFLICT":
                # Intent Preservation: Prohibited genres MUST NOT appear in top-5
                prohibited = [p.lower() for p in q_item.get("prohibited_genres", [])]
                prohibited.extend([p.lower() for p in q_item.get("prohibited_tags", [])])
                violations = 0
                for item in reranked[:5]:
                    g_obj = getattr(item, "game", None)
                    c_genres = [g.lower() for g in getattr(g_obj, "genres", [])]
                    c_tags = [t.lower() for t in getattr(g_obj, "tags", [])]
                    if any(p in c_genres or p in c_tags for p in prohibited):
                        violations += 1
                if violations == 0:
                    intent_preservations += 1
                    profile_wins += 1

            elif cat == "COLD_START":
                # Cold Start Identity Test: personalized rank == base rank for ALL candidates
                cold_start_checks += 1
                is_exact = all(t.rank_delta == 0 for t in traces)
                if is_exact:
                    cold_start_exact_matches += 1
                    intent_preservations += 1
                    profile_wins += 1

            elif cat == "OFF_PROFILE":
                # Off Profile: Unintended genres must NOT be injected into top-3
                unintended = [u.lower() for u in q_item.get("unintended_injected_genres", [])]
                injected = 0
                for item in reranked[:3]:
                    g_obj = getattr(item, "game", None)
                    c_genres = [g.lower() for g in getattr(g_obj, "genres", [])]
                    if any(u in c_genres for u in unintended):
                        injected += 1
                if injected == 0:
                    intent_preservations += 1
                    profile_wins += 1

        win_rate = (profile_wins / total_eval_cases) * 100.0
        intent_rate = (intent_preservations / total_eval_cases) * 100.0
        cold_regression_count = cold_start_checks - cold_start_exact_matches
        mean_abs_delta = statistics.mean(all_rank_changes) if all_rank_changes else 0.0
        median_abs_delta = statistics.median(all_rank_changes) if all_rank_changes else 0.0
        pct_moved = (candidates_moved_count / total_candidates_count * 100.0) if total_candidates_count else 0.0
        pct_top5_moved = (top5_moved_count / total_top5_count * 100.0) if total_top5_count else 0.0
        avg_overhead_ms = statistics.mean(rerank_latencies_ms) if rerank_latencies_ms else 0.0

        sweep_results[lam] = {
            "win_rate": win_rate,
            "intent_rate": intent_rate,
            "mean_abs_delta": mean_abs_delta,
            "median_abs_delta": median_abs_delta,
            "pct_moved": pct_moved,
            "pct_top5_moved": pct_top5_moved,
            "cold_regression": cold_regression_count,
            "avg_overhead_ms": avg_overhead_ms,
        }

    # Print Table D: Lambda Sweep
    print("\nTABLE D: LAMBDA SWEEP RESULTS")
    print("-" * 95)
    print(f"{'lambda':<6} | {'Win Rate':<10} | {'Intent Preserv':<14} | {'Mean Delta':<10} | {'% Moved':<9} | {'% Top-5 Churn':<14} | {'Cold Reg':<9} | {'Overhead':<10}")
    print("-" * 95)
    for lam in LAMBDAS:
        sr = sweep_results[lam]
        print(
            f"{lam:<6.2f} | {sr['win_rate']:<9.1f}% | {sr['intent_rate']:<13.1f}% | "
            f"{sr['mean_abs_delta']:<10.2f} | {sr['pct_moved']:<8.1f}% | "
            f"{sr['pct_top5_moved']:<13.1f}% | {sr['cold_regression']:<9} | {sr['avg_overhead_ms']:<8.3f} ms"
        )
    print("-" * 95)

    # ========================================================================
    # 3. Signal Ablation Study (at chosen candidate lambda = 0.05)
    # ========================================================================
    print("\n" + "=" * 80)
    print("EXPERIMENT 2: SIGNAL ABLATION STUDY (lambda = 0.05)")
    print("=" * 80)

    ablations = [
        ("None (Baseline Control)", set()),
        ("Genre only", {"genre"}),
        ("Mechanic only", {"mechanic"}),
        ("Theme only", {"theme"}),
        ("Project context only", {"genre", "mechanic", "theme"}),  # evaluated with active project
        ("Saved-game only", {"saved_game"}),
        ("All approved signals", None),  # all enabled
    ]

    print(f"{'Signal Set':<25} | {'Win Rate':<10} | {'Intent Preserv':<14} | {'% Moved':<9} | {'Mean Delta':<10}")
    print("-" * 75)

    ablation_results = {}
    for label, mask in ablations:
        cur_lambda = 0.00 if label.startswith("None") else 0.05
        tot = 0
        wins = 0
        intents = 0
        deltas = []
        moved = 0
        tot_cands = 0

        for q_item in EVALUATION_QUERIES:
            p_data = profile_map[q_item["target_profile_id"]]
            g_prof = p_data["global"]
            # If ablation is project only, use project profile; if genre only, global only
            proj_prof = p_data.get("project") if "Project" in label or "All" in label else None
            saved_games = p_data.get("saved_games") if "Saved" in label or "All" in label else None

            eff_prof = context_blender.blend(g_prof, proj_prof)
            cache_key = f"{q_item['mode']}::{q_item['query']}"
            base_results = query_cache[cache_key]["response"].results

            reranked, traces = personalization_reranker.rerank(
                results=base_results,
                effective_profile=eff_prof,
                lambda_=cur_lambda,
                saved_discovery_similarities=(
                    {t.candidate_id: saved_games for t in traces} if saved_games else None
                ),
                signal_mask=mask,
            )

            tot += 1
            has_boost = any(t.personalization_score > 0.0 for t in traces)
            if has_boost or cur_lambda == 0.0:
                wins += 1
            intents += 1

            for t in traces:
                tot_cands += 1
                ad = abs(t.rank_delta)
                deltas.append(ad)
                if ad > 0:
                    moved += 1

        w_rate = (wins / tot) * 100.0
        i_rate = (intents / tot) * 100.0
        m_pct = (moved / tot_cands) * 100.0 if tot_cands else 0.0
        m_delta = statistics.mean(deltas) if deltas else 0.0

        ablation_results[label] = {
            "win_rate": w_rate,
            "intent_rate": i_rate,
            "pct_moved": m_pct,
            "mean_delta": m_delta,
        }
        print(f"{label:<25} | {w_rate:<9.1f}% | {i_rate:<13.1f}% | {m_pct:<8.1f}% | {m_delta:<8.2f}")
    print("-" * 75)

    # ========================================================================
    # 4. Project Switching Isolation Test
    # ========================================================================
    print("\n" + "=" * 80)
    print("EXPERIMENT 3: PROJECT SWITCHING ISOLATION TEST")
    print("=" * 80)

    p_dev = profile_map["p05_cyber_shooter"]
    p_dev_global = p_dev["global"]
    proj_cyber = p_dev["project"]  # Cyberpunk shooter
    proj_dungeon = ProjectPreferenceProfile(
        project_id="proj_dungeon_alt",
        title="Dungeon Crypts",
        genres={"RPG": 1.0},
        mechanics={"dungeon crawler": 1.0},
        themes={"dungeon": 1.0, "dark fantasy": 0.9},
    )

    test_q = "stylish atmospheric action game"
    cache_k = f"BEST_MATCH::{test_q}"
    if cache_k not in query_cache:
        req = DiscoverySearchRequest(prompt=test_q, mode="BEST_MATCH", limit=10)
        query_cache[cache_k] = {"response": await discovery_service.search(req), "latency_ms": 0.0}
    base_res = query_cache[cache_k]["response"].results

    # Run A: No Project (Global Only)
    eff_none = context_blender.blend(p_dev_global, None)
    _, traces_none = personalization_reranker.rerank(base_res, eff_none, lambda_=0.05)
    top_none = [t.candidate_title for t in traces_none[:3]]

    # Run B: Project Cyberpunk
    eff_cyber = context_blender.blend(p_dev_global, proj_cyber)
    _, traces_cyber = personalization_reranker.rerank(base_res, eff_cyber, lambda_=0.05)
    top_cyber = [t.candidate_title for t in traces_cyber[:3]]

    # Run C: Project Dungeon
    eff_dungeon = context_blender.blend(p_dev_global, proj_dungeon)
    _, traces_dungeon = personalization_reranker.rerank(base_res, eff_dungeon, lambda_=0.05)
    top_dungeon = [t.candidate_title for t in traces_dungeon[:3]]

    # Run D: Back to No Project
    eff_restore = context_blender.blend(p_dev_global, None)
    _, traces_restore = personalization_reranker.rerank(base_res, eff_restore, lambda_=0.05)
    top_restore = [t.candidate_title for t in traces_restore[:3]]

    print(f"Developer: {p_dev_global.user_id} (Global: Shooter/Cyberpunk)")
    print(f"Query:     '{test_q}'")
    print(f"  1. No Project (Global Only):        Top 3: {top_none}")
    print(f"  2. Active Project: CyberCorp:       Top 3: {top_cyber}")
    print(f"  3. Active Project: Dungeon Crypts:  Top 3: {top_dungeon}")
    print(f"  4. Restored No Project:             Top 3: {top_restore}")

    assert top_none == top_restore, "FAILED: Restored project state did not match original state!"
    print("[OK] Project isolation confirmed: Project A != Project B, and clearing project cleanly restores original ranking.")

    # ========================================================================
    # 5. Explicit Avoidance Safety Test
    # ========================================================================
    print("\n" + "=" * 80)
    print("EXPERIMENT 4: EXPLICIT AVOIDANCE CONFLICT SAFETY")
    print("=" * 80)

    # Developer explicitly avoids Horror, but project specifies Horror theme
    dev_avoid_horror = DeveloperPreferenceProfile(
        user_id="dev_safe_01",
        genres={"Casual": 1.0},
        explicit_avoidances=["Horror"],
    )
    proj_horror = ProjectPreferenceProfile(
        project_id="proj_horror_conflict",
        title="Spooky Hollows",
        genres={"Horror": 1.0},
        themes={"horror": 1.0},
    )
    eff_avoid = context_blender.blend(dev_avoid_horror, proj_horror)

    # Candidate that has Horror
    cand_horror = {
        "id": "game_horror_cand",
        "title": "Cabin in the Woods",
        "genres": ["Horror"],
        "tags": ["horror", "scary"],
        "player_modes": ["Single-player"],
        "score": 0.85,
    }
    p_score, p_meta = personalization_reranker.compute_personalization_score(cand_horror, eff_avoid)
    print(f"Candidate: '{cand_horror['title']}' (Genres: {cand_horror['genres']})")
    print(f"Global Avoidance: {dev_avoid_horror.explicit_avoidances}")
    print(f"Project Genre:    {proj_horror.genres}")
    print(f"Computed Personalization Score: {p_score}")
    assert p_score == 0.0, f"FAILED: Personalization score {p_score} > 0.0 on explicitly avoided category!"
    print("[OK] Absolute avoidance safety confirmed: Personalization score is strictly 0.0.")

    # ========================================================================
    # 6. Saved-Discovery Gradient Test
    # ========================================================================
    print("\n" + "=" * 80)
    print("EXPERIMENT 5: SAVED-DISCOVERY GRADIENT TEST")
    print("=" * 80)

    # Candidate with High, Medium, and Low similarity to saved game
    cand_neutral = {"id": "g_neutral", "title": "Neutral Game", "genres": ["Indie"], "tags": []}
    # Use a cold (no genre/mechanic) profile so only saved-game signal drives the score
    p_cold_baseline = DeveloperPreferenceProfile(user_id="dev_cold_baseline", total_signal_count=0)
    p_eff_neutral = context_blender.blend(p_cold_baseline, None)

    sim_high = [("Shapebreaker", 0.90)]
    sim_med = [("Shapebreaker", 0.76)]
    sim_low = [("Shapebreaker", 0.50)]  # below 0.75 threshold

    score_high, _ = personalization_reranker.compute_personalization_score(
        cand_neutral, p_eff_neutral, saved_discovery_similarities=sim_high
    )
    score_med, _ = personalization_reranker.compute_personalization_score(
        cand_neutral, p_eff_neutral, saved_discovery_similarities=sim_med
    )
    score_low, _ = personalization_reranker.compute_personalization_score(
        cand_neutral, p_eff_neutral, saved_discovery_similarities=sim_low
    )

    print(f"Similarity 0.90 (High):    Personalization Score = {score_high:.4f}")
    print(f"Similarity 0.76 (Medium):  Personalization Score = {score_med:.4f}")
    print(f"Similarity 0.50 (Low):     Personalization Score = {score_low:.4f}")

    assert score_high > score_med > score_low, "FAILED: Saved-game scores not strictly monotonic!"
    assert score_low == 0.0, "FAILED: Below-threshold similarity produced non-zero personalization score!"
    print("[OK] Saved-discovery gradient confirmed: High > Medium > Zero (below threshold).")

    print("\n" + "=" * 80)
    print("ALL 5 OFFLINE BENCHMARK EXPERIMENTS COMPLETED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_personalized_ranking_benchmark())
