import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey
from app.db.session import Base


def generate_uuid() -> str:
    """Generate a server-side UUID string."""
    return str(uuid.uuid4())


class BuildJob(Base):
    """SQLAlchemy model for asynchronous build jobs."""
    __tablename__ = "build_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)

    # Owner — nullable for migration safety (pre-B7 orphaned rows).
    # Post-B7: every API-created BuildJob MUST have a non-null user_id.
    # user_id is always sourced from get_current_user(), never from request body.
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    project_id = Column(String(36), nullable=True, index=True)
    prompt = Column(Text, nullable=False)
    engine = Column(String(100), nullable=False, default="Phaser")
    art_density = Column(Integer, nullable=False, default=50)
    physics = Column(Integer, nullable=False, default=80)
    modules = Column(JSON, nullable=False, default=list)
    scale = Column(String(20), nullable=False, default="standard")
    world_mode = Column(String(20), nullable=False, default="linear")

    # Status: QUEUED -> RUNNING -> VALIDATING -> SUCCESS / ERROR
    status = Column(String(50), nullable=False, default="QUEUED", index=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    # Validated Game DSL artifact (Phase B3)
    game_dsl = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<BuildJob(id={self.id}, status='{self.status}', project_id={self.project_id})>"
