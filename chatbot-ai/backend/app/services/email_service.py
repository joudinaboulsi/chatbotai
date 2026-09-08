import logging

import aiosmtplib
from email.mime.text import MIMEText
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret
from app.models.enums import SmtpEncryption
from app.models.settings import EmailSettings

logger = logging.getLogger("app.email")


async def get_settings_row(db: AsyncSession) -> EmailSettings | None:
    result = await db.execute(select(EmailSettings).limit(1))
    return result.scalar_one_or_none()


async def get_or_create_settings_row(db: AsyncSession) -> EmailSettings:
    row = await get_settings_row(db)
    if row is None:
        row = EmailSettings()
        db.add(row)
        await db.flush()
    return row


async def send_email(db: AsyncSession, *, to_email: str, subject: str, body_text: str) -> bool:
    """Returns True if the email was actually sent. Returns False (without
    raising) if SMTP simply isn't configured yet — that's an expected admin
    setup step, not a failure. Raises on genuine send failure so callers can
    record a system_error/email_failed notification."""

    settings_row = await get_settings_row(db)
    if settings_row is None or not settings_row.is_configured or not settings_row.smtp_host:
        logger.info("Email not sent (SMTP not configured): %s", subject)
        return False

    password = decrypt_secret(settings_row.smtp_password_encrypted) if settings_row.smtp_password_encrypted else None

    message = MIMEText(body_text, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = f"{settings_row.from_name or ''} <{settings_row.from_email}>".strip()
    message["To"] = to_email

    await aiosmtplib.send(
        message,
        hostname=settings_row.smtp_host,
        port=settings_row.smtp_port,
        username=settings_row.smtp_username,
        password=password,
        use_tls=settings_row.encryption == SmtpEncryption.SSL,
        start_tls=settings_row.encryption == SmtpEncryption.TLS,
    )
    return True
