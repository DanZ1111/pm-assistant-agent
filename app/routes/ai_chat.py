"""Build 21 — Bottom AI chat endpoint + conversation history.

The chat surface in the browser POSTs to /ai/chat with a message + optional
conversation_id + optional project_id + mode ("ask" | "intake"). Server-side
flow per MASTERPLAN.md Build 21 detail section.
"""
from __future__ import annotations

import json
import os
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
import app.crud as crud
from app.ai.tools import TOOL_SCHEMAS, dispatch
from app.ai.matching import find_best_match, MATCH_THRESHOLD
from app.ai.prompts import CHAT_ASK_SYSTEM_PROMPT, CHAT_INTAKE_SYSTEM_PROMPT
from app.dependencies import (
    get_current_user, require_auth, is_forbidden_ai_question,
    sanitize_project_for_user, can_view_journal,
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
_IDEA_PROPOSAL_TOOLS = {"create_idea", "link_idea_to_project", "update_idea"}


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


def build_project_context(db: Session, project_id: int, current_user) -> dict | None:
    """Build safe prompt context from the same role filter used elsewhere."""
    project = crud.get_project(db, project_id)
    if project is None:
        return None
    context = sanitize_project_for_user(project, current_user)
    context["id"] = project.id
    context["linked_ideas"] = [
        {
            "id": item["idea"].id,
            "serial_number": item["idea"].serial_number,
            "name": item["idea"].name,
            "idea_type": item["idea"].idea_type,
            "source": item["idea"].source,
        }
        for item in crud.get_ideas_for_project(db, project.id)
    ]
    if can_view_journal(current_user):
        context["recent_journal"] = [
            {
                "entry_type": entry.entry_type,
                "entry_text": entry.entry_text,
            }
            for entry in crud.get_journal_entries_for_project(db, project.id)[:5]
        ]
    return context


def _build_system_prompt(base_prompt: str, db: Session, conv, current_user) -> str:
    role_context = (
        f"\nCurrent user: {current_user.display_name or current_user.username} "
        f"(role={current_user.role})."
    )
    if not conv.project_id:
        return base_prompt + role_context + (
            "\nThis is a Global conversation. Do not assume a project. "
            "Ask which project the user means before proposing a project-linked action."
        )
    project_context = build_project_context(db, conv.project_id, current_user)
    if project_context is None:
        return base_prompt + role_context
    return base_prompt + role_context + (
        "\nActive project context follows as role-filtered JSON. Unless the user "
        "explicitly starts a new conversation, assume unqualified messages refer "
        "to this project. Prefer create_idea with project_id for inspirations so "
        "the confirmed action appears in Inspired By. Never invent missing values.\n"
        + json.dumps(project_context, ensure_ascii=False, default=str)
    )


def _with_active_project_defaults(tool_name: str, args: dict, conv) -> dict:
    out = dict(args or {})
    if conv.project_id and tool_name in ("create_idea", "link_idea_to_project"):
        out.setdefault("project_id", conv.project_id)
    return out


def _decorate_confirmation_result(tool_name: str, args: dict, result: dict, db: Session) -> dict:
    if result.get("error") != "confirmation_required":
        return result
    proposal_id = uuid.uuid4().hex
    decorated = dict(result)
    decorated["proposal_id"] = proposal_id
    if tool_name == "create_idea":
        name = str(args.get("name") or "").strip() or "(untitled)"
        project = crud.get_project(db, int(args["project_id"])) if args.get("project_id") else None
        decorated["summary"] = (
            f"Create Idea “{name}”"
            + (f" and link it to {project.name}?" if project else "?")
        )
        match, score = find_best_match(name, crud.get_all_open_ideas(db))
        if match and score >= MATCH_THRESHOLD:
            decorated["duplicate"] = {
                "idea_id": match.id,
                "serial_number": match.serial_number,
                "name": match.name,
                "score": round(score, 3),
            }
            decorated["summary"] += (
                f" A similar idea already exists: {match.serial_number} — {match.name}."
            )
    elif tool_name == "link_idea_to_project":
        idea = crud.get_idea(db, int(args.get("idea_id") or 0))
        decorated["summary"] = (
            f"Link {idea.serial_number + ' — ' + idea.name if idea else 'this idea'} "
            "to the active project's Inspired By section?"
        )
    else:
        decorated["summary"] = "Apply this Idea update?"
    return decorated


def _find_pending_proposal(db: Session, conv, proposal_id: str):
    for msg in reversed(crud.get_ai_messages_for_conversation(db, conv.id)):
        metadata = msg.metadata_json or {}
        tool_calls = metadata.get("tool_calls") or []
        for index, tool_call in enumerate(tool_calls):
            result = tool_call.get("result") or {}
            if result.get("proposal_id") == proposal_id:
                return msg, metadata, tool_calls, index, tool_call
    return None


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

    scope = body.get("scope")

    # Load or create the conversation. Build 26 conversations keep one scope:
    # switching Project / Global starts a fresh thread instead of silently
    # changing what prior messages mean.
    if conversation_id:
        conv = crud.get_ai_conversation(db, conversation_id, current_user.id)
        if not conv:
            # Either doesn't exist or isn't this user's — treat as fresh.
            conv = crud.create_ai_conversation(db, current_user.id, project_id=project_id)
        elif scope in ("project", "global"):
            requested_project_id = project_id if scope == "project" else None
            if conv.project_id != requested_project_id:
                return JSONResponse({
                    "ok": False,
                    "error": "scope_change_requires_new_conversation",
                    "message": "Start a new conversation to switch between This Project and Global scope.",
                }, status_code=409)
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
    system_prompt = _build_system_prompt(system_prompt, db, conv, current_user)
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
            args = _with_active_project_defaults(name, args, conv)
            result = dispatch(name, args, db, current_user)
            result = _decorate_confirmation_result(name, args, result, db)
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
        "project_id": conv.project_id,
        "project_name": conv.project.name if conv.project_id and conv.project else None,
        "assistant_message": assistant_text or "(no response)",
        "tool_calls": tool_results,
    }


@router.post("/ai/chat/{conversation_id}/proposals/{proposal_id}/confirm")
async def confirm_chat_proposal(
    conversation_id: int,
    proposal_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException:
        return JSONResponse({"ok": False, "error": "not_authenticated"}, status_code=401)
    conv = crud.get_ai_conversation(db, conversation_id, current_user.id)
    if not conv:
        return JSONResponse({"ok": False, "error": "conversation_not_found"}, status_code=404)
    found = _find_pending_proposal(db, conv, proposal_id)
    if not found:
        return JSONResponse({"ok": False, "error": "proposal_not_found"}, status_code=404)
    msg, metadata, tool_calls, index, tool_call = found
    prior_result = tool_call.get("result") or {}
    if prior_result.get("proposal_status") in ("confirmed", "cancelled"):
        return JSONResponse({"ok": False, "error": "proposal_already_resolved"}, status_code=409)
    try:
        body = await request.json()
    except Exception:
        body = {}
    action = body.get("action") or "confirm"
    tool_name = tool_call.get("name")
    args = dict(tool_call.get("args") or {})

    if action == "link_existing" and tool_name == "create_idea":
        duplicate = prior_result.get("duplicate") or {}
        if not duplicate.get("idea_id") or not args.get("project_id"):
            return JSONResponse({"ok": False, "error": "duplicate_link_unavailable"}, status_code=400)
        tool_name = "link_idea_to_project"
        args = {
            "project_id": args["project_id"],
            "idea_id": duplicate["idea_id"],
            "note": args.get("note"),
        }
    elif action not in ("confirm", "create_new"):
        return JSONResponse({"ok": False, "error": "invalid_proposal_action"}, status_code=400)

    result = dispatch(tool_name, args, db, current_user, confirmed=True)
    if result.get("ok"):
        result = {**result, "proposal_id": proposal_id, "proposal_status": "confirmed"}
        tool_calls[index] = {**tool_call, "confirmed_as": tool_name, "result": result}
        metadata = {**metadata, "tool_calls": tool_calls}
        msg.metadata_json = metadata
        db.commit()
        return {"ok": True, "message": result.get("message") or "Saved.", "result": result}
    return JSONResponse({
        "ok": False,
        "error": result.get("error") or "proposal_failed",
        "message": "I couldn't save that action. Please review the details and try again.",
    }, status_code=400)


@router.post("/ai/chat/{conversation_id}/proposals/{proposal_id}/cancel")
def cancel_chat_proposal(
    conversation_id: int,
    proposal_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException:
        return JSONResponse({"ok": False, "error": "not_authenticated"}, status_code=401)
    conv = crud.get_ai_conversation(db, conversation_id, current_user.id)
    if not conv:
        return JSONResponse({"ok": False, "error": "conversation_not_found"}, status_code=404)
    found = _find_pending_proposal(db, conv, proposal_id)
    if not found:
        return JSONResponse({"ok": False, "error": "proposal_not_found"}, status_code=404)
    msg, metadata, tool_calls, index, tool_call = found
    prior_result = tool_call.get("result") or {}
    if prior_result.get("proposal_status") in ("confirmed", "cancelled"):
        return JSONResponse({"ok": False, "error": "proposal_already_resolved"}, status_code=409)
    tool_calls[index] = {
        **tool_call,
        "result": {
            **prior_result,
            "ok": False,
            "error": "cancelled",
            "proposal_status": "cancelled",
            "message": "Cancelled.",
        },
    }
    msg.metadata_json = {**metadata, "tool_calls": tool_calls}
    db.commit()
    return {"ok": True}


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
            elif err == "confirmation_required":
                parts.append(f"Review and confirm the proposed `{name}` action below.")
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
