import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, UniqueConstraint
from app.db.session import Base


def generate_uuid() -> str:
    """Generate a server-side UUID string."""
    return str(uuid.uuid4())


class ProjectInspiration(Base):
    """
    SQLAlchemy model for persistent game inspirations attached to a project.

    Stores a minimal immutable historical snapshot of the game's metadata
    at the time the developer attached it.
    """
    __tablename__ = "project_inspirations"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)

    # Owner project — CASCADE deletes inspirations when project is deleted.
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Canonical Steam App ID
    steam_app_id = Column(String(50), nullable=False)

    # Minimal snapshot fields
    title = Column(String(255), nullable=False)
    cover_url = Column(String(500), nullable=True)
    genres = Column(JSON, nullable=False, default=list)
    tags = Column(JSON, nullable=False, default=list)
    player_modes = Column(JSON, nullable=False, default=list)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "steam_app_id",
            name="uq_project_inspirations_project_game",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectInspiration(id={self.id}, project_id='{self.project_id}', "
            f"steam_app_id='{self.steam_app_id}', title='{self.title}')>"
        )
