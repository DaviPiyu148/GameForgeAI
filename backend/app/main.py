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
from app.api.profile import router as profile_router


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


def _sanitize_validation_error_details(errors: list) -> list:
    """
    Pydantic v2 embeds the raw exception object under `ctx.error` for any custom
    `@field_validator` that raises a bare ValueError/AssertionError (e.g. the DSL's
    script-injection checks or Remix's mutually-exclusive-intents check). That raw
    exception object is not JSON-serializable, so `JSONResponse` would crash while
    trying to render `details` -- turning a clean 422 into an unhandled 500. Strip
    it down to its string form; the human-readable message is already in `msg`.
    """
    sanitized = []
    for err in errors:
        err = dict(err)
        ctx = err.get("ctx")
        if isinstance(ctx, dict) and "error" in ctx:
            ctx = dict(ctx)
            ctx["error"] = str(ctx["error"])
            err["ctx"] = ctx
        sanitized.append(err)
    return sanitized


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Format Pydantic validation errors into structured error envelope."""
    error_details = _sanitize_validation_error_details(exc.errors())
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
app.include_router(profile_router, prefix="/api")            # V3: /api/profile/*


@app.get("/")
def root():
    """Root discovery endpoint."""
    return {
        "name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "health": "/api/health",
        "docs": "/docs",
    }
