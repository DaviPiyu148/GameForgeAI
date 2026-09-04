"""ProjectInspiration data access repository."""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.project_inspiration import ProjectInspiration


class ProjectInspirationRepository:
    """Data access repository for ProjectInspiration entities."""

    def list_by_project(self, db: Session, project_id: str) -> List[ProjectInspiration]:
        """List all inspirations for a given project, ordered newest first."""
        return (
            db.query(ProjectInspiration)
            .filter(ProjectInspiration.project_id == project_id)
            .order_by(ProjectInspiration.created_at.desc(), ProjectInspiration.id.desc())
            .all()
        )

    def get_by_project_and_game(
        self, db: Session, project_id: str, steam_app_id: str
    ) -> Optional[ProjectInspiration]:
        """Find an inspiration record by project + steam_app_id."""
        return (
            db.query(ProjectInspiration)
            .filter(
                ProjectInspiration.project_id == project_id,
                ProjectInspiration.steam_app_id == steam_app_id,
            )
            .first()
        )

    def create(self, db: Session, record: ProjectInspiration) -> ProjectInspiration:
        """Persist a new project inspiration record."""
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def delete(self, db: Session, record: ProjectInspiration) -> None:
        """Delete a project inspiration record."""
        db.delete(record)
        db.commit()


project_inspiration_repository = ProjectInspirationRepository()
