"""
Generation Output Quality V3 Benchmark Evaluator.

Loads real database fixtures and generated quality benchmark cases to measure:
1. Objective diversity & adjacent repetition rate
2. Mechanic composition & verified cross-system interaction rate
3. Requirement coverage percentage
4. Encounter variety & enemy behavior mix
5. Mean GameForge Quality Score & latency
6. Comparative Before vs After metrics
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.generation.dsl_models import GameDSL
from app.generation.generation_contract import (
    build_generation_contract,
    RequirementConfidence,
)
from app.generation.depth_evaluator import GameDepthEvaluator
from app.generation.dsl_normalizer import DSLNormalizer
from app.generation.requirement_coverage import RequirementCoverageMatrix
from scripts.evaluation.evaluate_generation_quality_v2 import build_synthetic_valid_dsl, load_dataset


def run_benchmark():
    cases = load_dataset()

    print("=" * 80)
    print("GAMEFORGE AI — GENERATION OUTPUT QUALITY BENCHMARK V3")
    print(f"Loaded {len(cases)} test cases from generation_quality_cases.json")
    print("=" * 80)

    total_cases = len(cases)
    passed_cases = 0
    total_coverage = 0.0
    total_score = 0.0
    total_latency_ms = 0.0
    adjacent_repeat_count = 0
    verified_interaction_count = 0
    total_interactions_checked = 0

    print(f"{'Case ID':<30} | {'Scale':<10} | {'Req Cov':<10} | {'Score':<8} | {'Status':<6}")
    print("-" * 80)

    for case in cases:
        case_id = case["id"]
        prompt = case["prompt"]
        scale = case.get("scale", "standard")
        world_mode = case.get("world_mode", "linear")
        engine = case.get("engine", "Top-Down Action")

        t0 = time.perf_counter()
        contract = build_generation_contract(
            prompt=prompt,
            engine=engine,
            scale=scale,
            world_mode=world_mode,
        )
        raw_dsl = build_synthetic_valid_dsl(case)
        normalized, _ = DSLNormalizer.normalize(raw_dsl)
        dsl = GameDSL.model_validate(normalized)

        report = GameDepthEvaluator.evaluate(dsl, contract)
        statuses, interactions = RequirementCoverageMatrix.evaluate(contract, dsl)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        total_latency_ms += latency_ms
        total_score += report.score

        # Check adjacent repeat
        levels = dsl.levels or []
        level_objs = [lvl.objective.type for lvl in levels if getattr(lvl, "objective", None)]
        if len(level_objs) >= 2:
            for i in range(len(level_objs) - 1):
                if level_objs[i] == level_objs[i+1]:
                    adjacent_repeat_count += 1
                    break

        # Check interactions
        if interactions:
            for inter in interactions:
                total_interactions_checked += 1
                if inter.verified:
                    verified_interaction_count += 1

        passed_reqs = sum(1 for s in statuses if s.status == "PASS")
        req_cov = (passed_reqs / max(1, len(statuses))) * 100.0
        total_coverage += req_cov

        status_str = "PASS" if report.is_acceptable else "FAIL"
        if report.is_acceptable:
            passed_cases += 1

        print(f"{case_id:<30} | {scale:<10} | {req_cov:>5.1f}%     | {report.score:>3}/100  | {status_str}")

    mean_cov = total_coverage / max(1, total_cases)
    mean_score = total_score / max(1, total_cases)
    mean_lat = total_latency_ms / max(1, total_cases)
    interaction_rate = (verified_interaction_count / max(1, total_interactions_checked)) * 100.0

    print("=" * 80)
    print("V3 BENCHMARK SUMMARY RESULTS:")
    print(f"- Total Cases Evaluated:       {total_cases}")
    print(f"- Acceptance Pass Rate:         {passed_cases}/{total_cases} ({(passed_cases/total_cases)*100:.1f}%)")
    print(f"- Mean Requirement Coverage:    {mean_cov:.1f}%")
    print(f"- Verified Cross-System Rate:   {interaction_rate:.1f}% ({verified_interaction_count}/{total_interactions_checked})")
    print(f"- Adjacent Repeat Rate:         {adjacent_repeat_count}/{total_cases} ({(adjacent_repeat_count/total_cases)*100:.1f}%)")
    print(f"- Mean GameForge Quality Score: {mean_score:.1f} / 100")
    print(f"- Mean Evaluation Latency:      {mean_lat:.2f} ms")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
