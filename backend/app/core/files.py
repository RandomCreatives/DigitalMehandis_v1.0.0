"""
File upload handling — validates, stores, and extracts metadata from PDFs.
"""
import os
import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.core.config import get_settings

settings = get_settings()

ALLOWED_MIME_TYPES = {"application/pdf", "image/vnd.dxf", "application/dxf"}
ALLOWED_EXTENSIONS = {".pdf", ".dxf"}


async def save_upload(file: UploadFile, project_id: str) -> dict:
    """
    Validates and saves an uploaded file.
    Returns metadata dict.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Only PDF is supported in Phase 1.")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)

    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit.")

    upload_dir = Path(settings.UPLOAD_DIR) / project_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    dest = upload_dir / f"{file_id}{ext}"
    dest.write_bytes(content)

    if ext == ".pdf":
        page_count = _count_pdf_pages(content)
    else:
        page_count = 1

    return {
        "file_path": str(dest),
        "file_size_mb": round(size_mb, 2),
        "page_count": page_count,
        "original_filename": file.filename,
    }


def _count_pdf_pages(content: bytes) -> int:
    """Quick page count by scanning PDF cross-reference."""
    try:
        count = content.count(b"/Page\n") + content.count(b"/Page ")
        return max(count, 1)
    except Exception:
        return 1


def delete_file(file_path: str) -> None:
    try:
        os.remove(file_path)
    except FileNotFoundError:
        pass
