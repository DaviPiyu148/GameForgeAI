from contextlib import asynccontextmanager
import uuid
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.builds import router as builds_router
from app.api.discovery import router as discovery_router
from app.api.auth import router as auth_router
from app.api.saved_discoveries import router as saved_discoveries_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle context manager: sweep database on startup to reconcile any interrupted builds."""
    from app.db.session import SessionLocal
    from app.repositories.build_repo import build_repository
    from sqlalchemy.exc import OperationalError
    db = SessionLocal()
    try:
        reconciled = build_repository.reconcile_orphaned_builds(db)
        if reconciled > 0:
            import logging
            logging.getLogger("gameforge").info(
                f"Reconciled {reconciled} orphaned build(s) to ERROR state on startup."
            )
    except OperationalError:
        # Table not created yet (e.g. in test setup before Base.metadata.create_all)
        pass
    except Exception as e:
        import logging
        logging.getLogger("gameforge").warning(f"Startup orphan reconciliation skipped: {e}")
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="GameForge AI Modular Monolith API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Format Pydantic validation errors into structured error envelope."""
    error_details = exc.errors()
    first_error = error_details[0] if error_details else {}
    msg = f"{first_error.get('loc', ['field'])[-1]}: {first_error.get('msg', 'Invalid input')}"
    if "/builds" in request.url.path:
        code = "BUILD_VALIDATION_FAILED"
    elif "/discovery" in request.url.path:
        code = "DISCOVERY_VALIDATION_FAILED"
    elif "/auth" in request.url.path:
        code = "AUTH_VALIDATION_FAILED"
    else:
        code = "PROJECT_VALIDATION_FAILED"
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": code,
                "message": msg,
                "request_id": str(uuid.uuid4()),
                "details": error_details,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Convert HTTPExceptions (including auth 401s from get_current_user) to
    the structured error envelope used throughout the API.
    """
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        # Already structured (from get_current_user or other raising code)
        content = {"error": detail}
    else:
        content = {
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(detail) if detail else "An error occurred.",
                "request_id": str(uuid.uuid4()),
            }
        }
    headers = getattr(exc, "headers", None)
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


# Register API Routers
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")           # B7: /api/auth/*
app.include_router(projects_router, prefix="/api")
app.include_router(builds_router, prefix="/api")
app.include_router(discovery_router, prefix="/api")
app.include_router(saved_discoveries_router, prefix="/api")  # B7: /api/saved-discoveries/*


@app.get("/")
def root():
    """Root discovery endpoint."""
    return {
        "name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "health": "/api/health",
        "docs": "/docs",
    }
