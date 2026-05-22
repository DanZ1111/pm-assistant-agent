from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os

from app.database import engine, Base, SessionLocal
import app.models  # register models before create_all
from app.models import User
from app.routes.projects import router as projects_router
from app.routes.admin import router as admin_router
from app.routes.files import router as files_router
from app.routes.intake import router as intake_router
from app.routes.help import router as help_router
from app.routes.auth import router as auth_router
from app.routes.admin_users import router as admin_users_router


def _bootstrap_admin_from_env():
    """If INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD are set and no admin
    exists, create one. Idempotent — never overwrites an existing admin.
    Designed for first-deploy bootstrap on Railway. DELETE these env vars after
    your admin is created.
    """
    initial_user = os.environ.get("INITIAL_ADMIN_USERNAME")
    initial_pass = os.environ.get("INITIAL_ADMIN_PASSWORD")
    if not (initial_user and initial_pass):
        return

    from passlib.context import CryptContext
    db = SessionLocal()
    try:
        if db.query(User).filter(User.role == "admin").first():
            print("[bootstrap] Admin already exists — env-var bootstrap skipped.")
            return
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        username = initial_user.lower().strip()
        if db.query(User).filter(User.username == username).first():
            print(f"[bootstrap] Username '{username}' already taken — bootstrap skipped.")
            return
        admin = User(
            username=username,
            display_name=initial_user.strip(),
            role="admin",
            hashed_password=pwd_ctx.hash(initial_pass),
        )
        db.add(admin)
        db.commit()
        print(f"[bootstrap] Admin '{username}' created from env vars. "
              "Delete INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD now.")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    os.makedirs("app/uploads", exist_ok=True)
    _bootstrap_admin_from_env()
    yield


app = FastAPI(title="PM Product Tracker", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")

app.include_router(projects_router)
app.include_router(admin_router)
app.include_router(files_router)
app.include_router(intake_router)
app.include_router(help_router)
app.include_router(auth_router)
app.include_router(admin_users_router)


@app.get("/healthz")
def healthz():
    """Lightweight health check for Railway / load balancers."""
    return {"status": "ok"}


@app.get("/")
def root():
    return RedirectResponse(url="/projects")
