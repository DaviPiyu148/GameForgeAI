"""
Development seed script: create a reproducible dev user account.

Usage:
    DEV_SEED_PASSWORD=your-local-password python scripts/seed_dev.py

Environment variables:
    DEV_SEED_PASSWORD  (required) — plaintext password for the dev account.
    DATABASE_URL       (optional) — falls back to settings.DATABASE_URL.

This script is for local development ONLY. Never run in production.
Passwords are NOT hardcoded — always supplied via environment variable.

Dev account credentials:
    email:    dev@gameforge.local
    username: DevPlayer
"""
import os
import sys

# Add backend root to import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    password = os.environ.get("DEV_SEED_PASSWORD", "").strip()
    if not password:
        print("ERROR: DEV_SEED_PASSWORD environment variable is required.")
        print("Usage: DEV_SEED_PASSWORD=your-local-dev-password python scripts/seed_dev.py")
        sys.exit(1)

    # Import app modules after path setup
    from app.db.session import SessionLocal, Base, engine
    from app.models.user import User
    from app.repositories.user_repo import user_repository
    from app.auth.password import hash_password, validate_password_strength

    # Ensure tables exist (for fresh environments)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        DEV_EMAIL = "dev@gameforge.local"
        DEV_USERNAME = "DevPlayer"

        existing = user_repository.get_by_email(db, DEV_EMAIL)
        if existing:
            print(f"Dev account already exists (email: {DEV_EMAIL}, id: {existing.id})")
            print("No changes made.")
            return

        try:
            validate_password_strength(password)
        except ValueError as e:
            print(f"ERROR: Password does not meet requirements: {e}")
            sys.exit(1)

        user = User(
            email=DEV_EMAIL,
            username=DEV_USERNAME,
            password_hash=hash_password(password),
            level=1,
        )
        saved = user_repository.create(db, user)
        print(f"[OK] Dev account created successfully.")
        print(f"  email:    {saved.email}")
        print(f"  username: {saved.username}")
        print(f"  id:       {saved.id}")
        print(f"  level:    {saved.level}")
        print()
        print("You can now log in at http://localhost:5173/ with these credentials.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
