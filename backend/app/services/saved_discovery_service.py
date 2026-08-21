"""
SavedDiscovery business logic service.

Security invariants:
- user_id always comes from get_current_user(), never from request body.
- Duplicate saves return 409 (not silently overwrite).
- Owner mismatch on delete returns 404 (IDOR protection — does not reveal
  whether the record exists for another user).
- Catalog metadata resolved server-side; frontend-submitted metadata is ignored.
"""
import logging
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models.saved_discovery import SavedDiscovery
from app.repositories.saved_discovery_repo import SavedDiscoveryRepository, saved_discovery_repository
from app.schemas.saved_discovery import (
    SaveDiscoveryRequest,
    SavedDiscoveryListResponse,
    SavedDiscoveryResponse,
)

if TYPE_CHECKING:
    from app.services.discovery_service import DiscoveryService

logger = logging.getLogger(__name__)


class DuplicateSaveError(Exception):
    """Raised when a user attempts to save a game they have already saved."""


class SavedDiscoveryNotFoundError(Exception):
    """Raised when a saved discovery record is not found or does not belong to the requesting user."""


class SavedDiscoveryService:
    """Business logic for managing user-saved game discoveries."""

    def __init__(
        self,
        repo: SavedDiscoveryRepository = saved_discovery_repository,
        discovery_svc: Optional["DiscoveryService"] = None,
    ) -> None:
        self.repo = repo
        self._discovery_svc = discovery_svc

    def _get_discovery_svc(self) -> "DiscoveryService":
        """Lazy-load discovery service to avoid circular import at module level."""
        if self._discovery_svc is None:
            from app.services.discovery_service import discovery_service
            self._discovery_svc = discovery_service
        return self._discovery_svc

    def _resolve_game_metadata(self, steam_app_id: str):
        """
        Resolve display metadata for a steam_app_id from the in-memory catalog.
        Returns (title, genres) — falls back gracefully if catalog is unavailable.
        """
        try:
            game = self._get_discovery_svc().get_game_by_steam_id(steam_app_id)
            if game:
                title = game.get("title") or f"Game {steam_app_id}"
                genres = game.get("genres") or []
                return title, genres
        except Exception:
            logger.warning("SavedDiscoveryService: catalog lookup failed for %s", steam_app_id)
        return f"Game {steam_app_id}", []

    def _to_response(self, record: SavedDiscovery) -> SavedDiscoveryResponse:
        """Convert SavedDiscovery ORM record to response schema with resolved metadata."""
        title, genres = self._resolve_game_metadata(record.steam_app_id)
        return SavedDiscoveryResponse(
            id=record.id,
            user_id=record.user_id,
            steam_app_id=record.steam_app_id,
            title=title,
            genres=genres,
            created_at=record.created_at,
        )

    def list_saved(self, db: Session, user_id: str) -> SavedDiscoveryListResponse:
        """Return all saved discoveries for the authenticated user with resolved metadata."""
        records = self.repo.get_by_user(db, user_id)
        return SavedDiscoveryListResponse(
            discoveries=[self._to_response(r) for r in records]
        )

    def save_discovery(
        self, db: Session, user_id: str, data: SaveDiscoveryRequest
    ) -> SavedDiscoveryResponse:
        """
        Save a game to the user's discovery bookmarks.

        Raises DuplicateSaveError if already saved (409).
        """
        # Check for duplicate
        existing = self.repo.get_by_user_and_game(db, user_id, data.steam_app_id)
        if existing:
            raise DuplicateSaveError(
                f"Game '{data.steam_app_id}' is already in your saved discoveries."
            )

        record = SavedDiscovery(
            user_id=user_id,
            steam_app_id=data.steam_app_id,
        )
        saved = self.repo.create(db, record)
        return self._to_response(saved)

    def delete_saved(self, db: Session, user_id: str, record_id: str) -> None:
        """
        Delete a saved discovery record.

        Raises SavedDiscoveryNotFoundError if the record does not exist OR does
        not belong to user_id. Owner mismatch produces the same 404 as not-found
        to prevent IDOR information leakage.
        """
        record = self.repo.get_by_id_and_user(db, record_id, user_id)
        if not record:
            raise SavedDiscoveryNotFoundError(
                f"Saved discovery '{record_id}' not found."
            )
        self.repo.delete(db, record)


saved_discovery_service = SavedDiscoveryService()
