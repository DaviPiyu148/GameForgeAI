import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey
from app.db.session import Base


def generate_uuid() -> str:
    """Generate a server-side UUID string."""
    return str(uuid.uuid4())


class ProjectVersion(Base):
    """SQLAlchemy model for tracking project revision history and DSL improvement patches."""
    __tablename__ = "project_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version_number = Column(Integer, nullable=False, default=1)
    game_dsl = Column(JSON, nullable=False)
    design_spec = Column(JSON, nullable=True)
    change_summary = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<ProjectVersion(id={self.id}, project_id={self.project_id}, version={self.version_number})>"
