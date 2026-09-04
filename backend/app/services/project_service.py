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
    CompileProjectRequest,
    CompileProjectResponse,
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
from app.schemas.blueprint import GameBlueprint
from app.schemas.remix import RemixApplyRequest, RemixApplyResponse, REMIX_INTENT_LABELS
from app.schemas.design_spec import GameDesignSpec
from app.generation.dsl_models import GameDSL
from app.generation.validator import validate_game_dsl
from app.generation.blueprint import build_game_blueprint
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
            scale=project.scale or "standard",
            worldMode=project.world_mode or "linear",
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
            scale=data.parameters.scale,
            world_mode=data.parameters.world_mode,
            design_spec=data.design_spec,
            game_dsl=data.game_dsl,
            runtime_metadata=data.runtime_metadata,
            current_version=data.current_version or 1,
        )
        db.add(project)
        db.flush()

        # If game_dsl or design_spec was omitted, generate starter deterministic blueprint
        if not project.game_dsl or not project.design_spec:
            from app.services.game_generation_service import game_generation_service
            fallback = game_generation_service._build_deterministic_fallback(
                prompt=project.prompt,
                contract=None,
                engine=project.engine,
                scale=project.scale or "standard",
                world_mode=project.world_mode or "linear",
                modules=project.modules or [],
            )
            if not project.design_spec:
                project.design_spec = fallback.get("design_spec")
            if not project.game_dsl:
                project.game_dsl = fallback.get("dsl")

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

    def delete_project(
        self, db: Session, project_id: str, user_id: Optional[str] = None
    ) -> None:
        """
        Permanently delete an owned project.

        CASCADE constraints on project_versions and playtest_sessions handle
        their dependent rows automatically.  build_jobs.project_id is a plain
        string reference (no FK), so those audit records are intentionally
        retained as build history and do NOT create orphan rows in the
        relational sense.
        """
        project = self._get_owned_project(db, project_id, user_id)
        self.repo.delete(db, project)

    def duplicate_project(
        self, db: Session, project_id: str, user_id: Optional[str] = None
    ) -> ProjectResponse:
        """
        Create an independent copy of an existing project.

        The duplicate:
          - Inherits the current playable configuration (engine, scale, world_mode,
            art_density, physics, modules, prompt, genre, title + " (Copy)") and
            the latest design_spec and game_dsl so it is immediately playable.
          - Starts with a fresh version history (v1 only, new ProjectVersion row).
          - Gets its own new UUID.
          - Does NOT inherit playtest_sessions, build_jobs, or telemetry/analysis
            records — those are runtime/session history tied to the original.
          - Has status PLAYABLE if original has a game_dsl; otherwise PLAYABLE with
            no DSL (the project row is still valid; just needs a new build).
        """
        original = self._get_owned_project(db, project_id, user_id)

        copy = Project(
            user_id=user_id,
            title=f"{original.title} (Copy)",
            genre=original.genre,
            prompt=original.prompt,
            status="PLAYABLE",
            engine=original.engine,
            art_density=original.art_density,
            physics=original.physics,
            modules=list(original.modules) if original.modules else [],
            scale=original.scale or "standard",
            world_mode=original.world_mode or "linear",
            # Snapshot current playable design artifacts.
            design_spec=original.design_spec,
            game_dsl=original.game_dsl,
            runtime_metadata=original.runtime_metadata,
            current_version=1,
        )
        db.add(copy)
        db.flush()  # Assign copy.id before creating the v1 version record.

        # Create a fresh v1 ProjectVersion for the duplicate.
        if copy.game_dsl:
            v1 = ProjectVersion(
                project_id=copy.id,
                version_number=1,
                game_dsl=copy.game_dsl,
                design_spec=copy.design_spec,
                change_summary="Duplicated from project '{}'.".format(original.title),
            )
            db.add(v1)

        db.commit()
        db.refresh(copy)
        return self.to_response(copy)

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
                project.scale = params.scale
                project.world_mode = params.world_mode
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

    def _format_playtest_response(self, session: PlaytestSession) -> PlaytestSessionResponse:
        """Helper to serialize PlaytestSession with version_number metadata."""
        resp = PlaytestSessionResponse.model_validate(session)
        ver = None
        if session.ai_analysis and isinstance(session.ai_analysis, dict):
            ver = session.ai_analysis.get("version_number")
        resp.version_number = ver or 1
        return resp

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

        target_version = (
            data.version_number
            if (data.version_number and data.version_number >= 1)
            else (project.current_version or 1)
        )
        initial_analysis = {"version_number": target_version}

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
            ai_analysis=initial_analysis,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return self._format_playtest_response(session)

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
        return self._format_playtest_response(session)

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
        return [self._format_playtest_response(s) for s in sessions]

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
            cur_ver = 1
            if target_session.ai_analysis and isinstance(target_session.ai_analysis, dict):
                cur_ver = target_session.ai_analysis.get("version_number", project.current_version or 1)
            else:
                cur_ver = project.current_version or 1
            analysis_data = validated.model_dump()
            analysis_data["version_number"] = cur_ver
            target_session.ai_analysis = analysis_data
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

        current_ver_num = project.current_version or 1

        # 1. Optimistic Locking Base Version Check
        if data.base_version_number is not None and data.base_version_number != current_ver_num:
            raise ValueError(
                f"Stale analysis conflict: Project is at version {current_ver_num}, "
                f"but recommendation was requested for base version {data.base_version_number}."
            )

        # 2. Session Staleness Check
        source_session = None
        if data.session_id:
            source_session = (
                db.query(PlaytestSession)
                .filter(
                    PlaytestSession.id == data.session_id,
                    PlaytestSession.project_id == project.id,
                    PlaytestSession.user_id == user_id,
                )
                .first()
            )
            if not source_session:
                raise PlaytestNotFoundError(data.session_id)

            session_ver = None
            if source_session.ai_analysis and isinstance(source_session.ai_analysis, dict):
                session_ver = source_session.ai_analysis.get("version_number")

            current_ver_rec = (
                db.query(ProjectVersion)
                .filter(
                    ProjectVersion.project_id == project.id,
                    ProjectVersion.version_number == current_ver_num,
                )
                .first()
            )
            if session_ver is not None and session_ver != current_ver_num:
                raise ValueError(
                    f"Stale analysis conflict: Playtest session was recorded for version {session_ver}, "
                    f"which is stale relative to current version {current_ver_num}."
                )
            if current_ver_rec and source_session.created_at and source_session.created_at < current_ver_rec.created_at:
                raise ValueError(
                    f"Stale analysis conflict: Playtest session was recorded prior to current version {current_ver_num}."
                )

        current_dsl = project.game_dsl
        design_spec = project.design_spec or {"title": project.title, "genre": project.genre}

        # Filter and track actionable field-level changes
        from app.schemas.improvement import ImprovementFieldChange
        changes: List[ImprovementFieldChange] = []
        actionable_recs = []

        for rec in data.selected_recommendations:
            patch = rec.get("suggested_patch", {})
            rec_id = rec.get("id", "rec")
            rec_desc = rec.get("description", "")
            if isinstance(patch, dict) and patch:
                actionable_recs.append(rec)
                for top_k, top_v in patch.items():
                    if isinstance(top_v, dict) and isinstance(current_dsl.get(top_k), dict):
                        for sub_k, sub_v in top_v.items():
                            prev_v = current_dsl.get(top_k, {}).get(sub_k)
                            changes.append(
                                ImprovementFieldChange(
                                    fieldName=f"{top_k}.{sub_k}",
                                    previousValue=prev_v,
                                    newValue=sub_v,
                                    recommendationId=rec_id,
                                    description=rec_desc,
                                )
                            )
                    else:
                        prev_v = current_dsl.get(top_k)
                        changes.append(
                            ImprovementFieldChange(
                                fieldName=top_k,
                                previousValue=prev_v,
                                newValue=top_v,
                                recommendationId=rec_id,
                                description=rec_desc,
                            )
                        )

        result = await game_generation_service.apply_improvements(
            current_dsl=current_dsl,
            design_spec=design_spec,
            selected_recommendations=actionable_recs if actionable_recs else data.selected_recommendations,
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
        new_version_num = max(max_v or 0, current_ver_num) + 1
        new_dsl_dict = result.dsl.model_dump()

        source_info = (
            f"Playtest improvement (session {data.session_id} v{current_ver_num})"
            if data.session_id
            else f"Playtest improvement (v{current_ver_num})"
        )
        recs_summary = "; ".join(r.get("description", "Improvement applied") for r in data.selected_recommendations)
        change_desc = f"{source_info}: {recs_summary}"
        if data.user_notes:
            change_desc += f" [Notes: {data.user_notes}]"

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
            projectId=project.id,
            previousVersionNumber=current_ver_num,
            newVersionNumber=new_version_num,
            version_number=new_version_num,
            gameDsl=new_dsl_dict,
            designSpec=project.design_spec,
            changeSummary=change_desc,
            changes=changes,
            sourceSessionId=data.session_id,
            status="SUCCESS",
            message=f"Playtest improvements applied successfully as version {new_version_num}.",
        )

    def get_project_blueprint(
        self,
        db: Session,
        project_id: str,
        user_id: str,
    ) -> GameBlueprint:
        """Derive and return the nontechnical-friendly Game Blueprint for an owned project."""
        project = self._get_owned_project(db, project_id, user_id)

        if not project.game_dsl:
            raise ValueError("Project has no generated Game DSL yet.")

        dsl_val = validate_game_dsl(project.game_dsl)
        if not dsl_val.is_valid or not dsl_val.dsl:
            raise ValueError("Stored Game DSL failed validation; cannot derive blueprint.")

        design_spec_obj: Optional[GameDesignSpec] = None
        spec_source = project.design_spec or (
            project.game_dsl.get("design_spec") if isinstance(project.game_dsl, dict) else None
        )
        if spec_source:
            try:
                design_spec_obj = GameDesignSpec.model_validate(spec_source)
            except Exception:
                design_spec_obj = None

        return build_game_blueprint(project.id, dsl_val.dsl, design_spec_obj)

    async def apply_project_remix(
        self,
        db: Session,
        project_id: str,
        user_id: str,
        data: RemixApplyRequest,
    ) -> RemixApplyResponse:
        """Apply structured remix intents to create a new versioned project remix."""
        project = self._get_owned_project(db, project_id, user_id)

        if not project.game_dsl:
            raise ValueError("Cannot remix a project without existing Game DSL.")

        current_dsl = project.game_dsl
        design_spec = project.design_spec or {"title": project.title, "genre": project.genre}

        personalization = None
        try:
            from app.services.preference_service import preference_service
            personalization = preference_service.get_generation_context(db, user_id)
        except Exception:
            personalization = None

        result = await game_generation_service.apply_remix(
            current_dsl=current_dsl,
            design_spec=design_spec,
            intents=[i.model_dump(mode="json") for i in data.intents],
            personalization=personalization,
        )

        if not result.success or not result.dsl:
            raise ValueError(f"Remix failed: {result.error_message or 'Invalid DSL'}")

        from sqlalchemy import func
        max_v = (
            db.query(func.max(ProjectVersion.version_number))
            .filter(ProjectVersion.project_id == project.id)
            .scalar()
        )
        new_version_num = max(max_v or 0, project.current_version or 0) + 1
        new_dsl_dict = result.dsl.model_dump()
        new_spec_dict = result.design_spec.model_dump() if result.design_spec else project.design_spec

        intent_labels = ", ".join(REMIX_INTENT_LABELS.get(i.type.value, i.type.value) for i in data.intents)
        change_desc = f"Remix applied: {intent_labels}."
        clamp_note = result.provider_meta.get("remix_clamped_note") if result.provider_meta else None
        if clamp_note:
            change_desc = f"{change_desc} {clamp_note}"

        project.game_dsl = new_dsl_dict
        project.design_spec = new_spec_dict
        project.current_version = new_version_num
        project.updated_at = datetime.now(timezone.utc)

        version_rec = ProjectVersion(
            project_id=project.id,
            version_number=new_version_num,
            game_dsl=new_dsl_dict,
            design_spec=new_spec_dict,
            change_summary=change_desc,
            remix_intent=[i.model_dump(mode="json") for i in data.intents],
        )
        db.add(version_rec)
        db.commit()
        db.refresh(project)

        blueprint = build_game_blueprint(
            project.id,
            GameDSL.model_validate(new_dsl_dict),
            GameDesignSpec.model_validate(new_spec_dict) if new_spec_dict else None,
        )

        return RemixApplyResponse(
            project_id=project.id,
            version_number=new_version_num,
            game_dsl=new_dsl_dict,
            design_spec=new_spec_dict,
            blueprint=blueprint,
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
                "remix_intent": v.remix_intent,
            }
            for v in versions
        ]

    def restore_project_version(
        self,
        db: Session,
        project_id: str,
        user_id: str,
        target_version_number: int,
    ) -> ProjectResponse:
        """
        Restore a historical ProjectVersion into a new immutable forward version (vN+1).

        Guarantees:
          - Immutable history: target version is never modified.
          - Clean provenance: remix_intent is reset to None, change_summary records the restore source.
          - Concurrency-safe forward version allocation: calculates candidate next version
            and commits atomically within transaction.
        """
        from sqlalchemy import func
        from sqlalchemy.exc import IntegrityError

        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                project = self._get_owned_project(db, project_id, user_id)

                target_version = (
                    db.query(ProjectVersion)
                    .filter(
                        ProjectVersion.project_id == project_id,
                        ProjectVersion.version_number == target_version_number,
                    )
                    .first()
                )
                if not target_version:
                    raise ValueError(f"Version {target_version_number} not found for project '{project_id}'.")

                # Query highest recorded version number for this project within transaction
                max_v = (
                    db.query(func.max(ProjectVersion.version_number))
                    .filter(ProjectVersion.project_id == project.id)
                    .scalar()
                )
                new_version_num = max(max_v or 0, project.current_version or 0) + 1

                project.game_dsl = target_version.game_dsl
                project.design_spec = target_version.design_spec
                project.current_version = new_version_num
                project.updated_at = datetime.now(timezone.utc)

                new_version_rec = ProjectVersion(
                    project_id=project.id,
                    version_number=new_version_num,
                    game_dsl=target_version.game_dsl,
                    design_spec=target_version.design_spec,
                    change_summary=f"Restored from version {target_version_number}.",
                    remix_intent=None,
                )
                db.add(new_version_rec)
                db.commit()
                db.refresh(project)
                return self.to_response(project)
            except IntegrityError:
                db.rollback()
                db.expire_all()
                if attempt == max_attempts - 1:
                    raise

    def compile_project_version(
        self,
        db: Session,
        project_id: str,
        user_id: str,
        version_number: Optional[int] = None,
    ) -> CompileProjectResponse:
        """
        Deterministically compile an active or historical project version into a validated playable Phaser prototype.

        Guarantees:
          - IDOR safe: requester must own the project.
          - Authoritative version resolution: resolves requested version or active project.current_version.
          - Immutability: strictly read-only on ProjectVersion history (does NOT mutate historical rows).
          - Parameter propagation: applies engine, physics, art density, world mode, modules, and theme to DSL.
          - Runtime compatibility validation: verifies Phaser 3.88.2 renderer boundaries and capability matrix.
          - Deterministic execution: 0 Gemini / 0 external LLM calls.
        """
        project = self._get_owned_project(db, project_id, user_id)

        target_version_num = version_number if version_number is not None else (project.current_version or 1)

        # Look up target version record in database
        version_row = (
            db.query(ProjectVersion)
            .filter(
                ProjectVersion.project_id == project_id,
                ProjectVersion.version_number == target_version_num,
            )
            .first()
        )

        if version_number is not None and not version_row:
            raise ValueError(f"Version {version_number} not found for project '{project_id}'.")

        if version_row and version_row.game_dsl:
            raw_dsl = version_row.game_dsl
            raw_spec = version_row.design_spec or project.design_spec
        else:
            raw_dsl = project.game_dsl
            raw_spec = project.design_spec

        if not raw_dsl or not isinstance(raw_dsl, dict):
            raise ValueError(f"Project version {target_version_num} has no generated Game DSL to compile.")

        # Deepen & propagate build parameters deterministically
        if target_version_num == project.current_version:
            engine = project.engine or raw_dsl.get("metadata", {}).get("archetype") or "Top-Down Action"
            art_density = project.art_density if project.art_density is not None else 50
            physics = project.physics if project.physics is not None else 80
            modules = project.modules if isinstance(project.modules, list) else []
            world_mode = project.world_mode
            scale = project.scale
        else:
            # For historical versions, preserve that specific version's archetype and world settings
            engine = raw_dsl.get("metadata", {}).get("archetype") or project.engine or "Top-Down Action"
            art_density = 50
            physics = 80
            modules = []
            world_mode = raw_dsl.get("world", {}).get("world_mode") or project.world_mode
            scale = raw_dsl.get("world", {}).get("scale") or project.scale

        compiled_dict = game_generation_service._compile_and_propagate_parameters(
            dsl_dict=raw_dsl,
            spec_dict=raw_spec,
            engine=engine,
            art_density=art_density,
            physics=physics,
            modules=modules,
        )

        if world_mode and world_mode in ("linear", "campaign", "open_world"):
            compiled_dict.setdefault("world", {})["world_mode"] = world_mode

        # Schema validation
        dsl_val = validate_game_dsl(compiled_dict)
        if not dsl_val.is_valid or not dsl_val.dsl:
            raise ValueError(f"Compiled Game DSL failed validation: {'; '.join(dsl_val.errors)}")

        # Runtime compatibility checks for Phaser
        from app.runtime.compatibility import RuntimeCompatibilityValidator
        compat = RuntimeCompatibilityValidator.validate(dsl_val.dsl)
        if not compat.compatible:
            raise ValueError(f"Phaser runtime compatibility validation failed: {'; '.join(compat.errors)}")

        # Deterministic runtime metadata generation with version traceability
        from app.runtime.metadata import generate_runtime_metadata
        seed_source = f"{project.id}_v{target_version_num}"
        runtime_meta = generate_runtime_metadata(seed_source=seed_source)
        runtime_meta["version_number"] = target_version_num
        runtime_meta["project_id"] = project.id
        if project.runtime_metadata and isinstance(project.runtime_metadata, dict):
            if "provider" in project.runtime_metadata:
                runtime_meta["provider"] = project.runtime_metadata["provider"]
            if "model" in project.runtime_metadata:
                runtime_meta["model"] = project.runtime_metadata["model"]

        # If compiling current active version, sync runtime_metadata and updated_at
        if target_version_num == project.current_version:
            project.runtime_metadata = runtime_meta
            project.updated_at = datetime.now(timezone.utc)
            db.commit()

        return CompileProjectResponse(
            projectId=project.id,
            versionNumber=target_version_num,
            status="SUCCESS",
            gameDsl=compiled_dict,
            designSpec=raw_spec,
            runtimeMetadata=runtime_meta,
            validationSummary={
                "isValid": True,
                "archetype": compat.archetype,
                "warnings": compat.warnings,
                "entitiesCount": len(dsl_val.dsl.entities),
                "rulesCount": len(dsl_val.dsl.rules),
            },
            compiledAt=datetime.now(timezone.utc),
            message=f"Prototype for version {target_version_num} compiled and validated successfully.",
        )


project_service = ProjectService()

