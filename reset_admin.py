"""
Reset the admin account to a known username/password.
Idempotent: works whether or not an admin exists. Safe to re-run.

After running:
  username: admin
  password: show me the money   (with spaces — type it as-is at login)

Locally:
  python3 reset_admin.py

On Railway (using the Railway CLI from your local machine):
  railway run python3 reset_admin.py

On Railway (using the Railway dashboard shell):
  Settings → Shell → python3 reset_admin.py

Uses DATABASE_URL env var automatically, so it points at the same database
your live app is using.
"""

import sys
import os

# Make sure 'app' is importable regardless of CWD
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, SQLALCHEMY_DATABASE_URL, engine, Base
import app.models  # register all models
from app.models import User, UserSession
from passlib.context import CryptContext


FIXED_USERNAME = "admin"
FIXED_PASSWORD = "show me the money"


def main():
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_ctx.hash(FIXED_PASSWORD)

    # Make sure tables exist (idempotent — safe if they already do)
    Base.metadata.create_all(bind=engine)

    # Mask password in any printed URL
    db_url_masked = SQLALCHEMY_DATABASE_URL
    if "@" in db_url_masked:
        # postgresql://user:pass@host... → keep scheme + ***@host
        scheme, rest = db_url_masked.split("://", 1)
        creds, host = rest.split("@", 1)
        db_url_masked = f"{scheme}://***@{host}"
    print(f"Connected to: {db_url_masked}")

    db = SessionLocal()
    try:
        # Find any existing admin
        admin = db.query(User).filter(User.role == "admin").first()

        if admin:
            old_username = admin.username
            admin.username = FIXED_USERNAME
            admin.display_name = admin.display_name or "Admin"
            admin.hashed_password = hashed
            action = "reset"
        else:
            # No admin exists. Make sure the desired username isn't taken by a non-admin.
            taken = db.query(User).filter(User.username == FIXED_USERNAME).first()
            if taken:
                taken.role = "admin"
                taken.hashed_password = hashed
                admin = taken
                old_username = taken.username
                action = "promoted to admin"
            else:
                admin = User(
                    username=FIXED_USERNAME,
                    display_name="Admin",
                    role="admin",
                    hashed_password=hashed,
                )
                db.add(admin)
                db.flush()
                old_username = "(new)"
                action = "created"

        # Invalidate all existing sessions for this user — forces re-login
        deleted_sessions = (
            db.query(UserSession)
            .filter(UserSession.user_id == admin.id)
            .delete()
        )
        db.commit()
        db.refresh(admin)

        print("─" * 60)
        print(f"Admin {action}.")
        if old_username != admin.username:
            print(f"  Username:  '{old_username}' → '{admin.username}'")
        else:
            print(f"  Username:  {admin.username}")
        print(f"  Password:  {FIXED_PASSWORD}   (note the spaces)")
        print(f"  Sessions invalidated: {deleted_sessions}")
        print("─" * 60)
        print("Log in at /auth/login with the credentials above.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
