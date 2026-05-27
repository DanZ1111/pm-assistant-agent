import os
import json
import base64
from openai import OpenAI
from app.ai.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    VISION_EXTRACTION_SYSTEM_PROMPT,
    DUAL_MODE_INTAKE_PROMPT,
    JOURNAL_SUMMARY_PROMPT,
)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        from dotenv import load_dotenv
        load_dotenv()
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=120.0)
    return _client


def extract_project_fields(raw_text: str) -> dict:
    """Call GPT-4o with JSON mode to extract project fields from raw text.
    Returns a dict of extracted fields, or {"_error": reason} on failure.
    """
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-5.4",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            max_completion_tokens=1000,
            temperature=0.1,
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as e:
        return {"_error": str(e)}


def extract_from_pdf(file_path: str) -> dict:
    """Extract text from a PDF and run field extraction.
    Returns {"extracted": dict, "raw_text": str} or {"_error": str}.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        pages = reader.pages[:10]  # cap at 10 pages
        raw_text = "\n\n".join(page.extract_text() or "" for page in pages).strip()
        if not raw_text:
            return {"_error": "Could not extract text from PDF — it may be a scanned image or empty."}
        extracted = extract_project_fields(raw_text)
        if "_error" in extracted:
            return extracted
        return {"extracted": extracted, "raw_text": raw_text}
    except Exception as e:
        return {"_error": str(e)}


def extract_from_image(file_path: str) -> dict:
    """Use vision API to extract fields and generate a summary from an image.
    Returns {"extracted": dict, "ai_summary": str} or {"_error": str}.
    """
    try:
        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else "png"
        mime = f"image/{ext}" if ext in ("png", "jpg", "jpeg", "gif", "webp") else "image/png"
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-5.4",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": VISION_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": "Analyze this product image and extract information."},
                ]},
            ],
            max_completion_tokens=1000,
            temperature=0.1,
        )
        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)
        ai_summary = result.pop("ai_summary", "")
        return {"extracted": result, "ai_summary": ai_summary}
    except Exception as e:
        return {"_error": str(e)}


def answer_help_question(question: str) -> str:
    """Answer a question about how to use PM Product Tracker using USER_GUIDE.md and CHANGELOG.md."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def _read(name, limit=8000):
        path = os.path.join(root, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()[:limit]
        except Exception:
            return f"({name} not found)"

    user_guide = _read("USER_GUIDE.md")
    changelog = _read("CHANGELOG.md")

    system_prompt = (
        "You are a helpful onboarding assistant for PM Product Tracker — "
        "an internal product management tool for a knife and product development company.\n\n"
        "Answer the user's question based only on the documentation below. "
        "Be concise (under 200 words). Use numbered steps for how-to questions. "
        "Use bullet points for lists. Never invent features not in the docs. "
        "If the question isn't covered, say so and suggest they check with the team.\n\n"
        f"---\nUSER GUIDE:\n{user_guide}\n\n---\nCHANGELOG:\n{changelog}"
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            max_completion_tokens=600,
            temperature=0.2,
        )
        return response.choices[0].message.content or "I couldn't generate an answer."
    except Exception as e:
        return f"Sorry, I couldn't answer that right now: {e}"


def extract_intake(raw_text: str) -> dict:
    """Dual-mode classifier: returns {classification: 'project'|'idea',
    project_fields: {...}, idea_fields: {...}}. Defaults to 'idea' on
    ambiguous text per product policy.
    """
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-5.4",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": DUAL_MODE_INTAKE_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            max_completion_tokens=1200,
            temperature=0.1,
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        # Normalize the shape
        cls = parsed.get("classification")
        if cls not in ("project", "idea"):
            cls = "idea"  # default to idea on missing/invalid classification
        return {
            "classification": cls,
            "project_fields": parsed.get("project_fields") or {},
            "idea_fields": parsed.get("idea_fields") or {},
        }
    except Exception as e:
        return {"_error": str(e)}


def summarize_journal_entry(entry_text: str) -> dict:
    """Summarize a Project Journal entry into {'title': str, 'summary': str}.
    Returns {'_error': str} on failure so the caller can preserve the existing
    title/summary instead of overwriting with garbage.
    """
    if not entry_text or not entry_text.strip():
        return {"_error": "Entry text is empty."}
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-5.4",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": JOURNAL_SUMMARY_PROMPT},
                {"role": "user", "content": entry_text},
            ],
            max_completion_tokens=300,
            temperature=0.2,
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        title = (parsed.get("title") or "").strip()
        summary = (parsed.get("summary") or "").strip()
        if not title or not summary:
            return {"_error": "AI returned an incomplete summary."}
        return {"title": title, "summary": summary}
    except Exception as e:
        return {"_error": str(e)}
