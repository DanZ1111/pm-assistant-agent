import os
import json
import base64
from openai import OpenAI
from app.ai.prompts import EXTRACTION_SYSTEM_PROMPT, VISION_EXTRACTION_SYSTEM_PROMPT

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
