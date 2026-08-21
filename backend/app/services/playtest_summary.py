"""
Deterministic Playtest Summary & Aggregation Engine.

Computes authoritative gameplay metrics directly from allowlisted telemetry event streams.
Ensures the backend computes verifiable ground-truth facts rather than relying on LLMs
for basic event counting.

Security invariant: `score` is NEVER seeded from or overridden by a client-declared value.
It is derived purely from bounded, per-event contributions below. `declared_score` is
accepted only as an unused diagnostic/display input from the client and has zero effect
on the authoritative summary. Individual event numeric fields are clamped to sane per-event
bounds so a single forged event cannot inflate the authoritative score/damage arbitrarily.
"""
from typing import Any, Dict, List, Optional

# Per-event numeric clamps. These bound the damage/points a single allowlisted telemetry
# event may contribute, so a client cannot forge an oversized `data` payload to inflate
# authoritative aggregates (score, damage) even though the event *type* is allowlisted.
MAX_DAMAGE_PER_EVENT = 500
MAX_POINTS_PER_COLLECTIBLE = 1000
MAX_WAVE_NUMBER = 999


def _clamped_int(data: Dict[str, Any], key: str, default: int, max_value: int, min_value: int = 0) -> int:
    try:
        value = int(data.get(key, default))
    except (TypeError, ValueError):
        value = default
    return max(min_value, min(value, max_value))


class PlaytestSummaryEngine:
    """
    Deterministic aggregator for playtest event streams.
    """

    @classmethod
    def aggregate(
        cls,
        events: Optional[List[Dict[str, Any]]],
        declared_duration: int = 0,
        declared_score: int = 0,
        declared_outcome: str = "PLAYED",
    ) -> Dict[str, Any]:
        """
        Aggregate chronological telemetry events into a deterministic summary.

        `declared_score` is intentionally never used to seed or override the computed
        `score` field below — it exists only for backward-compatible request payload
        acceptance and is otherwise ignored.
        """
        if not events:
            return {
                "duration_seconds": max(0, declared_duration),
                "score": 0,
                "damage_taken": 0,
                "damage_dealt": 0,
                "deaths": 0,
                "enemies_defeated": 0,
                "collectibles_gathered": 0,
                "objectives_completed": 0,
                "waves_reached": 1,
                "phase_reached": "EARLY",
                "outcome": declared_outcome.upper() if declared_outcome else "PLAYED",
                "termination_reason": "session_completed" if declared_outcome == "WON" else "normal_exit",
            }

        start_time: Optional[int] = None
        end_time: Optional[int] = None
        damage_taken = 0
        damage_dealt = 0
        deaths = 0
        enemies_defeated = 0
        collectibles_gathered = 0
        objectives_completed = 0
        score = 0
        waves_reached = 1
        phase_reached = "EARLY"
        outcome = declared_outcome.upper()
        termination_reason = "normal_exit"

        for ev in events:
            ev_type = str(ev.get("type", "")).strip().upper()
            ts = int(ev.get("timestamp", 0))
            data = ev.get("data") or {}

            if start_time is None and ts > 0:
                start_time = ts
            if ts > 0:
                end_time = ts

            if ev_type in ("SESSION_STARTED", "SESSION_START"):
                start_time = ts
            elif ev_type in ("SESSION_ENDED", "SESSION_END"):
                end_time = ts
                if "outcome" in data:
                    outcome = str(data["outcome"]).upper()

            elif ev_type in ("PLAYER_DAMAGED", "PLAYER_DAMAGE"):
                damage_taken += _clamped_int(data, "damage", 10, MAX_DAMAGE_PER_EVENT)
            elif ev_type in ("PLAYER_DIED", "PLAYER_DEATH"):
                deaths += 1
                outcome = "LOST"
                termination_reason = "player_death"
            elif ev_type == "ENEMY_DEFEATED":
                enemies_defeated += 1
                damage_dealt += _clamped_int(data, "damageDealt", 25, MAX_DAMAGE_PER_EVENT)
            elif ev_type in ("COLLECTIBLE_COLLECTED", "ITEM_COLLECTED"):
                collectibles_gathered += 1
                score += _clamped_int(data, "points", 50, MAX_POINTS_PER_COLLECTIBLE)
            elif ev_type == "OBJECTIVE_COMPLETED":
                objectives_completed += 1
                if "wave" in data:
                    waves_reached = max(waves_reached, _clamped_int(data, "wave", waves_reached, MAX_WAVE_NUMBER, min_value=1))
            elif ev_type == "WAVE_STARTED":
                waves_reached = max(waves_reached, _clamped_int(data, "wave", 1, MAX_WAVE_NUMBER, min_value=1))
            elif ev_type == "PHASE_STARTED":
                phase_reached = str(data.get("phase", "EARLY")).upper()
            elif ev_type == "SCORE_CHANGED":
                # Informational only. `score` is authoritative from the discrete,
                # bounded scoring events above and is never overridden by a
                # client-reported running total, which could be forged independently
                # of any actual in-game scoring event.
                pass
            elif ev_type == "GAME_WON":
                outcome = "WON"
                termination_reason = "objective_cleared"
            elif ev_type == "GAME_LOST":
                outcome = "LOST"
                termination_reason = "mission_failed"

        computed_duration = declared_duration
        if start_time and end_time and end_time >= start_time:
            computed_duration = max(1, round((end_time - start_time) / 1000))

        return {
            "duration_seconds": computed_duration,
            "score": score,
            "damage_taken": damage_taken,
            "damage_dealt": damage_dealt,
            "deaths": deaths,
            "enemies_defeated": enemies_defeated,
            "collectibles_gathered": collectibles_gathered,
            "objectives_completed": objectives_completed,
            "waves_reached": waves_reached,
            "phase_reached": phase_reached,
            "outcome": outcome,
            "termination_reason": termination_reason,
        }
