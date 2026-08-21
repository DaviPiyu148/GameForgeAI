"""SavedDiscovery data access repository."""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.saved_discovery import SavedDiscovery


class SavedDiscoveryRepository:
    """Data access repository for SavedDiscovery entities."""

    def get_by_user(self, db: Session, user_id: str) -> List[SavedDiscovery]:
        """List all saved discoveries for a given user, ordered newest first."""
        return (
            db.query(SavedDiscovery)
            .filter(SavedDiscovery.user_id == user_id)
            .order_by(SavedDiscovery.created_at.desc())
            .all()
        )

    def get_by_user_and_game(
        self, db: Session, user_id: str, steam_app_id: str
    ) -> Optional[SavedDiscovery]:
        """Find a saved discovery record by user + game key (for duplicate check)."""
        return (
            db.query(SavedDiscovery)
            .filter(
                SavedDiscovery.user_id == user_id,
                SavedDiscovery.steam_app_id == steam_app_id,
            )
            .first()
        )

    def get_by_id_and_user(
        self, db: Session, record_id: str, user_id: str
    ) -> Optional[SavedDiscovery]:
        """
        Find a saved discovery by its PK, but ONLY if it belongs to user_id.
        Owner mismatch returns None — callers treat this as 404 (IDOR protection).
        """
        return (
            db.query(SavedDiscovery)
            .filter(
                SavedDiscovery.id == record_id,
                SavedDiscovery.user_id == user_id,
            )
            .first()
        )

    def create(self, db: Session, saved: SavedDiscovery) -> SavedDiscovery:
        """Persist a new saved discovery record."""
        db.add(saved)
        db.commit()
        db.refresh(saved)
        return saved

    def delete(self, db: Session, saved: SavedDiscovery) -> None:
        """Delete a saved discovery record."""
        db.delete(saved)
        db.commit()


saved_discovery_repository = SavedDiscoveryRepository()
