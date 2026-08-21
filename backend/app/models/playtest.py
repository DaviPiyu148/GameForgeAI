import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey
from app.db.session import Base


def generate_uuid() -> str:
    """Generate a server-side UUID string."""
    return str(uuid.uuid4())


class PlaytestSession(Base):
    """SQLAlchemy model for recording player prototype playtest sessions and telemetry."""
    __tablename__ = "playtest_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    duration_seconds = Column(Integer, nullable=False, default=0)
    score = Column(Integer, nullable=False, default=0)
    damage_taken = Column(Integer, nullable=False, default=0)
    damage_dealt = Column(Integer, nullable=False, default=0)
    enemies_defeated = Column(Integer, nullable=False, default=0)
    collectibles_gathered = Column(Integer, nullable=False, default=0)
    objectives_completed = Column(Integer, nullable=False, default=0)
    outcome = Column(String(50), nullable=False, default="PLAYED")  # WON, LOST, ABANDONED, PLAYED

    telemetry_events = Column(JSON, nullable=True)
    ai_analysis = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<PlaytestSession(id={self.id}, project_id={self.project_id}, outcome='{self.outcome}', score={self.score})>"
