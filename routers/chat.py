from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from database import get_db
from agent.runner import run_agent
from models import Conversation, Message, User
from auth import get_current_user

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ChatResponse(BaseModel):
    response: str
    session_id: str


class HistoryMessage(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    messages: list[HistoryMessage]
    session_id: str


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    response_text = run_agent(request.message.strip(), request.session_id, db, current_user)
    return ChatResponse(response=response_text, session_id=request.session_id)


@router.get("/history", response_model=HistoryResponse)
def history(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Allow access to own sessions + legacy anonymous sessions (user_id IS NULL)
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.session_id == session_id,
            or_(
                Conversation.user_id == current_user.id,
                Conversation.user_id.is_(None),
            ),
        )
        .first()
    )
    if not conv:
        return HistoryResponse(messages=[], session_id=session_id)

    # Return user messages and final assistant messages only (skip tool intermediates)
    messages = (
        db.query(Message)
        .filter(
            Message.conversation_id == conv.id,
            Message.role.in_(["user", "assistant"]),
            Message.tool_calls.is_(None),
        )
        .order_by(Message.created_at.asc())
        .limit(40)
        .all()
    )

    return HistoryResponse(
        messages=[
            HistoryMessage(role=m.role, content=m.content or "")
            for m in messages
            if m.content
        ],
        session_id=session_id,
    )
