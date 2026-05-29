"""Build 21 — Bottom AI chat endpoint + conversation history.

The chat surface in the browser POSTs to /ai/chat with a message + optional
conversation_id + optional project_id + mode ("ask" | "intake"). Server-side
flow per MASTERPLAN.md Build 21 detail section.
"""
from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
import app.crud as crud
from app.ai.tools import TOOL_SCHEMAS, dispatch
from app.ai.prompts import CHAT_ASK_SYSTEM_PROMPT, CHAT_INTAKE_SYSTEM_PROMPT
from app.dependencies import (
    get_current_user, require_auth, is_forbidden_ai_question,
    _RedirectException,
)

router = APIRouter()

# Lazy OpenAI client (mirrors app.ai.parser pattern).
_client = None
def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=120.0)
    return _client

# How many prior messages to inject for context. Keeps token use bounded.
_HISTORY_LIMIT = 10
_MODEL = "gpt-5.4"


def _refusal_response():
    return {
        "ok": False,
        "error": "question_blocked_by_permission_guard",
        "message": "I'm not able to answer that based on your current access level.",
    }


def _serialize_message(msg) -> dict:
    return {
        "id": msg.id,
        "role": msg.role,
        "message": msg.message,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "metadata": msg.metadata_json or {},
    }


def _serialize_conversation(conv, with_project_name=True) -> dict:
    out = {
        "id": conv.id,
        "title": conv.title,
        "project_id": conv.project_id,
        "status": conv.status,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
    }
    if with_project_name and conv.project_id and getattr(conv, "project", None):
        out["project_name"] = conv.project.name
    return out


@router.post("/ai/chat")
async def ai_chat(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException:
        return JSONResponse({"ok": False, "error": "not_authenticated"}, status_code=401)

    body = await request.json()
    message_text = (body.get("message") or "").strip()
    if not message_text:
        return JSONResponse({"ok": False, "error": "empty_message"}, status_code=400)

    mode = body.get("mode") or "intake"
    if mode not in ("ask", "intake"):
        mode = "intake"

    project_id = body.get("project_id")
    try:
        project_id = int(project_id) if project_id else None
    except (ValueError, TypeError):
        project_id = None

    conversation_id = body.get("conversation_id")
    try:
        conversation_id = int(conversation_id) if conversation_id else None
    except (ValueError, TypeError):
        conversation_id = None

    # Permission guard — block forbidden questions BEFORE any OpenAI call.
    if is_forbidden_ai_question(current_user, message_text):
        return JSONResponse(_refusal_response(), status_code=200)

    # Load or create the conversation.
    if conversation_id:
        conv = crud.get_ai_conversation(db, conversation_id, current_user.id)
        if not conv:
            # Either doesn't exist or isn't this user's — treat as fresh.
            conv = crud.create_ai_conversation(db, current_user.id, project_id=project_id)
    else:
        conv = crud.create_ai_conversation(db, current_user.id, project_id=project_id)

    # Persist user message first (so it's there even if OpenAI errors).
    crud.save_ai_message(
        db,
        project_id=conv.project_id,
        role="user",
        message=message_text,
        metadata={"conversation_id": conv.id, "mode": mode, "source": "bottom_chat"},
    )

    # Build OpenAI messages list.
    system_prompt = CHAT_INTAKE_SYSTEM_PROMPT if mode == "intake" else CHAT_ASK_SYSTEM_PROMPT
    history = crud.get_ai_messages_for_conversation(db, conv.id, limit=_HISTORY_LIMIT)
    openai_messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        # The last entry is the new user message we just saved — include it as-is.
        openai_messages.append({"role": m.role, "content": m.message})

    # Call OpenAI. If it errors, we still respond gracefully.
    assistant_text = ""
    tool_results = []
    try:
        kwargs = {
            "model": _MODEL,
            "messages": openai_messages,
            "temperature": 0.3,
        }
        if mode == "intake":
            kwargs["tools"] = TOOL_SCHEMAS
            kwargs["tool_choice"] = "auto"
        response = _get_client().chat.completions.create(**kwargs)
        choice = response.choices[0]
        assistant_text = (choice.message.content or "").strip()
        tool_calls = getattr(choice.message, "tool_calls", None) or []
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            result = dispatch(name, args, db, current_user)
            tool_results.append({"name": name, "args": args, "result": result})
        if not assistant_text and tool_results:
            # If the model returned only tool_calls with no prose, give the user a brief summary.
            assistant_text = _summarize_tool_results(tool_results)
    except Exception as exc:
        assistant_text = f"(AI error — please try again. Detail: {type(exc).__name__})"

    # Persist assistant message.
    crud.save_ai_message(
        db,
        project_id=conv.project_id,
        role="assistant",
        message=assistant_text or "(no response)",
        metadata={
            "conversation_id": conv.id,
            "mode": mode,
            "source": "bottom_chat",
            "tool_calls": tool_results or None,
        },
    )

    return {
        "ok": True,
        "conversation_id": conv.id,
        "assistant_message": assistant_text or "(no response)",
        "tool_calls": tool_results,
    }


def _summarize_tool_results(tool_results: list) -> str:
    """Brief plain-text wrap-up if the model didn't return prose."""
    parts = []
    for tr in tool_results:
        r = tr.get("result") or {}
        name = tr.get("name") or "unknown_tool"
        if r.get("ok"):
            parts.append(f"Done: {name}.")
        else:
            err = r.get("error") or "unknown_error"
            if err == "not_wired_until_build_21":
                parts.append(f"`{name}` isn't wired in this release — it'll land in a follow-up build.")
            elif err == "forbidden":
                parts.append(f"You don't have permission to run `{name}`.")
            elif err == "field_not_allowlisted":
                parts.append(f"That field can't be set via chat ({r.get('field')}).")
            else:
                parts.append(f"`{name}` failed: {err}.")
    return " ".join(parts)


@router.get("/ai/conversations")
def list_conversations(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException:
        return JSONResponse({"ok": False, "error": "not_authenticated"}, status_code=401)
    convs = crud.list_ai_conversations(db, current_user.id, include_archived=False)
    return {"ok": True, "conversations": [_serialize_conversation(c) for c in convs]}


@router.get("/ai/chat/{conversation_id}")
def get_chat(conversation_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException:
        return JSONResponse({"ok": False, "error": "not_authenticated"}, status_code=401)
    conv = crud.get_ai_conversation(db, conversation_id, current_user.id)
    if not conv:
        return JSONResponse({"ok": False, "error": "conversation_not_found"}, status_code=404)
    msgs = crud.get_ai_messages_for_conversation(db, conv.id)
    return {
        "ok": True,
        "conversation": _serialize_conversation(conv),
        "messages": [_serialize_message(m) for m in msgs],
    }


@router.post("/ai/conversations/{conversation_id}/archive")
def archive_conversation(conversation_id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException:
        return JSONResponse({"ok": False, "error": "not_authenticated"}, status_code=401)
    ok = crud.archive_ai_conversation(db, conversation_id, current_user.id)
    if not ok:
        return JSONResponse({"ok": False, "error": "conversation_not_found"}, status_code=404)
    return {"ok": True}
