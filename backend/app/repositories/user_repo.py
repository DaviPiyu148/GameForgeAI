"""User data access repository."""
from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Data access repository for User entities."""

    def get_by_id(self, db: Session, user_id: str) -> Optional[User]:
        """Find a user by primary key UUID."""
        return db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Find a user by normalized (lowercase) email address."""
        return db.query(User).filter(User.email == email.lower().strip()).first()

    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        """Find a user by username (case-sensitive)."""
        return db.query(User).filter(User.username == username.strip()).first()

    def create(self, db: Session, user: User) -> User:
        """Persist a new user record."""
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


user_repository = UserRepository()
