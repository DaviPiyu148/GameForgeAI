"""
Deterministic Benchmark Script: evaluate_gameplay_experience_v1.py
Evaluates gameplay rhythm, beat scores, and deadlock-free execution
across real-output database fixtures.
"""

import json
from pathlib import Path
import statistics
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.generation.dsl_models import GameDSL

from app.generation.gameplay_rhythm import GameplayRhythmManager
from app.generation.depth_evaluator import GameDepthEvaluator
from app.generation.generation_contract import build_generation_contract


def run_benchmark():
    fixtures_path = Path(__file__).parent.parent / "tests" / "data" / "real_output_fixtures.json"
    if not fixtures_path.exists():
        print(f"Error: Fixtures file not found at {fixtures_path}")
        return

    with open(fixtures_path, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    print("============================================================")
    print("GAMEFORGE AI — GAMEPLAY EXPERIENCE V1 BENCHMARK")
    print(f"Total Fixtures Analyzed: {len(fixtures)}")
    print("============================================================")

    beat_scores = []
    quality_scores = []
    deadlock_count = 0
    warning_count = 0

    for idx, fix in enumerate(fixtures, 1):
        title = fix.get("title", f"Game #{idx}")
        dsl = GameDSL.model_validate(fix["dsl"])

        # 1. Deadlock Detection
        deadlock_res = GameplayRhythmManager.detect_deadlocks(dsl)
        if not deadlock_res.is_valid:
            deadlock_count += len(deadlock_res.deadlocks)
        warning_count += len(deadlock_res.warnings)

        # 2. Gameplay Beat Evaluation
        beat_score, beats = GameplayRhythmManager.evaluate_gameplay_beats(dsl)
        beat_scores.append(beat_score)

        # 3. Overall Depth & Quality Score
        contract = build_generation_contract(title, world_mode=dsl.world.world_mode)
        report = GameDepthEvaluator.evaluate(dsl, contract)
        quality_scores.append(report.score)

        print(f"[{idx:02d}] {title[:32]:<32} | Beats: {beat_score:4.1f}/100 | Quality: {report.score:3d}/100 | Deadlocks: {len(deadlock_res.deadlocks)}")

    print("------------------------------------------------------------")
    print("SUMMARY METRICS:")
    print(f"Mean Gameplay Beat Score:    {statistics.mean(beat_scores):.2f}/100")
    print(f"Median Gameplay Beat Score:  {statistics.median(beat_scores):.2f}/100")
    print(f"Mean Overall Quality Score:  {statistics.mean(quality_scores):.2f}/100")
    print(f"Median Overall Quality Score:{statistics.median(quality_scores):.2f}/100")
    print(f"Total Detected Deadlocks:    {deadlock_count}")
    print(f"Total Pacing Notices:        {warning_count}")
    print("============================================================")


if __name__ == "__main__":
    run_benchmark()
