from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
import app.crud as crud
from app.ai.parser import answer_help_question
from app.dependencies import get_current_user, require_auth, is_forbidden_ai_question, _RedirectException

router = APIRouter()


@router.post("/ai/help/ask")
async def help_ask(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException:
        return JSONResponse({"error": "Please log in to use the AI assistant."}, status_code=401)

    body = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        return JSONResponse({"error": "No question provided."}, status_code=400)

    # AI permission guard — refuse forbidden topics
    if is_forbidden_ai_question(current_user, question):
        refusal = "I'm not able to provide that information based on your current access level."
        crud.save_ai_message(db, None, "user", question, {"source": "help_modal", "role": current_user.role})
        crud.save_ai_message(db, None, "assistant", refusal, {"source": "help_modal", "refused": True})
        return {"answer": refusal}

    answer = answer_help_question(question)

    crud.save_ai_message(db, None, "user", question, {"source": "help_modal", "role": current_user.role})
    crud.save_ai_message(db, None, "assistant", answer, {"source": "help_modal"})

    return {"answer": answer}
