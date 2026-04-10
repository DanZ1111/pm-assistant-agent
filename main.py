from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text
from database import engine, Base
import models  # register all ORM models before create_all
from routers.chat import router as chat_router
from routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Safe column migrations for existing Railway DB (idempotent)
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE entities ADD COLUMN IF NOT EXISTS visibility VARCHAR NOT NULL DEFAULT 'workspace';"
        ))
        conn.execute(text(
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);"
        ))
        conn.commit()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(chat_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
