import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint
from app.db.session import Base


def generate_uuid() -> str:
    """Generate a server-side UUID string."""
    return str(uuid.uuid4())


class UserProgress(Base):
    """SQLAlchemy model for server-authoritative user gamification progress and XP."""
    __tablename__ = "user_progress"

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    total_xp = Column(Integer, nullable=False, default=0)
    current_level = Column(Integer, nullable=False, default=1)

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
        return f"<UserProgress(user_id='{self.user_id}', total_xp={self.total_xp}, current_level={self.current_level})>"


class XPEvent(Base):
    """SQLAlchemy model for auditing all discrete XP grants to users."""
    __tablename__ = "xp_events"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(50), nullable=False)
    xp_amount = Column(Integer, nullable=False)
    source_reference = Column(String(255), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return f"<XPEvent(id='{self.id}', user_id='{self.user_id}', event_type='{self.event_type}', xp={self.xp_amount})>"


class UserMilestone(Base):
    """SQLAlchemy model for persisting server-validated unlocked creator milestones."""
    __tablename__ = "user_milestones"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    milestone_key = Column(String(50), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    description = Column(String(255), nullable=False)
    icon = Column(String(50), nullable=False)
    unlocked_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "milestone_key", name="uq_user_milestones_user_key"),
    )

    def __repr__(self) -> str:
        return f"<UserMilestone(user_id='{self.user_id}', key='{self.milestone_key}', unlocked_at='{self.unlocked_at}')>"

