import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfExtractionError(Exception):
    pass


def extract_text(file_path: str) -> str:
    try:
        reader = PdfReader(file_path)
    except (PdfReadError, OSError) as exc:
        raise PdfExtractionError(f"Could not read PDF: {exc}") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise PdfExtractionError("PDF is password-protected") from exc

    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            continue

    text = "\n\n".join(pages_text)
    if not text.strip():
        raise PdfExtractionError("No extractable text found in PDF (it may be scanned/image-only)")
    return text


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, *, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """Word-based sliding-window chunking. Simple and dependency-light;
    `chunk_size`/`overlap` are word counts, not exact LLM tokens — good
    enough for retrieval granularity without pulling in a tokenizer."""

    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    step = max(chunk_size - overlap, 1)
    while start < len(words):
        chunk_words = words[start : start + chunk_size]
        chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break
        start += step
    return chunks


def estimate_token_count(text: str) -> int:
    # Rough heuristic (~4 chars/token for English); good enough for display
    # purposes, not for exact billing.
    return max(len(text) // 4, 1)
