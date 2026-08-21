import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, UniqueConstraint
from app.db.session import Base


def generate_uuid() -> str:
    """Generate a server-side UUID string."""
    return str(uuid.uuid4())


class User(Base):
    """SQLAlchemy model for authenticated user accounts."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)

    # Email is normalized to lowercase before storage.
    # Must be unique across all accounts.
    email = Column(String(254), nullable=False, unique=True, index=True)

    # Display username — unique across all accounts.
    # Normalized to stripped form; case-sensitive comparison.
    username = Column(String(50), nullable=False, unique=True, index=True)

    # Argon2-hashed password via pwdlib. NEVER serialized in responses.
    password_hash = Column(String(255), nullable=False)

    # Gamification level — starts at 1.
    level = Column(Integer, nullable=False, default=1)

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

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"
