"""Temporary assistant attachment lifecycle for Build 28.

Pending bytes stay outside the publicly mounted uploads directory. Confirmed
saves move the original bytes into project files through the normal CRUD path.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

import app.crud as crud
from app.ai.parser import _extract_docx_text, _extract_pdf_text


PENDING_UPLOAD_DIR = Path(
    os.getenv(
        "AI_PENDING_UPLOAD_DIR",
        Path(__file__).resolve().parents[1] / "pending_uploads",
    )
)
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
PENDING_TTL_SECONDS = 24 * 60 * 60
ALLOWED_EXTENSIONS = {
    "pdf": "pdf",
    "docx": "word",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "webp": "image",
    "gif": "image",
}
FILE_CATEGORIES = {
    "rendering", "reference", "quotation", "thesis",
    "factory_feedback", "packaging", "other",
}
_ATTACHMENT_ID_RE = re.compile(r"^[a-f0-9]{32}$")


class AttachmentError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _ensure_dir() -> None:
    PENDING_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _paths(attachment_id: str, extension: str | None = None) -> tuple[Path, Path]:
    if not _ATTACHMENT_ID_RE.fullmatch(attachment_id or ""):
        raise AttachmentError("attachment_not_found", "Attachment not found.")
    meta_path = PENDING_UPLOAD_DIR / f"{attachment_id}.json"
    if extension:
        return PENDING_UPLOAD_DIR / f"{attachment_id}.{extension}", meta_path
    return PENDING_UPLOAD_DIR / attachment_id, meta_path


def _public_metadata(metadata: dict) -> dict:
    return {
        key: metadata.get(key)
        for key in (
            "attachment_id", "original_filename", "file_type", "content_type",
            "file_size", "created_at", "extracted_text_preview",
            "extraction_error",
        )
    }


def cleanup_stale_pending_attachments(now: float | None = None) -> int:
    """Delete pending bytes and sidecars older than the TTL."""
    _ensure_dir()
    now = now if now is not None else time.time()
    removed = 0
    for meta_path in PENDING_UPLOAD_DIR.glob("*.json"):
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            created_ts = float(metadata.get("created_ts") or meta_path.stat().st_mtime)
        except Exception:
            created_ts = meta_path.stat().st_mtime
            metadata = {}
        if now - created_ts <= PENDING_TTL_SECONDS:
            continue
        stored_name = metadata.get("stored_name")
        if stored_name:
            (PENDING_UPLOAD_DIR / stored_name).unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        removed += 1
    return removed


def create_pending_attachment(
    content: bytes,
    original_filename: str,
    content_type: str,
    user_id: int,
) -> dict:
    cleanup_stale_pending_attachments()
    filename = os.path.basename((original_filename or "").strip())
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise AttachmentError(
            "unsupported_attachment_type",
            "Upload a PDF, DOCX, PNG, JPG, WEBP, or GIF file.",
        )
    if not content:
        raise AttachmentError("empty_attachment", "The selected file is empty.")
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise AttachmentError("attachment_too_large", "Attachments must be 10 MB or smaller.")

    attachment_id = uuid.uuid4().hex
    stored_name = f"{attachment_id}.{extension}"
    disk_path, meta_path = _paths(attachment_id, extension)
    _ensure_dir()
    disk_path.write_bytes(content)

    extracted_text = ""
    extraction_error = None
    try:
        if extension == "pdf":
            extracted_text = _extract_pdf_text(str(disk_path))
        elif extension == "docx":
            extracted_text = _extract_docx_text(str(disk_path))
    except Exception as exc:
        extraction_error = f"{type(exc).__name__}: {exc}"

    created_ts = time.time()
    metadata = {
        "attachment_id": attachment_id,
        "user_id": int(user_id),
        "original_filename": filename,
        "stored_name": stored_name,
        "extension": extension,
        "file_type": ALLOWED_EXTENSIONS[extension],
        "content_type": content_type or "application/octet-stream",
        "file_size": len(content),
        "created_ts": created_ts,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created_ts)),
        "extracted_text": extracted_text[:30000],
        "extracted_text_preview": extracted_text[:240],
        "extraction_error": extraction_error,
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
    return _public_metadata(metadata)


def get_pending_attachment(attachment_id: str, user_id: int) -> dict:
    cleanup_stale_pending_attachments()
    _, meta_path = _paths(attachment_id)
    if not meta_path.exists():
        raise AttachmentError("attachment_not_found", "Attachment not found or expired.")
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AttachmentError("attachment_not_found", "Attachment metadata is invalid.") from exc
    if int(metadata.get("user_id") or 0) != int(user_id):
        raise AttachmentError("attachment_not_found", "Attachment not found or expired.")
    disk_path = PENDING_UPLOAD_DIR / str(metadata.get("stored_name") or "")
    if not disk_path.exists():
        raise AttachmentError("attachment_not_found", "Attachment bytes are missing.")
    return metadata


def get_public_pending_attachment(attachment_id: str, user_id: int) -> dict:
    return _public_metadata(get_pending_attachment(attachment_id, user_id))


def read_pending_bytes(metadata: dict) -> bytes:
    return (PENDING_UPLOAD_DIR / metadata["stored_name"]).read_bytes()


def discard_pending_attachment(attachment_id: str, user_id: int) -> bool:
    metadata = get_pending_attachment(attachment_id, user_id)
    (PENDING_UPLOAD_DIR / metadata["stored_name"]).unlink(missing_ok=True)
    (PENDING_UPLOAD_DIR / f"{attachment_id}.json").unlink(missing_ok=True)
    return True


def persist_pending_attachment(
    db,
    attachment_id: str,
    user_id: int,
    project_id: int,
    file_category: str = "reference",
    source_note: str | None = None,
):
    """Move original bytes to public project storage and create ProjectFile."""
    metadata = get_pending_attachment(attachment_id, user_id)
    category = file_category if file_category in FILE_CATEGORIES else "reference"
    source = PENDING_UPLOAD_DIR / metadata["stored_name"]
    unique_name = f"{uuid.uuid4().hex}.{metadata['extension']}"
    destination = Path(crud.UPLOAD_DIR) / unique_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    try:
        project_file = crud.upload_file(
            db,
            project_id=project_id,
            filename=unique_name,
            original_filename=metadata["original_filename"],
            file_path=f"uploads/{unique_name}",
            file_type=metadata["file_type"],
            file_category=category,
            file_size=metadata["file_size"],
            source_note=(source_note or "").strip() or "Saved from assistant discussion",
            changed_by="ai",
            source_type="ai_chat",
        )
    except Exception:
        shutil.move(str(destination), str(source))
        raise
    (PENDING_UPLOAD_DIR / f"{attachment_id}.json").unlink(missing_ok=True)
    return project_file
