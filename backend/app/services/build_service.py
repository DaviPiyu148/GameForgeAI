import asyncio
from datetime import datetime, timezone
import json
from typing import AsyncGenerator, Callable, Dict, List, Optional, Set
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.build import BuildJob
from app.models.build_log import BuildLog
from app.repositories.build_repo import BuildRepository, build_repository
from app.schemas.build import (
    BuildCreate,
    BuildLogEntry,
    BuildLogListResponse,
    BuildResponse,
)
from app.schemas.project import BuildParams, ProjectCreate
from app.services.game_generation_service import (
    GameGenerationService,
    game_generation_service,
)
from app.services.project_service import ProjectService, project_service


class BuildNotFoundError(Exception):
    """
    Raised when a requested build job does not exist OR the requester is not the owner.
    Owner mismatch produces the same 404 as not-found (IDOR protection).
    """
    def __init__(self, build_id: str):
        self.build_id = build_id
        super().__init__(f"Build job with ID '{build_id}' not found.")


class BuildEventBroadcaster:
    """In-memory event broadcaster for live SSE subscriptions per build."""

    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def add_subscriber(self, build_id: str) -> asyncio.Queue:
        """Register a subscriber queue for a specific build."""
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            if build_id not in self._subscribers:
                self._subscribers[build_id] = set()
            self._subscribers[build_id].add(queue)
        return queue

    async def remove_subscriber(self, build_id: str, queue: asyncio.Queue):
        """Unregister a subscriber queue."""
        async with self._lock:
            if build_id in self._subscribers:
                self._subscribers[build_id].discard(queue)
                if not self._subscribers[build_id]:
                    del self._subscribers[build_id]

    async def broadcast(self, build_id: str, event_type: str, data: dict):
        """Push an event to all live subscribers of a build under lock to maintain ordering."""
        async with self._lock:
            queues = list(self._subscribers.get(build_id, []))
            for q in queues:
                try:
                    q.put_nowait({"event": event_type, "data": data})
                except asyncio.QueueFull:
                    pass


class BuildService:
    """
    Orchestration service for BuildJob lifecycle, AI generation, and SSE streaming.
    Guarantees atomic state transitions, cancel-safety, log sequence monotonicity,
    and orphan reconciliation.
    """

    def __init__(
        self,
        repo: BuildRepository = build_repository,
        proj_service: ProjectService = project_service,
        generation_svc: GameGenerationService = game_generation_service,
        session_factory: Callable[[], Session] = SessionLocal,
    ):
        self.repo = repo
        self.project_service = proj_service
        self.generation_service = generation_svc
        self.session_factory = session_factory
        self.broadcaster = BuildEventBroadcaster()
        self._running_builds: Set[str] = set()
        self._active_tasks: Dict[str, asyncio.Task] = {}

    def to_response(self, build: BuildJob) -> BuildResponse:
        """Convert BuildJob ORM model to BuildResponse schema."""
        return BuildResponse(
            build_id=build.id,
            status=build.status,
            project_id=build.project_id,
            error_code=build.error_code,
            error_message=build.error_message,
            created_at=build.created_at,
            started_at=build.started_at,
            completed_at=build.completed_at,
            game_dsl=build.game_dsl,
        )

    async def submit_build(
        self, db: Session, data: "BuildCreate", user_id: Optional[str] = None
    ) -> "BuildResponse":
        """
        Create and queue a new build job, launching background execution.
        Idempotently returns existing active build if identical parameters are already in-flight.
        """
        prompt_cleaned = data.prompt.strip()

        # Idempotency check: prevent duplicate simultaneous builds for identical prompts
        if user_id:
            duplicate = self.repo.find_active_duplicate_build(
                db=db,
                user_id=user_id,
                prompt=prompt_cleaned,
                engine=data.parameters.engine,
                art_density=data.parameters.art_density,
                physics=data.parameters.physics,
            )
            if duplicate:
                return self.to_response(duplicate)

        build = BuildJob(
            user_id=user_id,
            prompt=prompt_cleaned,
            engine=data.parameters.engine,
            art_density=data.parameters.art_density,
            physics=data.parameters.physics,
            modules=data.parameters.modules,
            status="QUEUED",
        )
        saved = self.repo.create_build(db, build)

        # Launch background worker task on event loop and track task for cancellation
        task = asyncio.create_task(self._run_build_worker(saved.id, user_id=user_id))
        self._active_tasks[saved.id] = task

        return self.to_response(saved)

    async def cancel_build(
        self, db: Session, build_id: str, user_id: Optional[str] = None
    ) -> "BuildResponse":
        """
        Cancel an active build job with ownership check.
        Atomically transitions QUEUED/RUNNING/VALIDATING -> CANCELLED.
        Does NOT create a Project, aborts async task, logs cancellation, and notifies SSE.
        """
        build = self.repo.get_build_by_id(db, build_id)
        if not build:
            raise BuildNotFoundError(build_id)
        if user_id is not None and build.user_id != user_id:
            raise BuildNotFoundError(build_id)

        # If already terminal, return as is (idempotent)
        if build.status in ("SUCCESS", "ERROR", "CANCELLED"):
            return self.to_response(build)

        now = datetime.now(timezone.utc)

        # Atomic conditional update: only transition if still non-terminal
        cancelled = self.repo.transition_status(
            db=db,
            build_id=build_id,
            from_statuses=["QUEUED", "RUNNING", "VALIDATING"],
            to_status="CANCELLED",
            completed_at=now,
            error_code="BUILD_CANCELLED",
            error_message="Build cancelled by user.",
        )

        if not cancelled:
            # Build reached a terminal state (SUCCESS / ERROR) concurrently
            refreshed = self.repo.get_build_by_id(db, build_id)
            return self.to_response(refreshed or build)

        # Cancel in-memory worker task if active
        task = self._active_tasks.pop(build_id, None)
        if task and not task.done():
            task.cancel()
        self._running_builds.discard(build_id)

        # Safe monotonic log allocation
        cancel_log = self.repo.append_log(
            db,
            build_id=build_id,
            level="WARNING",
            message="[SYS] BUILD CANCELLED BY USER",
            timestamp=now,
        )

        # Broadcast terminal status and log to SSE
        await self.broadcaster.broadcast(
            build_id,
            "log",
            {
                "sequence": cancel_log.sequence_number,
                "level": "WARNING",
                "message": "[SYS] BUILD CANCELLED BY USER",
                "timestamp": now.isoformat(),
            },
        )
        await self.broadcaster.broadcast(
            build_id,
            "status",
            {
                "build_id": build_id,
                "status": "CANCELLED",
                "error_code": "BUILD_CANCELLED",
                "error_message": "Build cancelled by user.",
            },
        )

        refreshed = self.repo.get_build_by_id(db, build_id)
        return self.to_response(refreshed or build)

    def get_build(
        self, db: Session, build_id: str, user_id: Optional[str] = None
    ) -> "BuildResponse":
        """
        Retrieve build job status by ID with ownership check.
        Owner mismatch → BuildNotFoundError (404, IDOR protection).
        """
        build = self.repo.get_build_by_id(db, build_id)
        if not build:
            raise BuildNotFoundError(build_id)
        if user_id is not None and build.user_id != user_id:
            raise BuildNotFoundError(build_id)
        return self.to_response(build)

    def get_logs(
        self, db: Session, build_id: str, user_id: Optional[str] = None
    ) -> "BuildLogListResponse":
        """
        Retrieve all persisted logs for a build with ownership check.
        Owner mismatch → BuildNotFoundError (404, IDOR protection).
        """
        build = self.repo.get_build_by_id(db, build_id)
        if not build:
            raise BuildNotFoundError(build_id)
        if user_id is not None and build.user_id != user_id:
            raise BuildNotFoundError(build_id)

        db_logs = self.repo.get_logs(db, build_id)
        log_entries = [
            BuildLogEntry(
                sequence=log.sequence_number,
                level=log.level,
                message=log.message,
                timestamp=log.timestamp,
            )
            for log in db_logs
        ]
        return BuildLogListResponse(build_id=build_id, logs=log_entries)

    async def _run_build_worker(self, build_id: str, user_id: Optional[str] = None):
        """
        Background worker that executes the AI generation pipeline, writes logs,
        persists the validated Game DSL, and creates the Project on success.
        Enforces atomic state transitions and cancel-safety.
        """
        if build_id in self._running_builds:
            return
        self._running_builds.add(build_id)

        db: Session = self.session_factory()
        try:
            build = self.repo.get_build_by_id(db, build_id)
            if not build or build.status in ("SUCCESS", "ERROR", "CANCELLED"):
                return

            now = datetime.now(timezone.utc)
            # Atomically transition QUEUED -> RUNNING
            transitioned = self.repo.transition_status(
                db=db,
                build_id=build_id,
                from_statuses=["QUEUED"],
                to_status="RUNNING",
                started_at=now,
            )
            if not transitioned:
                # Build was cancelled or moved to error before worker ran
                return

            await self.broadcaster.broadcast(
                build_id,
                "status",
                {"build_id": build_id, "status": "RUNNING"},
            )

            # Helper to emit logs safely to DB and broadcast to SSE
            def emit_log(level: str, message: str):
                log = self.repo.append_log(
                    db,
                    build_id=build_id,
                    level=level,
                    message=message,
                )
                asyncio.create_task(
                    self.broadcaster.broadcast(
                        build_id,
                        "log",
                        {
                            "sequence": log.sequence_number,
                            "level": level,
                            "message": message,
                            "timestamp": log.timestamp.isoformat(),
                        },
                    )
                )

            # Helper to update status safely
            def set_status(status: str):
                if status == "VALIDATING":
                    self.repo.transition_status(
                        db=db,
                        build_id=build_id,
                        from_statuses=["RUNNING"],
                        to_status="VALIDATING",
                    )
                    asyncio.create_task(
                        self.broadcaster.broadcast(
                            build_id,
                            "status",
                            {"build_id": build_id, "status": "VALIDATING"},
                        )
                    )

            # Execute AI generation pipeline
            result = await self.generation_service.generate_game_dsl(
                prompt=build.prompt,
                engine=build.engine,
                art_density=build.art_density,
                physics=build.physics,
                modules=build.modules if isinstance(build.modules, list) else [],
                emit_log=emit_log,
                set_status=set_status,
            )

            # Check if build was cancelled while AI generation was in-flight
            refreshed = self.repo.get_build_by_id(db, build_id)
            if not refreshed or refreshed.status == "CANCELLED":
                return

            now = datetime.now(timezone.utc)

            if result.success and result.dsl:
                # Phase B5: Backend Runtime Compatibility Validation & [PHASER] Logging
                emit_log("INFO", "[PHASER] Initializing prototype compatibility checks (v1.0.0, Phaser 3.88.2)...")
                emit_log("INFO", f"[PHASER] Validating archetype: '{result.dsl.metadata.archetype}'...")
                emit_log("INFO", f"[PHASER] Checking world boundaries ({result.dsl.world.width}x{result.dsl.world.height}, gravity={result.dsl.world.gravity})...")
                emit_log("INFO", f"[PHASER] Checking {len(result.dsl.entities)} entity locomotion behaviors and bounds...")
                emit_log("INFO", f"[PHASER] Checking {len(result.dsl.rules)} gameplay rules and action handlers...")

                from app.runtime.compatibility import RuntimeCompatibilityValidator
                from app.runtime.metadata import generate_runtime_metadata

                compat_res = RuntimeCompatibilityValidator.validate(result.dsl)
                if not compat_res.compatible:
                    err_msg = "; ".join(compat_res.errors)
                    emit_log("ERROR", f"[PHASER] Runtime compatibility validation failed: {err_msg}")
                    self.repo.transition_status(
                        db=db,
                        build_id=build_id,
                        from_statuses=["RUNNING", "VALIDATING"],
                        to_status="ERROR",
                        completed_at=now,
                        error_code="RUNTIME_INCOMPATIBLE",
                        error_message=err_msg,
                    )
                    await self.broadcaster.broadcast(
                        build_id,
                        "status",
                        {
                            "build_id": build_id,
                            "status": "ERROR",
                            "error_code": "RUNTIME_INCOMPATIBLE",
                            "error_message": err_msg,
                        },
                    )
                    return

                emit_log("INFO", "[PHASER] Runtime compatibility validated. Prototype ready.")

                # Generate deterministic runtime metadata with provider traceability
                runtime_meta = generate_runtime_metadata(seed_source=build.id)
                if result.provider_meta:
                    runtime_meta["provider"] = result.provider_meta.get("provider", "gemini")
                    runtime_meta["model"] = result.provider_meta.get("model", "gemma-4-31b-it")
                    runtime_meta["fallbackUsed"] = result.provider_meta.get("fallback_used", False)
                    if result.provider_meta.get("fallback_reason"):
                        runtime_meta["fallbackReason"] = result.provider_meta.get("fallback_reason")

                # Derive project metadata from validated DSL
                derived_title = result.dsl.metadata.title or build.prompt[:40].strip() or "Untitled Prototype"
                derived_genre = result.dsl.metadata.genre or "Generated Concept"

                params = BuildParams(
                    engine=build.engine,
                    artDensity=build.art_density,
                    physics=build.physics,
                    modules=build.modules if isinstance(build.modules, list) else [],
                )

                # Pre-check cancellation state immediately before project creation
                current_chk = self.repo.get_build_by_id(db, build_id)
                if not current_chk or current_chk.status == "CANCELLED":
                    return

                # Create authoritative Project & Version
                project_res = self.project_service.create_project(
                    db,
                    ProjectCreate(
                        title=derived_title,
                        genre=derived_genre,
                        prompt=build.prompt,
                        status="PLAYABLE",
                        parameters=params,
                        designSpec=result.design_spec.model_dump() if result.design_spec else None,
                        gameDsl=result.dsl.model_dump(),
                        runtimeMetadata=runtime_meta,
                    ),
                    user_id=user_id,
                )

                # Atomic conditional transition to SUCCESS
                success_transition = self.repo.transition_status(
                    db=db,
                    build_id=build_id,
                    from_statuses=["RUNNING", "VALIDATING"],
                    to_status="SUCCESS",
                    completed_at=now,
                    project_id=project_res.id,
                    game_dsl=result.dsl.model_dump(),
                )

                if not success_transition:
                    # Concurrently cancelled at the exact moment of project creation!
                    # Clean up project to prevent orphaned projects on cancelled builds
                    if user_id:
                        try:
                            self.project_service.delete_project(db, project_res.id, user_id=user_id)
                        except Exception:
                            pass
                    return

                await self.broadcaster.broadcast(
                    build_id,
                    "status",
                    {
                        "build_id": build_id,
                        "status": "SUCCESS",
                        "project_id": project_res.id,
                    },
                )
            else:
                self.repo.transition_status(
                    db=db,
                    build_id=build_id,
                    from_statuses=["RUNNING", "VALIDATING"],
                    to_status="ERROR",
                    completed_at=now,
                    error_code=result.error_code or "GENERATION_FAILED",
                    error_message=result.error_message or "Game generation failed.",
                )
                await self.broadcaster.broadcast(
                    build_id,
                    "status",
                    {
                        "build_id": build_id,
                        "status": "ERROR",
                        "error_code": result.error_code or "GENERATION_FAILED",
                        "error_message": result.error_message or "Game generation failed.",
                    },
                )

        except asyncio.CancelledError:
            # Build was cancelled by user
            try:
                self.repo.transition_status(
                    db=db,
                    build_id=build_id,
                    from_statuses=["QUEUED", "RUNNING", "VALIDATING"],
                    to_status="CANCELLED",
                    completed_at=datetime.now(timezone.utc),
                    error_code="BUILD_CANCELLED",
                    error_message="Build cancelled by user.",
                )
            except Exception:
                pass
            raise
        except Exception as e:
            # Fatal unhandled error handling
            try:
                self.repo.transition_status(
                    db=db,
                    build_id=build_id,
                    from_statuses=["QUEUED", "RUNNING", "VALIDATING"],
                    to_status="ERROR",
                    completed_at=datetime.now(timezone.utc),
                    error_code="INTERNAL_BUILD_ERROR",
                    error_message=str(e),
                )
                await self.broadcaster.broadcast(
                    build_id,
                    "status",
                    {
                        "build_id": build_id,
                        "status": "ERROR",
                        "error_code": "INTERNAL_BUILD_ERROR",
                        "error_message": str(e),
                    },
                )
            except Exception:
                pass
        finally:
            self._running_builds.discard(build_id)
            self._active_tasks.pop(build_id, None)
            db.close()

    async def stream_events(
        self, build_id: str, user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        SSE Generator that yields historical persisted events first,
        then live streamed events until terminal state (SUCCESS / ERROR / CANCELLED).

        Subscribes to live events FIRST to guarantee zero event loss between
        persisted log retrieval and live streaming.
        """
        queue = await self.broadcaster.add_subscriber(build_id)
        last_seq = 0

        try:
            db: Session = self.session_factory()
            try:
                build = self.repo.get_build_by_id(db, build_id)
                if not build:
                    raise BuildNotFoundError(build_id)
                if user_id is not None and build.user_id != user_id:
                    raise BuildNotFoundError(build_id)

                # Replay initial status
                yield f"event: status\ndata: {json.dumps({'build_id': build_id, 'status': build.status})}\n\n"

                # Replay historical logs from database
                persisted_logs = self.repo.get_logs(db, build_id)
                for log in persisted_logs:
                    last_seq = max(last_seq, log.sequence_number)
                    payload = {
                        "sequence": log.sequence_number,
                        "level": log.level,
                        "message": log.message,
                        "timestamp": log.timestamp.isoformat(),
                    }
                    yield f"event: log\ndata: {json.dumps(payload)}\n\n"

                # If already terminal at subscription time, yield terminal event and close
                if build.status in ("SUCCESS", "ERROR", "CANCELLED"):
                    terminal_data = {"build_id": build_id, "status": build.status}
                    if build.project_id:
                        terminal_data["project_id"] = build.project_id
                    if build.error_code:
                        terminal_data["error_code"] = build.error_code
                    if build.error_message:
                        terminal_data["error_message"] = build.error_message
                    yield f"event: status\ndata: {json.dumps(terminal_data)}\n\n"
                    return
            finally:
                db.close()

            # Stream live events from the queue (deduplicating anything <= last_seq)
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Keep-alive comment ping
                    yield ": keep-alive\n\n"
                    continue

                event_type = event["event"]
                data = event["data"]

                # Deduplicate logs that were already replayed
                if event_type == "log" and data.get("sequence", 0) <= last_seq:
                    continue

                if event_type == "log" and "sequence" in data:
                    last_seq = max(last_seq, data["sequence"])

                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

                # Terminal status event ends the SSE stream
                if event_type == "status" and data.get("status") in ("SUCCESS", "ERROR", "CANCELLED"):
                    break
        finally:
            await self.broadcaster.remove_subscriber(build_id, queue)


build_service = BuildService()
