import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey
from app.db.session import Base


def generate_uuid() -> str:
    """Generate a server-side UUID string."""
    return str(uuid.uuid4())


class Project(Base):
    """SQLAlchemy model for persisted Game Projects."""
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)

    # Owner — nullable for migration safety.
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title = Column(String(255), nullable=False)
    genre = Column(String(100), nullable=False, default="Generated Concept")
    prompt = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="PLAYABLE")
    
    # Build specifications
    engine = Column(String(100), nullable=False, default="Top-Down Action")
    art_density = Column(Integer, nullable=False, default=50)
    physics = Column(Integer, nullable=False, default=80)
    modules = Column(JSON, nullable=False, default=list)
    scale = Column(String(20), nullable=False, default="standard")
    world_mode = Column(String(20), nullable=False, default="linear")

    # Validated Game DSL, GameDesignSpec, and Versioning
    design_spec = Column(JSON, nullable=True)
    game_dsl = Column(JSON, nullable=True)
    runtime_metadata = Column(JSON, nullable=True)
    current_version = Column(Integer, nullable=False, default=1)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, title='{self.title}', status='{self.status}', version={self.current_version})>"
