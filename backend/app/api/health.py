from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Health check endpoint confirming API availability."""
    return HealthResponse(
        status="ok",
        service="gameforge-api"
    )
