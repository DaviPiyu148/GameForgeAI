import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, UniqueConstraint
from app.db.session import Base


def generate_uuid() -> str:
    """Generate a server-side UUID string."""
    return str(uuid.uuid4())


class UserGenrePreference(Base):
    """SQLAlchemy model for tracking implicit behavioral genre affinity scores per user."""
    __tablename__ = "user_genre_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    genre = Column(String(50), nullable=False, index=True)
    score = Column(Float, nullable=False, default=0.0)
    interaction_count = Column(Integer, nullable=False, default=1)

    last_interaction_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "genre", name="uq_user_genre_preference"),
    )

    def __repr__(self) -> str:
        return f"<UserGenrePreference(user_id='{self.user_id}', genre='{self.genre}', score={self.score})>"
