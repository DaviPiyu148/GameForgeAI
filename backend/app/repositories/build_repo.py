"""
Data access repository for BuildJob and BuildLog entities.
Provides atomic conditional state transitions, monotonic sequence-safe logging,
orphan reconciliation, and duplicate build submission queries.
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.build import BuildJob
from app.models.build_log import BuildLog


class BuildRepository:
    """Data access repository for BuildJob and BuildLog entities."""

    def create_build(self, db: Session, build: BuildJob) -> BuildJob:
        """Persist a new build job."""
        db.add(build)
        db.commit()
        db.refresh(build)
        return build

    def get_build_by_id(self, db: Session, build_id: str) -> Optional[BuildJob]:
        """Find a build job by primary key ID."""
        return db.query(BuildJob).filter(BuildJob.id == build_id).first()

    def update_build(self, db: Session, build: BuildJob) -> BuildJob:
        """Commit updates to an existing build job."""
        db.commit()
        db.refresh(build)
        return build

    def transition_status(
        self,
        db: Session,
        build_id: str,
        from_statuses: List[str],
        to_status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        project_id: Optional[str] = None,
        game_dsl: Optional[dict] = None,
    ) -> bool:
        """
        Atomically transition a build job from one of `from_statuses` to `to_status`.
        Uses a conditional UPDATE:
          UPDATE build_jobs SET status=:to_status, ...
          WHERE id=:build_id AND status IN (:from_statuses)

        Returns True if exactly 1 row was updated, False if no row matched
        (e.g., due to a concurrent state transition to a terminal state).
        """
        values = {"status": to_status}
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at
        if error_code is not None:
            values["error_code"] = error_code
        if error_message is not None:
            values["error_message"] = error_message
        if project_id is not None:
            values["project_id"] = project_id
        if game_dsl is not None:
            values["game_dsl"] = game_dsl

        updated_count = (
            db.query(BuildJob)
            .filter(BuildJob.id == build_id, BuildJob.status.in_(from_statuses))
            .update(values, synchronize_session="fetch")
        )
        db.commit()
        return updated_count == 1

    def append_log(
        self,
        db: Session,
        build_id: str,
        level: str,
        message: str,
        timestamp: Optional[datetime] = None,
    ) -> BuildLog:
        """
        Safely append a log entry with monotonic sequence allocation.
        Retries on sequence collision race under high concurrency.
        """
        ts = timestamp or datetime.now(timezone.utc)
        for attempt in range(5):
            try:
                max_seq = (
                    db.query(func.max(BuildLog.sequence_number))
                    .filter(BuildLog.build_id == build_id)
                    .scalar()
                )
                next_seq = (max_seq or 0) + 1
                log = BuildLog(
                    build_id=build_id,
                    sequence_number=next_seq,
                    level=level,
                    message=message,
                    timestamp=ts,
                )
                db.add(log)
                db.commit()
                return log
            except IntegrityError:
                db.rollback()
                if attempt == 4:
                    raise
        raise RuntimeError(f"Failed to allocate unique sequence number for build '{build_id}'.")

    def add_log(self, db: Session, log: BuildLog) -> BuildLog:
        """Persist a new build log entry (backward-compatible)."""
        db.add(log)
        db.commit()
        return log

    def get_logs(
        self, db: Session, build_id: str, after_sequence: int = 0
    ) -> List[BuildLog]:
        """Retrieve all logs for a build in ascending sequence order."""
        return (
            db.query(BuildLog)
            .filter(
                BuildLog.build_id == build_id,
                BuildLog.sequence_number > after_sequence,
            )
            .order_by(BuildLog.sequence_number.asc())
            .all()
        )

    def get_next_sequence(self, db: Session, build_id: str) -> int:
        """Get the next 1-based sequence number for a build's logs."""
        max_seq = (
            db.query(func.max(BuildLog.sequence_number))
            .filter(BuildLog.build_id == build_id)
            .scalar()
        )
        return (max_seq or 0) + 1

    def find_active_duplicate_build(
        self,
        db: Session,
        user_id: Optional[str],
        prompt: str,
        engine: str,
        art_density: int,
        physics: int,
        scale: str = "standard",
        world_mode: str = "linear",
    ) -> Optional[BuildJob]:
        """
        Find an existing active (QUEUED/RUNNING/VALIDATING) build submitted by the same user
        with matching prompt and build parameters to prevent duplicate double-click submissions.
        """
        if not user_id:
            return None
        resolved_scale = scale or "standard"
        resolved_world_mode = world_mode or "linear"
        return (
            db.query(BuildJob)
            .filter(
                BuildJob.user_id == user_id,
                BuildJob.prompt == prompt,
                BuildJob.engine == engine,
                BuildJob.art_density == art_density,
                BuildJob.physics == physics,
                BuildJob.scale == resolved_scale,
                BuildJob.world_mode == resolved_world_mode,
                BuildJob.status.in_(["QUEUED", "RUNNING", "VALIDATING"]),
            )
            .first()
        )

    def reconcile_orphaned_builds(self, db: Session) -> int:
        """
        On server startup, sweep the database for builds stuck in non-terminal states
        (QUEUED, RUNNING, VALIDATING) from prior dead worker processes and transition
        them to ERROR with error_code='ORPHANED_BUILD'.
        Returns count of reconciled builds.
        """
        now = datetime.now(timezone.utc)
        count = (
            db.query(BuildJob)
            .filter(BuildJob.status.in_(["QUEUED", "RUNNING", "VALIDATING"]))
            .update(
                {
                    "status": "ERROR",
                    "error_code": "ORPHANED_BUILD",
                    "error_message": "Build interrupted by server restart or worker termination.",
                    "completed_at": now,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        return count


build_repository = BuildRepository()
