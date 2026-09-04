"""
ProjectInspiration business logic service.

Invariants:
- user_id always verified via project_service._get_owned_project().
- Canonical identity is steam_app_id.
- Server-side catalog lookup is authoritative for the snapshot.
- Duplicate attachments return 409 (ALREADY_INSPIRED).
- Deletion is scoped to the owned project and steam_app_id.
- alignment_reason is derived dynamically, never persisted.
"""
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session

from app.models.project_inspiration import ProjectInspiration
from app.repositories.project_inspiration_repo import (
    ProjectInspirationRepository,
    project_inspiration_repository,
)
from app.schemas.project_inspiration import (
    AttachInspirationRequest,
    ProjectInspirationListResponse,
    ProjectInspirationResponse,
)
from app.services.project_service import project_service, ProjectService

if TYPE_CHECKING:
    from app.services.discovery_service import DiscoveryService

logger = logging.getLogger(__name__)


class DuplicateInspirationError(Exception):
    """Raised when an inspiration is already attached to the project."""


class InspirationNotFoundError(Exception):
    """Raised when an inspiration is not found in the project."""


class ProjectInspirationService:
    """Business logic for managing project inspirations."""

    def __init__(
        self,
        repo: ProjectInspirationRepository = project_inspiration_repository,
        proj_svc: ProjectService = project_service,
        discovery_svc: Optional["DiscoveryService"] = None,
    ) -> None:
        self.repo = repo
        self.proj_svc = proj_svc
        self._discovery_svc = discovery_svc

    def _get_discovery_svc(self) -> "DiscoveryService":
        """Lazy-load discovery service to avoid circular imports."""
        if self._discovery_svc is None:
            from app.services.discovery_service import discovery_service
            self._discovery_svc = discovery_service
        return self._discovery_svc

    def _resolve_game_snapshot(self, steam_app_id: str) -> Dict[str, Any]:
        """
        Resolve minimal game snapshot metadata authoritative from catalog.
        Falls back gracefully if catalog is not loaded (e.g. lightweight test environments).
        """
        try:
            game = self._get_discovery_svc().get_game_by_steam_id(steam_app_id)
            if game:
                title = game.get("display_title") or game.get("title") or f"Game {steam_app_id}"
                hero = (
                    game.get("hero_image_url")
                    or game.get("cover_image_url")
                    or (game.get("enrichment") or {}).get("cover_url")
                    or f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{steam_app_id}/header.jpg"
                )
                raw_genres = game.get("display_genres") or game.get("genres") or []
                genres = [str(g).strip() for g in raw_genres if str(g).strip()]

                raw_tags = game.get("display_tags") or game.get("tags") or []
                tags = [str(t).strip() for t in raw_tags if str(t).strip()][:10]

                raw_modes = game.get("player_modes") or []
                player_modes = [str(m).strip() for m in raw_modes if str(m).strip()]

                return {
                    "title": title,
                    "cover_url": hero,
                    "genres": genres,
                    "tags": tags,
                    "player_modes": player_modes,
                }
        except Exception as e:
            logger.warning("ProjectInspirationService: catalog lookup failed for %s: %s", steam_app_id, e)

        # Fallback for catalog-absent environments (e.g. fast unit testing)
        return {
            "title": f"Game {steam_app_id}",
            "cover_url": f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{steam_app_id}/header.jpg",
            "genres": [],
            "tags": [],
            "player_modes": [],
        }

    def _to_response(self, record: ProjectInspiration) -> ProjectInspirationResponse:
        """Convert ORM record to Pydantic response schema."""
        return ProjectInspirationResponse(
            id=record.id,
            projectId=record.project_id,
            steamAppId=record.steam_app_id,
            title=record.title,
            coverUrl=record.cover_url,
            genres=record.genres if isinstance(record.genres, list) else [],
            tags=record.tags if isinstance(record.tags, list) else [],
            playerModes=record.player_modes if isinstance(record.player_modes, list) else [],
            createdAt=record.created_at,
        )

    def attach_inspiration(
        self,
        db: Session,
        project_id: str,
        user_id: Optional[str],
        data: AttachInspirationRequest,
    ) -> ProjectInspirationResponse:
        """
        Attach a game as inspiration to an owned project.
        Saves an immutable snapshot of the game metadata.
        """
        # 1. Enforce ownership and project existence
        self.proj_svc._get_owned_project(db, project_id, user_id=user_id)

        steam_app_id = data.steam_app_id.strip()

        # 2. Check for duplicate pre-condition
        existing = self.repo.get_by_project_and_game(db, project_id, steam_app_id)
        if existing:
            raise DuplicateInspirationError(
                f"Game '{steam_app_id}' is already attached as inspiration to project '{project_id}'."
            )

        # 3. Resolve snapshot authoritative server-side
        snapshot = self._resolve_game_snapshot(steam_app_id)

        record = ProjectInspiration(
            project_id=project_id,
            steam_app_id=steam_app_id,
            title=snapshot["title"],
            cover_url=snapshot["cover_url"],
            genres=snapshot["genres"],
            tags=snapshot["tags"],
            player_modes=snapshot["player_modes"],
        )

        try:
            created = self.repo.create(db, record)
            return self._to_response(created)
        except (IntegrityError, InvalidRequestError):
            db.rollback()
            raise DuplicateInspirationError(
                f"Game '{steam_app_id}' is already attached as inspiration to project '{project_id}'."
            )

    def list_inspirations(
        self,
        db: Session,
        project_id: str,
        user_id: Optional[str],
    ) -> ProjectInspirationListResponse:
        """
        List all inspirations attached to an owned project, newest first.
        """
        # Enforce ownership and project existence
        self.proj_svc._get_owned_project(db, project_id, user_id=user_id)

        records = self.repo.list_by_project(db, project_id)
        return ProjectInspirationListResponse(
            inspirations=[self._to_response(r) for r in records]
        )

    def detach_inspiration(
        self,
        db: Session,
        project_id: str,
        user_id: Optional[str],
        steam_app_id: str,
    ) -> None:
        """
        Detach an inspiration from an owned project.
        """
        # Enforce ownership and project existence
        self.proj_svc._get_owned_project(db, project_id, user_id=user_id)

        record = self.repo.get_by_project_and_game(db, project_id, steam_app_id.strip())
        if not record:
            raise InspirationNotFoundError(
                f"Inspiration for game '{steam_app_id}' not found on project '{project_id}'."
            )

        self.repo.delete(db, record)


project_inspiration_service = ProjectInspirationService()
