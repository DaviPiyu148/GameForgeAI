import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWLISTED_TELEMETRY_EVENTS = {
    "SESSION_STARTED",
    "SESSION_START",
    "SESSION_ENDED",
    "SESSION_END",
    "PLAYER_DAMAGED",
    "PLAYER_DAMAGE",
    "PLAYER_DIED",
    "PLAYER_DEATH",
    "OBJECTIVE_PROGRESS",
    "OBJECTIVE_COMPLETED",
    "WAVE_STARTED",
    "WAVE_COMPLETED",
    "PHASE_STARTED",
    "COLLECTIBLE_COLLECTED",
    "ITEM_COLLECTED",
    "ENEMY_SPAWNED",
    "ENEMY_DEFEATED",
    "PROJECTILE_FIRED",
    "CHECKPOINT_REACHED",
    "GAME_WON",
    "GAME_LOST",
    "SCORE_CHANGED",
}

PROHIBITED_SCRIPT_PATTERNS = [
    r"javascript:",
    r"<script",
    r"eval\(",
    r"new\s+Function",
    r"__proto__",
    r"\.constructor\b",
    r"\[\s*['\"]constructor['\"]\s*\]",
]


def check_for_script_injection(value: Any) -> None:
    """Recursively verify no executable code or injection strings exist in telemetry fields."""
    if isinstance(value, str):
        for pattern in PROHIBITED_SCRIPT_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValueError(f"Prohibited script or code execution detected: '{value}'")
    elif isinstance(value, dict):
        for k, v in value.items():
            check_for_script_injection(k)
            check_for_script_injection(v)
    elif isinstance(value, list):
        for item in value:
            check_for_script_injection(item)


class TelemetryEventSchema(BaseModel):
    """Allowlisted and bounded telemetry event data."""
    type: str
    timestamp: int = Field(..., ge=0)
    data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")

    @field_validator("type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        v_upper = v.strip().upper()
        if v_upper not in ALLOWLISTED_TELEMETRY_EVENTS:
            raise ValueError(f"Unsupported or unallowlisted telemetry event type: '{v}'")
        return v_upper

    @field_validator("data")
    @classmethod
    def validate_event_data(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v:
            check_for_script_injection(v)
            # Enforce reasonable payload size
            if len(str(v)) > 1024:
                raise ValueError("Telemetry event data payload exceeds maximum size limit (1KB)")
        return v


class PlaytestCreate(BaseModel):
    """Payload submitted when a playtest session finishes."""
    duration_seconds: int = Field(0, ge=0)
    score: int = Field(0, ge=0)
    damage_taken: int = Field(0, ge=0)
    damage_dealt: int = Field(0, ge=0)
    enemies_defeated: int = Field(0, ge=0)
    collectibles_gathered: int = Field(0, ge=0)
    objectives_completed: int = Field(0, ge=0)
    outcome: str = Field("PLAYED", max_length=50)
    version_number: Optional[int] = Field(default=1, ge=1)
    seed: Optional[int] = None
    telemetry_events: Optional[List[Union[TelemetryEventSchema, Dict[str, Any]]]] = Field(
        default_factory=list
    )

    model_config = ConfigDict(extra="ignore")

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in ("WON", "LOST", "ABANDONED", "PLAYED"):
            return "PLAYED"
        return cleaned

    @field_validator("telemetry_events")
    @classmethod
    def validate_telemetry_events(cls, v: Optional[List[Any]]) -> List[Dict[str, Any]]:
        if not v:
            return []
        cleaned: List[Dict[str, Any]] = []
        # Cap at 150 events to prevent unbounded growth
        for item in v[:150]:
            if isinstance(item, TelemetryEventSchema):
                cleaned.append(item.model_dump())
            elif isinstance(item, dict):
                ev_type = str(item.get("type", "")).strip().upper()
                if ev_type in ALLOWLISTED_TELEMETRY_EVENTS:
                    data = item.get("data")
                    if data:
                        check_for_script_injection(data)
                    cleaned.append({
                        "type": ev_type,
                        "timestamp": int(item.get("timestamp", 0)),
                        "data": data,
                    })
        return cleaned


class PlaytestProblem(BaseModel):
    """Specific diagnosed gameplay problem with supporting telemetry evidence."""
    category: str = Field(..., max_length=50)
    severity: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    evidence: str = Field(..., max_length=300)
    diagnosis: str = Field(..., max_length=300)

    model_config = ConfigDict(extra="ignore")


class PlaytestRecommendation(BaseModel):
    """Actionable improvement recommendation produced by AI critique."""
    id: str = Field(..., max_length=50)
    category: str = Field(..., max_length=50)
    description: str = Field(..., max_length=300)
    dsl_change_type: str = Field(..., max_length=50)
    evidence: Optional[str] = Field(default=None, max_length=300)
    suggested_patch: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class PlaytestAnalysisResponse(BaseModel):
    """Structured AI Playtest Critique output."""
    fun_rating: float = Field(..., ge=0.0, le=10.0)
    difficulty_rating: float = Field(..., ge=0.0, le=10.0)
    clarity_rating: float = Field(..., ge=0.0, le=10.0)
    strengths: List[str] = Field(default_factory=list, max_length=6)
    problems: List[Union[PlaytestProblem, str]] = Field(default_factory=list, max_length=6)
    recommendations: List[PlaytestRecommendation] = Field(default_factory=list, max_length=6)

    model_config = ConfigDict(extra="ignore")


class PlaytestSessionResponse(BaseModel):
    """Public schema for persisted playtest session."""
    id: str
    project_id: str
    user_id: str
    duration_seconds: int
    score: int
    damage_taken: int
    damage_dealt: int
    enemies_defeated: int
    collectibles_gathered: int
    objectives_completed: int
    outcome: str
    telemetry_events: Optional[List[Dict[str, Any]]] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="ignore")
