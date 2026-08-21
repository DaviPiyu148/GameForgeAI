import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Index
from app.db.session import Base


def generate_uuid() -> str:
    """Generate a server-side UUID string."""
    return str(uuid.uuid4())


class SavedDiscovery(Base):
    """
    SQLAlchemy model for user-saved game discoveries.

    Storage strategy: stores only the catalog key (steam_app_id / external_id).
    Display metadata (title, genres) is resolved from the in-memory catalog at
    query time. This prevents the frontend from injecting fake catalog metadata.

    ON DELETE CASCADE: when a user account is deleted, all their saved discoveries
    are automatically removed.
    """
    __tablename__ = "saved_discoveries"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)

    # Owner — non-nullable; every saved record must belong to a real user.
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The canonical identifier from the Steam Insights catalog (external_id field).
    # Used to resolve current game metadata from the FAISS catalog.
    steam_app_id = Column(String(50), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # One save record per user per game — prevents duplicate bookmarks.
        UniqueConstraint("user_id", "steam_app_id", name="uq_saved_discoveries_user_game"),
    )

    def __repr__(self) -> str:
        return f"<SavedDiscovery(id={self.id}, user_id={self.user_id}, steam_app_id='{self.steam_app_id}')>"
