"""
Bootstrap script — create the first admin user.
Run once: python3 create_admin.py --username admin

Password is entered via hidden prompt (not via CLI arg to avoid shell history leakage).
"""
import argparse
import getpass
import sys
import os

# Ensure app/ is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base, SessionLocal
from app.models import User
from passlib.context import CryptContext

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main():
    parser = argparse.ArgumentParser(description="Create the first admin user for PM Tracker.")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--display-name", default="", help="Display name (optional)")
    args = parser.parse_args()

    username = args.username.strip().lower()
    if not username:
        print("ERROR: Username cannot be empty.")
        sys.exit(1)

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == "admin").first()
        if existing:
            print(f"An admin user already exists: '{existing.username}'. No action taken.")
            print("If you need to reset the admin, delete the existing admin row from the database first.")
            sys.exit(0)

        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"ERROR: Username '{username}' is already taken.")
            sys.exit(1)

        password = getpass.getpass(f"Password for '{username}': ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("ERROR: Passwords do not match.")
            sys.exit(1)
        if len(password) < 8:
            print("ERROR: Password must be at least 8 characters.")
            sys.exit(1)

        hashed = pwd_ctx.hash(password)
        user = User(
            username=username,
            display_name=args.display_name.strip() or username,
            hashed_password=hashed,
            role="admin",
        )
        db.add(user)
        db.commit()
        print(f"\nAdmin user '{username}' created successfully.")
        print("You can now log in at http://localhost:8000/auth/login")
    finally:
        db.close()


if __name__ == "__main__":
    main()
