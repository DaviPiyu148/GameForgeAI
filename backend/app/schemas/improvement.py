from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ImprovementApplyRequest(BaseModel):
    """Payload to apply approved recommendations to a project."""
    selected_recommendations: List[Dict[str, Any]] = Field(..., min_length=1)
    user_notes: Optional[str] = Field(None, max_length=500)

    model_config = ConfigDict(extra="ignore")


class ImprovementApplyResponse(BaseModel):
    """Result of applying improvement patch."""
    project_id: str
    version_number: int
    game_dsl: Dict[str, Any]
    change_summary: str
    status: str = "SUCCESS"

    model_config = ConfigDict(extra="ignore")
