from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from database import get_db
from models import User
from auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str


class RoleUpdateRequest(BaseModel):
    role: str


@router.post("/auth/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    # First registered user becomes owner; all subsequent users default to viewer
    is_first = db.query(User).count() == 0
    role = "owner" if is_first else "viewer"
    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.username, user.role)
    return TokenResponse(access_token=token, token_type="bearer", role=user.role)


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.id, user.username, user.role)
    return TokenResponse(access_token=token, token_type="bearer", role=user.role)


@router.patch("/auth/users/{user_id}/role")
def update_role(
    user_id: int,
    body: RoleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can change roles")
    if body.role not in ("owner", "editor", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role — must be owner, editor, or viewer")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = body.role
    db.commit()
    return {"user_id": user_id, "username": target.username, "role": body.role}


@router.get("/auth/users")
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Owner-only: list all users and their roles."""
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can list users")
    users = db.query(User).order_by(User.created_at.asc()).all()
    return [{"id": u.id, "username": u.username, "role": u.role} for u in users]
