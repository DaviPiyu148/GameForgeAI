from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.builds import router as builds_router

__all__ = ["health_router", "projects_router", "builds_router"]
