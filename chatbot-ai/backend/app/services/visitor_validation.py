import re

from email_validator import EmailNotValidError, validate_email

_PHONE_RE = re.compile(r"^\+?[0-9][0-9\-\s().]{5,18}[0-9]$")


def validate_name(text: str) -> str | None:
    cleaned = text.strip()
    if not (1 <= len(cleaned) <= 255):
        return None
    if not re.search(r"[A-Za-zÀ-ɏ؀-ۿ]", cleaned):
        return None
    return cleaned


def validate_email_address(text: str) -> str | None:
    try:
        result = validate_email(text.strip(), check_deliverability=False)
        return result.normalized
    except EmailNotValidError:
        return None


def validate_phone(text: str) -> str | None:
    cleaned = text.strip()
    digits_only = re.sub(r"\D", "", cleaned)
    if len(digits_only) < 7 or len(digits_only) > 15:
        return None
    if not _PHONE_RE.match(cleaned):
        return None
    return cleaned
