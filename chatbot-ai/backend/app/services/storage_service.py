"""Local-filesystem file storage behind a small interface, so swapping in
S3/MinIO later only requires changing this module, not every caller."""

import os
import uuid

import magic
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALLOWED_IMAGE_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
ALLOWED_PDF_MIME_TYPE = "application/pdf"


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


async def _read_and_validate(file: UploadFile, max_size_mb: int) -> bytes:
    content = await file.read()
    max_bytes = max_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds the {max_size_mb}MB limit"
        )
    if len(content) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")
    return content


async def save_image(file: UploadFile, subdir: str) -> tuple[str, str]:
    """Validates + saves a branding image (logo/avatar). Returns
    (absolute_path, public_url)."""

    content = await _read_and_validate(file, settings.MAX_UPLOAD_SIZE_MB)
    detected_mime = magic.from_buffer(content, mime=True)

    # SVGs are XML text; libmagic reports them as text/xml or image/svg+xml
    # depending on platform, so accept either but still require a `.svg`-ish
    # payload structure check below is skipped here — trusting the sniffed
    # mime type against the allow-list.
    if detected_mime not in ALLOWED_IMAGE_MIME_TYPES and detected_mime not in ("text/xml", "text/plain"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported file type: {detected_mime}. Allowed: PNG, JPG, SVG, WEBP.",
        )

    if detected_mime in ("text/xml", "text/plain"):
        if b"<svg" not in content[:1000].lower():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "File does not look like a valid SVG")
        ext = ".svg"
    else:
        ext = ALLOWED_IMAGE_MIME_TYPES[detected_mime]

    directory = os.path.join(settings.STORAGE_LOCAL_PATH, subdir)
    _ensure_dir(directory)
    filename = f"{uuid.uuid4()}{ext}"
    abs_path = os.path.join(directory, filename)

    with open(abs_path, "wb") as f:
        f.write(content)

    public_url = f"/media/{subdir}/{filename}"
    return abs_path, public_url


async def save_pdf(file: UploadFile, subdir: str) -> tuple[str, str, int]:
    """Validates + saves a knowledge-base PDF. Returns (absolute_path,
    stored_filename, size_bytes)."""

    content = await _read_and_validate(file, settings.MAX_UPLOAD_SIZE_MB)
    detected_mime = magic.from_buffer(content, mime=True)
    if detected_mime != ALLOWED_PDF_MIME_TYPE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Unsupported file type: {detected_mime}. Only PDF is allowed."
        )

    directory = os.path.join(settings.STORAGE_LOCAL_PATH, subdir)
    _ensure_dir(directory)
    filename = f"{uuid.uuid4()}.pdf"
    abs_path = os.path.join(directory, filename)

    with open(abs_path, "wb") as f:
        f.write(content)

    return abs_path, filename, len(content)


def delete_file(abs_path: str) -> None:
    if abs_path and os.path.exists(abs_path):
        os.remove(abs_path)
