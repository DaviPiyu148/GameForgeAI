"""
Project and Playtest business logic service with strict ownership enforcement.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.playtest import PlaytestSession
from app.models.project_version import ProjectVersion
from app.repositories.project_repo import ProjectRepository, project_repository
from app.schemas.project import (
    BuildParams,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.playtest import (
    PlaytestCreate,
    PlaytestSessionResponse,
    PlaytestAnalysisResponse,
)
from app.schemas.improvement import (
    ImprovementApplyRequest,
    ImprovementApplyResponse,
)
from app.services.game_generation_service import game_generation_service


class ProjectNotFoundError(Exception):
    """Raised when a requested project does not exist OR the requester is not the owner."""
    def __init__(self, project_id: str):
        self.project_id = project_id
        super().__init__(f"Project with ID '{project_id}' not found.")


class PlaytestNotFoundError(Exception):
    """Raised when a requested playtest session does not exist OR ownership mismatch."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Playtest session with ID '{session_id}' not found.")


class ProjectService:
    """Business logic service for Project and Playtest operations with ownership enforcement."""

    def _get_owned_project(
        self, db: Session, project_id: str, user_id: Optional[str]
    ) -> Project:
        """
        Fetch a project by id, enforcing IDOR-safe ownership: raises ProjectNotFoundError
        (never a distinguishable 403) if the project doesn't exist, or if `user_id` is
        provided and doesn't match `project.user_id`. `user_id=None` skips the ownership
        check (used by internal/no-auth-context call sites). Centralizes the
        get-then-check idiom previously duplicated across this service's methods, so a
        future change to this check (e.g. audit logging) only needs to be made once.
        """
        project = self.repo.get_by_id(db, project_id)
        if not project:
            raise ProjectNotFoundError(project_id)
        if user_id is not None and project.user_id != user_id:
            raise ProjectNotFoundError(project_id)
        return project

    def __init__(self, repo: ProjectRepository = project_repository):
        self.repo = repo

    def to_response(self, project: Project) -> ProjectResponse:
        """Convert a Project ORM instance to a ProjectResponse schema."""
        now = datetime.now(timezone.utc)
        updated_at = project.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        delta = (now - updated_at).total_seconds()
        if delta < 60:
            last_modified = "Just now"
        elif delta < 3600:
            mins = int(delta // 60)
            last_modified = f"{mins}m ago"
        elif delta < 86400:
            hours = int(delta // 3600)
            last_modified = f"{hours}h ago"
        else:
            last_modified = updated_at.strftime("%b %d, %Y")

        params = BuildParams(
            engine=project.engine,
            artDensity=project.art_density,
            physics=project.physics,
            modules=project.modules if isinstance(project.modules, list) else [],
        )

        return ProjectResponse(
            id=project.id,
            title=project.title,
            genre=project.genre,
            status=project.status,
            lastModified=last_modified,
            parameters=params,
            prompt=project.prompt,
            designSpec=project.design_spec,
            gameDsl=project.game_dsl,
            runtimeMetadata=project.runtime_metadata,
            currentVersion=project.current_version or 1,
            createdAt=project.created_at,
            updatedAt=project.updated_at,
        )

    def create_project(
        self, db: Session, data: ProjectCreate, user_id: Optional[str] = None
    ) -> ProjectResponse:
        """
        Create and persist a new project record and its initial version (v1).
        """
        project = Project(
            user_id=user_id,
            title=data.title.strip(),
            genre=data.genre.strip() if data.genre else "Generated Concept",
            prompt=data.prompt.strip(),
            status=data.status or "PLAYABLE",
            engine=data.parameters.engine,
            art_density=data.parameters.art_density,
            physics=data.parameters.physics,
            modules=data.parameters.modules,
            design_spec=data.design_spec,
            game_dsl=data.game_dsl,
            runtime_metadata=data.runtime_metadata,
            current_version=data.current_version or 1,
        )
        db.add(project)
        db.flush()

        # Create initial ProjectVersion (v1) record atomically in the same transaction
        if project.game_dsl:
            v1 = ProjectVersion(
                project_id=project.id,
                version_number=1,
                game_dsl=project.game_dsl,
                design_spec=project.design_spec,
                change_summary="Initial prototype generated from prompt.",
            )
            db.add(v1)

        db.commit()
        db.refresh(project)
        return self.to_response(project)

    def get_project(
        self, db: Session, project_id: str, user_id: Optional[str] = None
    ) -> ProjectResponse:
        """
        Retrieve a single project by ID with IDOR protection.
        """
        project = self._get_owned_project(db, project_id, user_id)
        return self.to_response(project)

    def list_projects(
        self,
        db: Session,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProjectResponse]:
        """List projects owned by user."""
        projects = self.repo.list(db, limit=limit, offset=offset, user_id=user_id)
        return [self.to_response(p) for p in projects]

    def update_project(
        self, db: Session, project_id: str, data: ProjectUpdate, user_id: Optional[str] = None
    ) -> ProjectResponse:
        """Update permitted editable fields on an existing project with ownership check."""
        project = self._get_owned_project(db, project_id, user_id)

        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return self.to_response(project)

        if "title" in update_dict and update_dict["title"] is not None:
            project.title = update_dict["title"].strip()
        if "genre" in update_dict and update_dict["genre"] is not None:
            project.genre = update_dict["genre"].strip()
        if "prompt" in update_dict and update_dict["prompt"] is not None:
            project.prompt = update_dict["prompt"].strip()
        if "parameters" in update_dict and update_dict["parameters"] is not None:
            params = data.parameters
            if params is not None:
                project.engine = params.engine
                project.art_density = params.art_density
                project.physics = params.physics
                project.modules = params.modules
        if "design_spec" in update_dict and update_dict["design_spec"] is not None:
            project.design_spec = update_dict["design_spec"]
        if "game_dsl" in update_dict and update_dict["game_dsl"] is not None:
            project.game_dsl = update_dict["game_dsl"]
        if "runtime_metadata" in update_dict and update_dict["runtime_metadata"] is not None:
            project.runtime_metadata = update_dict["runtime_metadata"]
        # `current_version` is intentionally NOT client-settable via PATCH: it is not in
        # the documented editable-field contract (docs/08-API-CONTRACT.md) and is an
        # authoritative counter only ever advanced by apply_project_improvement's version
        # bump. Allowing arbitrary client writes here would let it drift out of sync with
        # the real project_versions history with no corresponding version row created.

        project.updated_at = datetime.now(timezone.utc)
        updated = self.repo.update(db, project)
        return self.to_response(updated)

    # -------------------------------------------------------------------------
    # Playtest & Telemetry Management
    # -------------------------------------------------------------------------

    def create_playtest_session(
        self,
        db: Session,
        project_id: str,
        user_id: str,
        data: PlaytestCreate,
    ) -> PlaytestSessionResponse:
        """Create and persist a new playtest session record with deterministic summary aggregation and ownership validation."""
        project = self._get_owned_project(db, project_id, user_id)

        # Deterministic summary calculation from telemetry event stream
        from app.services.playtest_summary import PlaytestSummaryEngine
        summary = PlaytestSummaryEngine.aggregate(
            events=data.telemetry_events,
            declared_duration=data.duration_seconds,
            declared_score=data.score,
            declared_outcome=data.outcome,
        )

        session = PlaytestSession(
            project_id=project_id,
            user_id=user_id,
            duration_seconds=summary["duration_seconds"],
            score=summary["score"],
            damage_taken=summary["damage_taken"],
            damage_dealt=summary["damage_dealt"],
            enemies_defeated=summary["enemies_defeated"],
            collectibles_gathered=summary["collectibles_gathered"],
            objectives_completed=summary["objectives_completed"],
            outcome=summary["outcome"],
            telemetry_events=data.telemetry_events,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return PlaytestSessionResponse.model_validate(session)

    def get_playtest_session(
        self,
        db: Session,
        project_id: str,
        session_id: str,
        user_id: str,
    ) -> PlaytestSessionResponse:
        """Retrieve a specific playtest session with ownership validation."""
        project = self._get_owned_project(db, project_id, user_id)

        session = (
            db.query(PlaytestSession)
            .filter(
                PlaytestSession.id == session_id,
                PlaytestSession.project_id == project_id,
                PlaytestSession.user_id == user_id,
            )
            .first()
        )
        if not session:
            raise PlaytestNotFoundError(session_id)
        return PlaytestSessionResponse.model_validate(session)

    def list_playtest_sessions(
        self,
        db: Session,
        project_id: str,
        user_id: str,
    ) -> List[PlaytestSessionResponse]:
        """List playtests for an owned project."""
        project = self._get_owned_project(db, project_id, user_id)

        sessions = (
            db.query(PlaytestSession)
            .filter(PlaytestSession.project_id == project_id, PlaytestSession.user_id == user_id)
            .order_by(PlaytestSession.created_at.desc())
            .all()
        )
        return [PlaytestSessionResponse.model_validate(s) for s in sessions]

    async def analyze_playtest_session(
        self,
        db: Session,
        project_id: str,
        user_id: str,
        session_id: Optional[str] = None,
        telemetry_payload: Optional[Dict[str, Any]] = None,
    ) -> PlaytestAnalysisResponse:
        """Run AI Playtest Critique on a completed session."""
        project = self._get_owned_project(db, project_id, user_id)

        telemetry: Dict[str, Any] = {}
        target_session = None

        if session_id:
            target_session = (
                db.query(PlaytestSession)
                .filter(
                    PlaytestSession.id == session_id,
                    PlaytestSession.project_id == project_id,
                    PlaytestSession.user_id == user_id,
                )
                .first()
            )
            if not target_session:
                raise PlaytestNotFoundError(session_id)
            telemetry = {
                "duration_seconds": target_session.duration_seconds,
                "score": target_session.score,
                "damage_taken": target_session.damage_taken,
                "damage_dealt": target_session.damage_dealt,
                "enemies_defeated": target_session.enemies_defeated,
                "collectibles_gathered": target_session.collectibles_gathered,
                "objectives_completed": target_session.objectives_completed,
                "outcome": target_session.outcome,
            }
        elif telemetry_payload:
            telemetry = telemetry_payload
        else:
            telemetry = {"duration_seconds": 60, "score": 100, "outcome": "PLAYED"}

        design_spec = project.design_spec or {"title": project.title, "genre": project.genre}
        dsl = project.game_dsl or {}

        analysis_dict = await game_generation_service.analyze_playtest(
            design_spec=design_spec,
            dsl=dsl,
            telemetry=telemetry,
        )

        # Validate BEFORE persisting: a malformed AI response must never be written to
        # the database, even partially. If validation fails here, the exception propagates
        # to a clean error response and target_session.ai_analysis is left untouched.
        validated = PlaytestAnalysisResponse.model_validate(analysis_dict)

        if target_session:
            target_session.ai_analysis = validated.model_dump()
            db.commit()

        return validated

    async def apply_project_improvement(
        self,
        db: Session,
        project_id: str,
        user_id: str,
        data: ImprovementApplyRequest,
    ) -> ImprovementApplyResponse:
        """Apply approved AI playtest recommendations to create a new project version."""
        project = self._get_owned_project(db, project_id, user_id)

        if not project.game_dsl:
            raise ValueError("Cannot improve project without existing Game DSL.")

        current_dsl = project.game_dsl
        design_spec = project.design_spec or {"title": project.title, "genre": project.genre}

        result = await game_generation_service.apply_improvements(
            current_dsl=current_dsl,
            design_spec=design_spec,
            selected_recommendations=data.selected_recommendations,
            user_notes=data.user_notes,
        )

        if not result.success or not result.dsl:
            raise ValueError(f"Improvement patching failed: {result.error_message or 'Invalid DSL'}")

        from sqlalchemy import func
        # Determine next monotonic version number from database history
        max_v = (
            db.query(func.max(ProjectVersion.version_number))
            .filter(ProjectVersion.project_id == project.id)
            .scalar()
        )
        new_version_num = max(max_v or 0, project.current_version or 0) + 1
        new_dsl_dict = result.dsl.model_dump()
        change_desc = "; ".join(
            r.get("description", "Improvement applied") for r in data.selected_recommendations
        )

        project.game_dsl = new_dsl_dict
        project.current_version = new_version_num
        project.updated_at = datetime.now(timezone.utc)

        # Save new ProjectVersion record in the same atomic transaction
        version_rec = ProjectVersion(
            project_id=project.id,
            version_number=new_version_num,
            game_dsl=new_dsl_dict,
            design_spec=project.design_spec,
            change_summary=change_desc,
        )
        db.add(version_rec)
        db.commit()
        db.refresh(project)

        return ImprovementApplyResponse(
            project_id=project.id,
            version_number=new_version_num,
            game_dsl=new_dsl_dict,
            change_summary=change_desc,
            status="SUCCESS",
        )

    def list_project_versions(
        self,
        db: Session,
        project_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """List version history of an owned project."""
        project = self._get_owned_project(db, project_id, user_id)

        versions = (
            db.query(ProjectVersion)
            .filter(ProjectVersion.project_id == project_id)
            .order_by(ProjectVersion.version_number.asc())
            .all()
        )
        return [
            {
                "id": v.id,
                "project_id": v.project_id,
                "version_number": v.version_number,
                "change_summary": v.change_summary,
                "created_at": v.created_at,
                "game_dsl": v.game_dsl,
            }
            for v in versions
        ]


project_service = ProjectService()
