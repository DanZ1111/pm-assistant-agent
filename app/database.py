import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Absolute path ensures the local SQLite DB is always in the project root regardless of CWD
_DEFAULT_SQLITE = "sqlite:///" + os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "pm_tracker.db"
)

# Use DATABASE_URL env var (e.g. Railway PostgreSQL) when set, otherwise local SQLite
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", _DEFAULT_SQLITE)

# Railway and Heroku use the legacy "postgres://" scheme; SQLAlchemy 2.x requires "postgresql://"
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# check_same_thread is a SQLite-only flag
_connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

# Enforce foreign-key constraints on SQLite to mirror PostgreSQL (Railway prod)
# behavior. Default SQLite has PRAGMA foreign_keys = OFF, which silently allows
# FK violations in dev that later 500 on Railway. This event listener flips it
# ON for every new SQLite connection. PostgreSQL ignores the PRAGMA.
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_fk_on(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
