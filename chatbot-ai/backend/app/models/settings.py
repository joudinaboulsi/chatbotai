from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin, pg_enum
from app.models.enums import SmscAuthScheme, SmtpEncryption


class EmailSettings(Base, UUIDPKMixin, TimestampMixin):
    """Singleton row (enforced in the service layer, not the schema) holding
    global SMTP configuration. smtp_password_encrypted is a Fernet
    ciphertext (see app.core.crypto) — never returned in any API response,
    and only decrypted server-side at send time."""

    __tablename__ = "email_settings"

    smtp_host: Mapped[str | None] = mapped_column(String(255))
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_username: Mapped[str | None] = mapped_column(String(255))
    smtp_password_encrypted: Mapped[str | None] = mapped_column(String(1024))
    encryption: Mapped[SmtpEncryption] = mapped_column(pg_enum(SmtpEncryption, "smtp_encryption"), default=SmtpEncryption.TLS)
    from_name: Mapped[str | None] = mapped_column(String(255))
    from_email: Mapped[str | None] = mapped_column(String(255))
    support_email: Mapped[str | None] = mapped_column(String(255))
    is_configured: Mapped[bool] = mapped_column(Boolean, default=False)


class SMSCSettings(Base, UUIDPKMixin, TimestampMixin):
    """Singleton row (enforced in the service layer) holding the SMSC API
    integration config. api_key_encrypted is a Fernet ciphertext (see
    app.core.crypto) — never returned in any API response, and only
    decrypted server-side at call time. The chatbot never talks to the SMSC
    MySQL database directly; this is the only address it knows about."""

    __tablename__ = "smsc_settings"

    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    api_base_url: Mapped[str | None] = mapped_column(String(500))
    api_key_encrypted: Mapped[str | None] = mapped_column(String(1024))
    auth_scheme: Mapped[SmscAuthScheme] = mapped_column(
        pg_enum(SmscAuthScheme, "smsc_auth_scheme"), default=SmscAuthScheme.BEARER
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    session_expire_minutes: Mapped[int] = mapped_column(Integer, default=30)
    is_configured: Mapped[bool] = mapped_column(Boolean, default=False)
