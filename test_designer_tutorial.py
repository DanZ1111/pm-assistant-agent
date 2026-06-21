"""Smoke test for /designer/tutorial — the standalone Chinese onboarding
page the user shares with the designer manager.

Locks (Q14):
1. Route gated to authenticated designer-portal users.
2. Page CTA points at /designer/manager so the DM lands on her actual
   workbench after reading the tutorial.

Run: python3 test_designer_tutorial.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

PASS, FAIL = [], []
RUN_TAG = datetime.utcnow().strftime("%Y%m%d%H%M%S")


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def _make_dm_fixture():
    """Create a designer_manager user with a live session token and
    return (user_id, token). Caller is responsible for cleanup."""
    from app.database import SessionLocal
    from app.models import User, UserSession

    db = SessionLocal()
    try:
        dm = User(
            username=f"tutorial_dm_{RUN_TAG}",
            display_name="Tutorial DM",
            hashed_password="not-used",
            role="designer_manager",
        )
        db.add(dm)
        db.flush()
        token = f"tutorial-{RUN_TAG}"
        db.add(UserSession(
            token=token,
            user_id=dm.id,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
        ))
        db.commit()
        return dm.id, token
    finally:
        db.close()


def _cleanup_dm(user_id):
    from app.database import SessionLocal
    from app.models import User, UserSession

    db = SessionLocal()
    try:
        db.query(UserSession).filter(UserSession.user_id == user_id).delete(
            synchronize_session=False
        )
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            db.delete(user)
        db.commit()
    finally:
        db.close()


def main():
    from app.database import Base, engine
    from app import migrations
    from app.main import app

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)

    client = TestClient(app)

    print("\n── 1. Anonymous user is redirected away from tutorial ──")
    anon = client.get("/designer/tutorial", follow_redirects=False)
    if anon.status_code in (302, 303):
        ok(f"anonymous GET /designer/tutorial -> {anon.status_code} redirect")
    else:
        fail("anonymous redirect", f"expected 302/303, got {anon.status_code}")

    print("\n── 2. Designer_manager can load the tutorial ──")
    dm_user_id, dm_token = _make_dm_fixture()
    try:
        dm_client = TestClient(app)
        dm_client.cookies.set("pm_session", dm_token)
        resp = dm_client.get("/designer/tutorial")
        if resp.status_code == 200:
            ok("designer_manager GET /designer/tutorial -> 200")
        else:
            fail("dm tutorial route", f"expected 200, got {resp.status_code}")
            return summary()

        print("\n── 3. Tutorial content is Chinese and CTA points at the workbench ──")
        body = resp.text
        if "设计师经理" in body and "欢迎使用" in body:
            ok("tutorial body contains expected Chinese section markers")
        else:
            fail("tutorial Chinese content", "missing expected zh markers")

        if 'href="/designer/manager"' in body:
            ok("tutorial CTA links to /designer/manager")
        else:
            fail("tutorial CTA", "missing /designer/manager href in body")
    finally:
        _cleanup_dm(dm_user_id)

    return summary()


def summary():
    print(f"\nPASSED: {len(PASS)} / FAILED: {len(FAIL)}")
    if FAIL:
        for name, reason in FAIL:
            print(f"  - {name}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
