from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# SQLite specific connect args
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=(settings.APP_ENV == "development"),
)

if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite disables foreign-key enforcement by default on every connection.
    # Without this, every declared ondelete=CASCADE/SET NULL relationship (Project,
    # ProjectVersion, PlaytestSession, BuildJob, SavedDiscovery) is inert metadata:
    # inserts referencing a non-existent parent row silently succeed and deletes
    # never cascade.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
