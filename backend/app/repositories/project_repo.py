from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.project import Project


class ProjectRepository:
    """Data access repository for Project entities."""

    def create(self, db: Session, project: Project) -> Project:
        """Persist a new project to the database."""
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def get_by_id(self, db: Session, project_id: str) -> Optional[Project]:
        """Find a project by its primary key ID."""
        return db.query(Project).filter(Project.id == project_id).first()

    def list(
        self,
        db: Session,
        limit: int = 100,
        offset: int = 0,
        user_id: Optional[str] = None,
    ) -> List[Project]:
        """
        List projects ordered by newest first.
        If user_id is provided, filters to only that user's projects.
        """
        query = db.query(Project).order_by(Project.created_at.desc())
        if user_id is not None:
            query = query.filter(Project.user_id == user_id)
        return query.offset(offset).limit(limit).all()

    def update(self, db: Session, project: Project) -> Project:
        """Commit updates to an existing project entity."""
        db.commit()
        db.refresh(project)
        return project


project_repository = ProjectRepository()
