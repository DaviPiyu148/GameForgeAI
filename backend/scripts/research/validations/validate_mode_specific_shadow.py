"""
GameForge Personalization V1 — Phase 6.3: Real-Query Shadow Validation with Mode-Specific Lambdas
=================================================================================================
Validates the mode-specific personalization policy on real database traffic in SHADOW mode:
  DISCOVER:     λ = 0.05
  HIDDEN_GEMS:  λ = 0.05
  BEST_MATCH:   λ = 0.02
  POPULAR:      λ = 0.00

Evaluates:
- 220 total real shadow requests across 4 Discovery modes (55 per mode)
- 4 profile maturity tiers (COLD, EMERGING, MODERATE, ESTABLISHED)
- Project context segmentation (with vs without active project)
- Shadow response identity invariant (HTTP response == base response)
- POPULAR λ=0.00 exact base ranking invariant (0 churn, 0 movement, 0 PAU loss)
- BEST_MATCH λ=0.02 reduction in churn & harmful slot changes
- Real contrasting project-context switching sequence (No Project -> A -> B -> No Project)
- Grounded explanation consistency
- Direct comparison against Phase 6.1 (global λ=0.05)
- Safety invariants (0 constraint violations, 0 avoidance violations, 0 cold regressions, 0 fallbacks)
- Latency per mode (< 50ms budget)
"""

import asyncio
import math
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.config import settings
from app.db.session import SessionLocal
from app.models.project import Project
from app.models.user import User
from app.schemas.discovery import DiscoverySearchRequest, DiscoverySearchResponse
from app.services.context_blender import context_blender
from app.services.discovery_service import discovery_service
from app.services.personalization_experiment import (
    ExperimentDiagnostics,
    PERSONALIZATION_MODE_SHADOW,
    personalization_experiment_service,
)
from app.services.personalization_explanation_service import PersonalizationExplanationService
from app.services.preference_aggregator import preference_aggregator

# ---------------------------------------------------------------------------
# Phase 6.3 Policy Definition
# ---------------------------------------------------------------------------
PHASE_6_3_POLICY: Dict[str, float] = {
    "DISCOVER": 0.05,
    "HIDDEN_GEMS": 0.05,
    "BEST_MATCH": 0.02,
    "POPULAR": 0.00,
}

# ---------------------------------------------------------------------------
# Phase 6.1 Historical Baselines (for direct comparison)
# ---------------------------------------------------------------------------
PHASE_6_1_METRICS = {
    "BEST_MATCH": {
        "lambda": 0.05,
        "pau": 0.0168,
        "beneficial_pct": 50.0,
        "harmful_pct": 30.0,
        "top5_churn": 0.30,
        "reqs": 50,
    },
    "POPULAR": {
        "lambda": 0.05,
        "pau": 0.0136,
        "beneficial_pct": 40.0,
        "harmful_pct": 23.3,
        "top5_churn": 0.36,
        "reqs": 25,
    },
    "DISCOVER": {
        "lambda": 0.05,
        "pau": 0.0287,
        "beneficial_pct": 51.8,
        "harmful_pct": 25.0,
        "top5_churn": 0.66,
        "reqs": 35,
    },
    "HIDDEN_GEMS": {
        "lambda": 0.05,
        "pau": 0.0272,
        "beneficial_pct": 45.7,
        "harmful_pct": 17.4,
        "top5_churn": 0.53,
        "reqs": 30,
    },
}

# ---------------------------------------------------------------------------
# Authentic Real Queries (11 queries per mode = 44 queries total)
# ---------------------------------------------------------------------------
AUTHENTIC_QUERIES: List[Tuple[str, str]] = [
    # 1. BEST_MATCH (11 queries)
    ("cozy automation game with peaceful exploration", "BEST_MATCH"),
    ("deck building roguelike with unusual progression", "BEST_MATCH"),
    ("fast paced cyberpunk action shooter", "BEST_MATCH"),
    ("creative management and city builder simulation", "BEST_MATCH"),
    ("2d precision platformer with tight controls", "BEST_MATCH"),
    ("deep space trading and resource economy simulation", "BEST_MATCH"),
    ("turn-based tactical strategy with grid combat", "BEST_MATCH"),
    ("hardcore survival crafting with open world", "BEST_MATCH"),
    ("tactical dungeon crawler rpg with party mechanics", "BEST_MATCH"),
    ("Slay the Spire", "BEST_MATCH"),
    ("Factorio", "BEST_MATCH"),

    # 2. POPULAR (11 queries)
    ("top rated sci-fi open world role playing game", "POPULAR"),
    ("popular multiplayer survival crafting", "POPULAR"),
    ("acclaimed competitive strategy deckbuilder", "POPULAR"),
    ("classic precision platformer masterpiece", "POPULAR"),
    ("iconic post-apocalyptic role playing game", "POPULAR"),
    ("best competitive multiplayer shooter", "POPULAR"),
    ("highest rated dark fantasy action rpg", "POPULAR"),
    ("popular indie simulation and farming", "POPULAR"),
    ("beloved space exploration sandbox game", "POPULAR"),
    ("top rated turn based tactical game", "POPULAR"),
    ("acclaimed story driven atmospheric mystery", "POPULAR"),

    # 3. DISCOVER (11 queries)
    ("atmospheric indie roguelike with dark fantasy mood", "DISCOVER"),
    ("stylish combat shooter with neon aesthetics", "DISCOVER"),
    ("minimalist automation puzzle without timers", "DISCOVER"),
    ("relaxing farming exploration without horror", "DISCOVER"),
    ("inventive physics platformer with grappling mechanics", "DISCOVER"),
    ("narrative-driven detective mystery in dystopian city", "DISCOVER"),
    ("retro pixel-art dungeon crawler with stealth elements", "DISCOVER"),
    ("procedural survival game with emergent weather", "DISCOVER"),
    ("tactical espionage and stealth simulation", "DISCOVER"),
    ("chill underwater exploration adventure", "DISCOVER"),
    ("surreal psychological puzzle exploration", "DISCOVER"),

    # 4. HIDDEN_GEMS (11 queries)
    ("underappreciated tactical roguelite card game", "HIDDEN_GEMS"),
    ("obscure atmospheric puzzle adventure", "HIDDEN_GEMS"),
    ("innovative 2d physics construction game", "HIDDEN_GEMS"),
    ("peaceful indie automation and logistics", "HIDDEN_GEMS"),
    ("cyberpunk hacking simulation with terminal interface", "HIDDEN_GEMS"),
    ("isometric dark fantasy action rpg", "HIDDEN_GEMS"),
    ("underrated space trader and bounty hunter", "HIDDEN_GEMS"),
    ("unexplored cozy crafting and gathering simulator", "HIDDEN_GEMS"),
    ("overlooked turn based grid tactical battler", "HIDDEN_GEMS"),
    ("experimental minimalist roguelike with unique mechanics", "HIDDEN_GEMS"),
    ("low review count deep strategy builder", "HIDDEN_GEMS"),
]


def ascii_safe(text: str) -> str:
    """Sanitize strings for Windows console printing."""
    return "".join(c if ord(c) < 128 else "?" for c in text)


def compute_percentile(values: List[float], p: float) -> float:
    """Compute empirical percentile."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1
    if c < len(sorted_v):
        return sorted_v[f] + (k - f) * (sorted_v[c] - sorted_v[f])
    return sorted_v[f]


async def run_phase_6_3_validation():
    print("=" * 80)
    print("GAMEFORGE PERSONALIZATION V1 — PHASE 6.3: REAL-QUERY SHADOW VALIDATION")
    print("WITH MODE-SPECIFIC LAMBDAS")
    print("=" * 80)
    print(f"Timestamp:                    {datetime.now(timezone.utc).isoformat()}")
    print(f"PERSONALIZATION_MODE:         {settings.PERSONALIZATION_MODE} (Observation Only)")
    print(f"PERSONALIZATION_TREATMENT_PCT:{settings.PERSONALIZATION_TREATMENT_PCT}%")
    print(f"LATENCY_BUDGET_MS:            {settings.PERSONALIZATION_LATENCY_BUDGET_MS} ms")
    print("MODE-SPECIFIC SHADOW POLICY:")
    for m, l in PHASE_6_3_POLICY.items():
        print(f"  {m:<14} -> λ = {l:.2f}")
    print("=" * 80)

    db = SessionLocal()

    # 1. Load real DB personas
    user_cold = db.query(User).filter(User.username == "testuser_browser2").first()
    user_emerging = db.query(User).filter(User.username == "DevAdmin").first()
    user_moderate = db.query(User).filter(User.username == "testuser").first()
    user_established_1 = db.query(User).filter(User.username == "audituser").first()
    user_established_2 = db.query(User).filter(User.username == "testuser_browser1").first()

    assert user_cold, "User 'testuser_browser2' must exist in DB"
    assert user_emerging, "User 'DevAdmin' must exist in DB"
    assert user_moderate, "User 'testuser' must exist in DB"
    assert user_established_1, "User 'audituser' must exist in DB"
    assert user_established_2, "User 'testuser_browser1' must exist in DB"

    projects_user2 = db.query(Project).filter(Project.user_id == user_established_2.id).all()
    project_cyber = next((p for p in projects_user2 if "Neon" in p.title or "Cyber" in p.title), None)
    project_void = next((p for p in projects_user2 if "Void" in p.title), None)

    print("\n[Loaded Real Database Test Personas]")
    personas = [
        ("COLD", user_cold, None),
        ("EMERGING", user_emerging, None),
        ("MODERATE", user_moderate, None),
        ("ESTABLISHED", user_established_1, None),
        ("ESTABLISHED_PROJECT", user_established_2, project_cyber.id if project_cyber else None),
    ]

    for label, u, proj_id in personas:
        p = preference_aggregator.build_profile(db, str(u.id))
        proj_str = f"Project: {proj_id[:8]}..." if proj_id else "No Project"
        print(f"  {label:<20} | User: {u.username:<18} (ID: {u.id[:8]}...) | Tier: {p.confidence_tier:<12} | Signals: {p.total_signal_count:>2} | {proj_str}")

    # 2. Warm up discovery service
    print("\nWarming Discovery service...")
    t_warm = time.perf_counter()
    discovery_service.warm()
    print(f"Discovery service warmed in {(time.perf_counter() - t_warm):.2f}s.")

    # 3. Build evaluation matrix: 44 queries x 5 personas = 220 requests
    test_runs = []
    for query_text, mode in AUTHENTIC_QUERIES:
        for label, u, proj_id in personas:
            test_runs.append({
                "user": u,
                "profile_label": label,
                "query": query_text,
                "mode": mode,
                "project_id": proj_id,
            })

    total_requests = len(test_runs)
    print(f"\nBuilt evaluation matrix: {total_requests} real shadow requests (Target: >= 200).")
    print(f"  BEST_MATCH:   {sum(1 for r in test_runs if r['mode'] == 'BEST_MATCH')} requests (25.0%)")
    print(f"  POPULAR:      {sum(1 for r in test_runs if r['mode'] == 'POPULAR')} requests (25.0%)")
    print(f"  DISCOVER:     {sum(1 for r in test_runs if r['mode'] == 'DISCOVER')} requests (25.0%)")
    print(f"  HIDDEN_GEMS:  {sum(1 for r in test_runs if r['mode'] == 'HIDDEN_GEMS')} requests (25.0%)")

    # 4. Execute Real Shadow Runs
    print("\n" + "=" * 80)
    print("1. EXECUTING REAL-QUERY SHADOW EVALUATION MATRIX (220 REQUESTS)")
    print("=" * 80)

    # Pre-fetch base search responses to minimize FAISS cache noise
    unique_queries = list({(r["query"], r["mode"]) for r in test_runs})
    base_cache: Dict[Tuple[str, str], DiscoverySearchResponse] = {}
    base_latencies: Dict[Tuple[str, str], float] = {}

    print(f"Pre-fetching {len(unique_queries)} base search responses across 4 modes...")
    t_base_start = time.perf_counter()
    for q_text, q_mode in unique_queries:
        req = DiscoverySearchRequest(prompt=q_text, mode=q_mode, limit=10)
        t0 = time.perf_counter()
        resp = await discovery_service.search(req)
        dt = (time.perf_counter() - t0) * 1000.0
        base_cache[(q_text, q_mode)] = resp
        base_latencies[(q_text, q_mode)] = dt
    print(f"Pre-fetched {len(unique_queries)} base responses in {(time.perf_counter() - t_base_start):.2f}s.\n")

    records: List[Dict[str, Any]] = []
    mode_counts: Dict[str, int] = {m: 0 for m in PHASE_6_3_POLICY}

    # Safety tracking counters
    shadow_identity_violations = 0
    lambda_selection_mismatches = 0
    popular_movement_violations = 0
    cold_start_violations = 0
    hard_constraint_violations = 0
    explicit_avoidance_violations = 0
    safety_fallbacks = 0
    no_evidence_personalization_runs = 0

    for i, run in enumerate(test_runs):
        user = run["user"]
        label = run["profile_label"]
        query_text = run["query"]
        mode = run["mode"]
        project_id = run["project_id"]

        mode_counts[mode] += 1
        base_resp = base_cache[(query_text, mode)]
        base_lat = base_latencies[(query_text, mode)]

        # Build user profile
        global_profile = preference_aggregator.build_profile(db, str(user.id))

        # Build optional project profile
        project_profile = None
        if project_id:
            try:
                project_profile = context_blender.build_project_profile(project=project_id, db=db)
            except Exception:
                project_profile = None

        effective_profile = context_blender.blend(global_profile, project_profile)

        # Apply experiment service in SHADOW mode with Phase 6.3 mode lambdas
        shadow_resp, diag = personalization_experiment_service.apply(
            base_response=base_resp,
            effective_profile=effective_profile,
            user_id=str(user.id),
            mode=PERSONALIZATION_MODE_SHADOW,
            mode_lambdas=PHASE_6_3_POLICY,
            latency_budget_ms=settings.PERSONALIZATION_LATENCY_BUDGET_MS,
        )
        diag.base_latency_ms = base_lat
        diag.total_latency_ms = base_lat + diag.personalization_latency_ms

        # ── ASSERTION 1: Lambda Selection Verification ─────────────────────
        expected_lambda = PHASE_6_3_POLICY[mode]
        if diag.lambda_ != expected_lambda or diag.discovery_mode != mode:
            lambda_selection_mismatches += 1

        # ── ASSERTION 2: Shadow Response Identity ──────────────────────────
        # In SHADOW mode, the public response must be 100% identical to base response
        base_ids = [r.game.id for r in base_resp.results]
        shadow_ids = [r.game.id for r in shadow_resp.results]
        if base_ids != shadow_ids or [r.score for r in base_resp.results] != [r.score for r in shadow_resp.results]:
            shadow_identity_violations += 1

        # ── ASSERTION 3: POPULAR Mode Invariant (λ = 0.00) ─────────────────
        if mode == "POPULAR":
            if (
                diag.top5_churn != 0
                or diag.top10_churn != 0
                or diag.candidates_moved != 0
                or diag.preference_alignment_uplift != 0.0
            ):
                popular_movement_violations += 1

        # ── ASSERTION 4: COLD Tier Invariant ───────────────────────────────
        if label == "COLD":
            if (
                diag.top5_churn != 0
                or diag.top10_churn != 0
                or diag.candidates_moved != 0
                or diag.preference_alignment_uplift != 0.0
            ):
                cold_start_violations += 1

        # ── ASSERTION 5: Safety Fallbacks & Constraint Violations ──────────
        if diag.safety_fallback_triggered:
            safety_fallbacks += 1
        if diag.intent_violations > 0:
            hard_constraint_violations += diag.intent_violations
        if diag.avoidance_violations > 0:
            explicit_avoidance_violations += diag.avoidance_violations
        if diag.no_evidence_personalization:
            no_evidence_personalization_runs += 1

        records.append({
            "run_index": i,
            "mode": mode,
            "selected_lambda": diag.lambda_,
            "configured_mode_lambdas": diag.configured_mode_lambdas,
            "profile_label": label,
            "profile_tier": diag.profile_confidence_tier,
            "has_project": diag.active_project,
            "pau": diag.preference_alignment_uplift,
            "beneficial": diag.beneficial_changes,
            "neutral": diag.neutral_changes,
            "harmful": diag.harmful_changes,
            "top5_churn": diag.top5_churn,
            "top10_churn": diag.top10_churn,
            "mean_abs_rank_delta": diag.mean_abs_rank_delta,
            "max_rank_delta": diag.max_rank_delta,
            "candidates_moved": diag.candidates_moved,
            "pers_latency_ms": diag.personalization_latency_ms,
            "base_latency_ms": diag.base_latency_ms,
            "total_latency_ms": diag.total_latency_ms,
        })

    print(f"Executed {len(records)} requests successfully.")
    print(f"  Shadow Identity Violations:     {shadow_identity_violations} (REQUIRED: 0)")
    print(f"  Lambda Selection Mismatches:    {lambda_selection_mismatches} (REQUIRED: 0)")
    print(f"  POPULAR Movement Violations:    {popular_movement_violations} (REQUIRED: 0)")
    print(f"  Cold-Start Invariant Failures:  {cold_start_violations} (REQUIRED: 0)")
    print(f"  Safety Fallbacks Triggered:     {safety_fallbacks} (REQUIRED: 0)")
    print(f"  Hard Constraint Violations:     {hard_constraint_violations} (REQUIRED: 0)")
    print(f"  Explicit Avoidance Violations:  {explicit_avoidance_violations} (REQUIRED: 0)")
    print(f"  No-Evidence Personalization:    {no_evidence_personalization_runs} (REQUIRED: 0)")

    assert shadow_identity_violations == 0, "Shadow response must be 100% identical to base response!"
    assert lambda_selection_mismatches == 0, "Selected lambda must match mode policy exactly!"
    assert popular_movement_violations == 0, "POPULAR mode must have zero churn and zero PAU loss!"
    assert cold_start_violations == 0, "COLD tier must produce exact base identity!"

    # ------------------------------------------------------------------------
    # 2. Mode Analysis & Detailed Metrics
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("2. MODE BREAKDOWN & METRICS (PHASE 6.3)")
    print("=" * 80)

    mode_metrics: Dict[str, Dict[str, Any]] = {}
    for m in ["DISCOVER", "HIDDEN_GEMS", "BEST_MATCH", "POPULAR"]:
        m_recs = [r for r in records if r["mode"] == m]
        pau_vals = [r["pau"] for r in m_recs]
        b_sum = sum(r["beneficial"] for r in m_recs)
        n_sum = sum(r["neutral"] for r in m_recs)
        h_sum = sum(r["harmful"] for r in m_recs)
        total_slot_changes = b_sum + n_sum + h_sum

        avg_pau = sum(pau_vals) / len(pau_vals)
        med_pau = compute_percentile(pau_vals, 50)
        p10_pau = compute_percentile(pau_vals, 10)
        p25_pau = compute_percentile(pau_vals, 25)
        p75_pau = compute_percentile(pau_vals, 75)
        p90_pau = compute_percentile(pau_vals, 90)

        ben_pct = (b_sum / total_slot_changes * 100.0) if total_slot_changes > 0 else 0.0
        neu_pct = (n_sum / total_slot_changes * 100.0) if total_slot_changes > 0 else 0.0
        har_pct = (h_sum / total_slot_changes * 100.0) if total_slot_changes > 0 else 0.0

        avg_t5_churn = sum(r["top5_churn"] for r in m_recs) / len(m_recs)
        avg_t10_churn = sum(r["top10_churn"] for r in m_recs) / len(m_recs)
        mean_abs_delta = sum(r["mean_abs_rank_delta"] for r in m_recs) / len(m_recs)
        p90_rank_delta = compute_percentile([r["max_rank_delta"] for r in m_recs], 90)
        zero_mov_count = sum(1 for r in m_recs if r["top5_churn"] == 0 and r["candidates_moved"] == 0)
        zero_mov_pct = zero_mov_count / len(m_recs) * 100.0

        pers_lats = [r["pers_latency_ms"] for r in m_recs]
        mean_lat = sum(pers_lats) / len(pers_lats)
        p95_lat = compute_percentile(pers_lats, 95)
        p99_lat = compute_percentile(pers_lats, 99)

        mode_metrics[m] = {
            "reqs": len(m_recs),
            "lambda": PHASE_6_3_POLICY[m],
            "mean_pau": avg_pau,
            "median_pau": med_pau,
            "p10": p10_pau,
            "p25": p25_pau,
            "p75": p75_pau,
            "p90": p90_pau,
            "beneficial_pct": ben_pct,
            "neutral_pct": neu_pct,
            "harmful_pct": har_pct,
            "top5_churn": avg_t5_churn,
            "top10_churn": avg_t10_churn,
            "mean_abs_delta": mean_abs_delta,
            "p90_rank_delta": p90_rank_delta,
            "zero_movement_pct": zero_mov_pct,
            "mean_latency_ms": mean_lat,
            "p95_latency_ms": p95_lat,
            "p99_latency_ms": p99_lat,
            "budget_exceed_rate": sum(1 for l in pers_lats if l > 50.0) / len(pers_lats) * 100.0,
        }

        print(f"\n--- Mode: {m} (λ = {PHASE_6_3_POLICY[m]:.2f}, Reqs: {len(m_recs)}) ---")
        print(f"  PAU: Mean={avg_pau:+.4f} | Med={med_pau:+.4f} | P10={p10_pau:+.4f} | P25={p25_pau:+.4f} | P75={p75_pau:+.4f} | P90={p90_pau:+.4f}")
        print(f"  Changes (Slots={total_slot_changes}): Beneficial={ben_pct:>5.1f}% | Neutral={neu_pct:>5.1f}% | Harmful={har_pct:>5.1f}%")
        print(f"  Movement: Top-5 Churn={avg_t5_churn:.2f} | Top-10 Churn={avg_t10_churn:.2f} | Mean Abs Delta={mean_abs_delta:.3f} | Zero Mov={zero_mov_pct:>5.1f}%")
        print(f"  Latency: Mean={mean_lat:.2f}ms | P95={p95_lat:.2f}ms | P99={p99_lat:.2f}ms | Exceed Budget={mode_metrics[m]['budget_exceed_rate']:.1f}%")

    # ------------------------------------------------------------------------
    # 3. Direct Comparison: Phase 6.1 vs Phase 6.3
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("3. DIRECT COMPARISON: PHASE 6.1 (GLOBAL λ=0.05) vs PHASE 6.3 (MODE-SPECIFIC λ)")
    print("=" * 80)

    print(f"| {'Mode':<11} | {'6.1 λ':>5} | {'6.3 λ':>5} | {'PAU 6.1':>8} | {'PAU 6.3':>8} | {'Ben 6.1':>8} | {'Ben 6.3':>8} | {'Harm 6.1':>8} | {'Harm 6.3':>8} | {'Churn 6.1':>9} | {'Churn 6.3':>9} |")
    print(f"|{'-'*13}|{'-'*7}|{'-'*7}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*11}|{'-'*11}|")
    for m in ["BEST_MATCH", "POPULAR", "DISCOVER", "HIDDEN_GEMS"]:
        p61 = PHASE_6_1_METRICS[m]
        p63 = mode_metrics[m]
        print(
            f"| {m:<11} | {p61['lambda']:>5.2f} | {p63['lambda']:>5.2f} | "
            f"{p61['pau']:>+8.4f} | {p63['mean_pau']:>+8.4f} | "
            f"{p61['beneficial_pct']:>7.1f}% | {p63['beneficial_pct']:>7.1f}% | "
            f"{p61['harmful_pct']:>7.1f}% | {p63['harmful_pct']:>7.1f}% | "
            f"{p61['top5_churn']:>9.2f} | {p63['top5_churn']:>9.2f} |"
        )

    # ------------------------------------------------------------------------
    # 4. Profile Maturity Tier Segmentation
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("4. PROFILE MATURITY TIER BREAKDOWN")
    print("=" * 80)
    print(f"| {'Tier':<14} | {'Reqs':>4} | {'Mean PAU':>9} | {'Top-5 Churn':>11} | {'Beneficial %':>12} | {'Harmful %':>9} |")
    print(f"|{'-'*16}|{'-'*6}|{'-'*11}|{'-'*13}|{'-'*14}|{'-'*11}|")
    for tier_label in ["COLD", "EMERGING", "MODERATE", "ESTABLISHED", "ESTABLISHED_PROJECT"]:
        t_recs = [r for r in records if r["profile_label"] == tier_label]
        t_pau = sum(r["pau"] for r in t_recs) / len(t_recs)
        t_churn = sum(r["top5_churn"] for r in t_recs) / len(t_recs)
        b_sum = sum(r["beneficial"] for r in t_recs)
        h_sum = sum(r["harmful"] for r in t_recs)
        tot = b_sum + sum(r["neutral"] for r in t_recs) + h_sum
        b_pct = (b_sum / tot * 100.0) if tot > 0 else 0.0
        h_pct = (h_sum / tot * 100.0) if tot > 0 else 0.0
        print(f"| {tier_label:<14} | {len(t_recs):>4} | {t_pau:>+9.4f} | {t_churn:>11.2f} | {b_pct:>11.1f}% | {h_pct:>8.1f}% |")

    # ------------------------------------------------------------------------
    # 5. Project Context Segmentation (With vs Without Project)
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("5. PROJECT CONTEXT SEGMENTATION (REAL QUERIES)")
    print("=" * 80)
    recs_no_proj = [r for r in records if not r["has_project"]]
    recs_with_proj = [r for r in records if r["has_project"]]

    pau_no_p = sum(r["pau"] for r in recs_no_proj) / len(recs_no_proj)
    pau_with_p = sum(r["pau"] for r in recs_with_proj) / len(recs_with_proj)

    tot_no_p = sum(r["beneficial"] + r["neutral"] + r["harmful"] for r in recs_no_proj)
    ben_no_p = sum(r["beneficial"] for r in recs_no_proj) / max(tot_no_p, 1) * 100.0
    har_no_p = sum(r["harmful"] for r in recs_no_proj) / max(tot_no_p, 1) * 100.0
    churn_no_p = sum(r["top5_churn"] for r in recs_no_proj) / len(recs_no_proj)

    tot_with_p = sum(r["beneficial"] + r["neutral"] + r["harmful"] for r in recs_with_proj)
    ben_with_p = sum(r["beneficial"] for r in recs_with_proj) / max(tot_with_p, 1) * 100.0
    har_with_p = sum(r["harmful"] for r in recs_with_proj) / max(tot_with_p, 1) * 100.0
    churn_with_p = sum(r["top5_churn"] for r in recs_with_proj) / len(recs_with_proj)

    print(f"Without Active Project (Reqs: {len(recs_no_proj)}):")
    print(f"  Mean PAU:       {pau_no_p:+.4f}")
    print(f"  Beneficial %:   {ben_no_p:>5.1f}%")
    print(f"  Harmful %:      {har_no_p:>5.1f}%")
    print(f"  Top-5 Churn:    {churn_no_p:.2f} slots/req")

    print(f"\nWith Active Project (Reqs: {len(recs_with_proj)}):")
    print(f"  Mean PAU:       {pau_with_p:+.4f} (Incremental Uplift: {(pau_with_p - pau_no_p):+.4f})")
    print(f"  Beneficial %:   {ben_with_p:>5.1f}%")
    print(f"  Harmful %:      {har_with_p:>5.1f}%")
    print(f"  Top-5 Churn:    {churn_with_p:.2f} slots/req")

    # ------------------------------------------------------------------------
    # 6. Live Project Switching Validation (Contrasting Projects)
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("6. LIVE CONTRASTING PROJECT SWITCHING VALIDATION (No Project -> A -> B -> None)")
    print("=" * 80)

    proj_a = project_cyber   # 'Neon Syndicate: Data Breach'
    proj_b = project_void    # 'Void Sector: Star-Runner'
    assert proj_a and proj_b, "User must have both Project A and Project B"

    p_a_prof = context_blender.build_project_profile(project=proj_a.id, db=db)
    p_b_prof = context_blender.build_project_profile(project=proj_b.id, db=db)
    global_u2 = preference_aggregator.build_profile(db, str(user_established_2.id))
    global_u2_before = global_u2.model_dump()

    explanation_svc = PersonalizationExplanationService()

    switch_queries = [
        ("games with procedural generation and tactical combat", "DISCOVER"),
        ("deep space trading and resource economy simulation", "BEST_MATCH"),
        ("stylish combat shooter with neon aesthetics", "DISCOVER"),
        ("innovative 2d physics construction game", "HIDDEN_GEMS"),
        ("top rated sci-fi open world role playing game", "POPULAR"),
    ]

    switching_results = []
    print(f"Testing project switching sequence across {len(switch_queries)} authentic queries...\n")

    for q_text, q_mode in switch_queries:
        req = DiscoverySearchRequest(prompt=q_text, mode=q_mode, limit=10)
        base = await discovery_service.search(req)
        exp_lambda = PHASE_6_3_POLICY[q_mode]

        # State 1: No Project
        eff_none = context_blender.blend(global_u2, None)
        _, diag_none = personalization_experiment_service.apply(
            base_response=base,
            effective_profile=eff_none,
            user_id=str(user_established_2.id),
            mode=PERSONALIZATION_MODE_SHADOW,
            mode_lambdas=PHASE_6_3_POLICY,
        )

        # State 2: Project A (Neon Syndicate)
        eff_a = context_blender.blend(global_u2, p_a_prof)
        _, diag_a = personalization_experiment_service.apply(
            base_response=base,
            effective_profile=eff_a,
            user_id=str(user_established_2.id),
            mode=PERSONALIZATION_MODE_SHADOW,
            mode_lambdas=PHASE_6_3_POLICY,
        )
        reasons_a = []
        for r_id in diag_a.personalized_top_k_ids[:3]:
            cand = next((r for r in base.results if r.game.id == r_id), None)
            if cand:
                rs = explanation_svc.explain(candidate=cand, effective_profile=eff_a, project_profile=p_a_prof)
                reasons_a.extend([re.text for re in rs])

        # State 3: Project B (Void Sector)
        eff_b = context_blender.blend(global_u2, p_b_prof)
        _, diag_b = personalization_experiment_service.apply(
            base_response=base,
            effective_profile=eff_b,
            user_id=str(user_established_2.id),
            mode=PERSONALIZATION_MODE_SHADOW,
            mode_lambdas=PHASE_6_3_POLICY,
        )
        reasons_b = []
        for r_id in diag_b.personalized_top_k_ids[:3]:
            cand = next((r for r in base.results if r.game.id == r_id), None)
            if cand:
                rs = explanation_svc.explain(candidate=cand, effective_profile=eff_b, project_profile=p_b_prof)
                reasons_b.extend([re.text for re in rs])

        # State 4: No Project Again
        eff_none_2 = context_blender.blend(global_u2, None)
        _, diag_none_2 = personalization_experiment_service.apply(
            base_response=base,
            effective_profile=eff_none_2,
            user_id=str(user_established_2.id),
            mode=PERSONALIZATION_MODE_SHADOW,
            mode_lambdas=PHASE_6_3_POLICY,
        )

        # Assertions
        exact_recovery = (diag_none.personalized_top_k_ids == diag_none_2.personalized_top_k_ids)
        assert exact_recovery, f"Exact recovery failed on query: '{q_text}'"

        diff_a = (diag_none.personalized_top_k_ids != diag_a.personalized_top_k_ids)
        diff_b = (diag_none.personalized_top_k_ids != diag_b.personalized_top_k_ids)
        diff_ab = (diag_a.personalized_top_k_ids != diag_b.personalized_top_k_ids)

        switching_results.append({
            "query": q_text,
            "mode": q_mode,
            "lambda": exp_lambda,
            "top3_none": [ascii_safe(r.game.title) for r in base.results[:3]],
            "top3_pers_none": diag_none.personalized_top_k_ids[:3],
            "top3_pers_a": diag_a.personalized_top_k_ids[:3],
            "top3_pers_b": diag_b.personalized_top_k_ids[:3],
            "exact_recovery": exact_recovery,
            "diff_a_vs_none": diff_a,
            "diff_b_vs_none": diff_b,
            "diff_a_vs_b": diff_ab,
            "reason_a": reasons_a[0] if reasons_a else "None",
            "reason_b": reasons_b[0] if reasons_b else "None",
        })

        print(f"--- Query: '{q_text}' ({q_mode}, λ={exp_lambda:.2f}) ---")
        print(f"  Base Top-3:        {[ascii_safe(r.game.title) for r in base.results[:3]]}")
        print(f"  Pers Top-3 None:   {diag_none.personalized_top_k_ids[:3]} | PAU={diag_none.preference_alignment_uplift:+.4f}")
        print(f"  Pers Top-3 Proj A: {diag_a.personalized_top_k_ids[:3]} | PAU={diag_a.preference_alignment_uplift:+.4f} | Diff vs None: {diff_a}")
        if reasons_a:
            print(f"    Grounded Reason A: \"{reasons_a[0]}\"")
        print(f"  Pers Top-3 Proj B: {diag_b.personalized_top_k_ids[:3]} | PAU={diag_b.preference_alignment_uplift:+.4f} | Diff vs None: {diff_b} | Diff vs A: {diff_ab}")
        if reasons_b:
            print(f"    Grounded Reason B: \"{reasons_b[0]}\"")
        print(f"  Exact Recovery:    {exact_recovery}\n")

    # Verify global immutability
    assert global_u2.model_dump() == global_u2_before, "Global profile must remain strictly immutable!"
    global_u2_after = preference_aggregator.build_profile(db, str(user_established_2.id))
    assert global_u2.genres == global_u2_after.genres
    assert global_u2.mechanics == global_u2_after.mechanics
    assert global_u2.themes == global_u2_after.themes
    assert global_u2.modes == global_u2_after.modes
    assert global_u2.explicit_avoidances == global_u2_after.explicit_avoidances
    assert global_u2.total_signal_count == global_u2_after.total_signal_count
    assert global_u2.confidence_tier == global_u2_after.confidence_tier
    print("Global Profile Immutability: EXACT MATCH (100% immutable)")

    # ------------------------------------------------------------------------
    # 7. Summary
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 6.3 REAL SHADOW EVALUATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_phase_6_3_validation())
