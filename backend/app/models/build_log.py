import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, Index
from app.db.session import Base


def generate_uuid() -> str:
    """Generate a server-side UUID string."""
    return str(uuid.uuid4())


class BuildLog(Base):
    """SQLAlchemy model for persistent build log entries."""
    __tablename__ = "build_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    build_id = Column(String(36), nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)
    level = Column(String(20), nullable=False, default="INFO")  # INFO, WARNING, ERROR, SUCCESS
    message = Column(Text, nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_build_logs_build_id_sequence", "build_id", "sequence_number", unique=True),
    )

    def __repr__(self) -> str:
        return f"<BuildLog(build_id={self.build_id}, seq={self.sequence_number}, level='{self.level}')>"
