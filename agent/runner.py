import json
from datetime import datetime
from sqlalchemy.orm import Session
from openai import OpenAI
from config import settings
from models import Conversation, Message, User
from agent.tools import TOOLS
from agent.tool_handlers import dispatch_tool
from agent.system_prompt import build_system_prompt

client = OpenAI(api_key=settings.openai_api_key)


def get_or_create_conversation(session_id: str, db: Session, user_id: int) -> Conversation:
    conv = db.query(Conversation).filter(Conversation.session_id == session_id).first()
    if not conv:
        conv = Conversation(session_id=session_id, user_id=user_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    else:
        conv.last_active = datetime.utcnow()
        db.commit()
    return conv


def save_message(
    conversation_id: int,
    role: str,
    content: str | None,
    db: Session,
    tool_calls=None,
    tool_call_id: str | None = None,
    tool_name: str | None = None,
) -> None:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        tool_calls=(
            json.dumps([tc.model_dump() for tc in tool_calls]) if tool_calls else None
        ),
        tool_call_id=tool_call_id,
        tool_name=tool_name,
    )
    db.add(msg)
    db.commit()


def load_history(conversation_id: int, db: Session) -> list[dict]:
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(settings.max_history_messages)
        .all()
    )

    result = []
    for msg in reversed(messages):
        if msg.role == "tool":
            # Tool result messages: role, tool_call_id, content
            result.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content or "",
            })
        elif msg.role == "assistant" and msg.tool_calls:
            # Assistant message that triggered tool calls
            m: dict = {
                "role": "assistant",
                "content": msg.content,  # may be None
                "tool_calls": json.loads(msg.tool_calls),
            }
            result.append(m)
        else:
            result.append({"role": msg.role, "content": msg.content or ""})

    return result


def run_agent(user_message: str, session_id: str, db: Session, user: User) -> str:
    conversation = get_or_create_conversation(session_id, db, user.id)
    save_message(conversation.id, "user", user_message, db)

    def build_messages() -> list[dict]:
        # Rebuild system prompt on every call so dynamic context stays current and permission-filtered
        return [{"role": "system", "content": build_system_prompt(db, user)}] + load_history(conversation.id, db)

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=build_messages(),
        tools=TOOLS,
        tool_choice="auto",
    )

    new_type_suggestions: list[str] = []

    # Tool call loop
    while response.choices[0].finish_reason == "tool_calls":
        tool_calls = response.choices[0].message.tool_calls
        assistant_content = response.choices[0].message.content  # may be None

        save_message(conversation.id, "assistant", assistant_content, db, tool_calls=tool_calls)

        for tc in tool_calls:
            result = dispatch_tool(tc.function.name, tc.function.arguments, db, user)

            if result.get("new_type_flag"):
                record_type = json.loads(tc.function.arguments).get("record_type", "")
                if record_type:
                    new_type_suggestions.append(record_type)

            save_message(
                conversation.id,
                "tool",
                json.dumps(result),
                db,
                tool_call_id=tc.id,
                tool_name=tc.function.name,
            )

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=build_messages(),
            tools=TOOLS,
            tool_choice="auto",
        )

    final_text = response.choices[0].message.content or "Done."

    # Append new record type suggestions if any were flagged
    if new_type_suggestions:
        unique = list(dict.fromkeys(new_type_suggestions))
        suggestion_note = (
            "\n\n*(Used new record type(s): "
            + ", ".join(f"'{t}'" for t in unique)
            + " — worth formalizing?)*"
        )
        final_text += suggestion_note

    save_message(conversation.id, "assistant", final_text, db)
    return final_text
