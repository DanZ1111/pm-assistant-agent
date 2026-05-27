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
from app.routes.calendar import router as calendar_router
from app.routes.ideas import router as ideas_router


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

# Register Jinja2 globals so templates can use {{ APP_VERSION }} etc.
# All version display in the UI MUST read from these — no hardcoded version literals.
# FastAPI's Jinja2Templates creates a SEPARATE Environment per instance, so
# we must inject globals into every router's `templates` (each routes module
# instantiates its own). Walk them all.
from app.version import CURRENT_VERSION, CURRENT_BUILD_NAME, LAST_UPDATED  # noqa: E402
from app.routes import projects as _r_projects, admin as _r_admin, files as _r_files  # noqa: E402
from app.routes import intake as _r_intake, help as _r_help, auth as _r_auth  # noqa: E402
from app.routes import admin_users as _r_admin_users, calendar as _r_calendar, ideas as _r_ideas  # noqa: E402

_GLOBALS = {
    "APP_VERSION": CURRENT_VERSION,
    "APP_BUILD_NAME": CURRENT_BUILD_NAME,
    "APP_LAST_UPDATED": LAST_UPDATED,
}
for _mod in (_r_projects, _r_admin, _r_files, _r_intake, _r_help, _r_auth,
             _r_admin_users, _r_calendar, _r_ideas):
    _t = getattr(_mod, "templates", None)
    if _t is not None:
        _t.env.globals.update(_GLOBALS)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")

app.include_router(projects_router)
app.include_router(admin_router)
app.include_router(files_router)
app.include_router(intake_router)
app.include_router(help_router)
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(calendar_router)
app.include_router(ideas_router)


@app.get("/healthz")
def healthz():
    """Lightweight health check for Railway / load balancers."""
    return {"status": "ok"}


@app.get("/")
def root():
    return RedirectResponse(url="/projects")
