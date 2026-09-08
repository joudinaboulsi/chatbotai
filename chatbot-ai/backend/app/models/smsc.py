import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin, pg_enum
from app.models.enums import SmscSessionStatus


class SmscSession(Base, UUIDPKMixin, TimestampMixin):
    """Links one chat conversation to a validated SMSC account.

    Created in PENDING status the moment a visitor asks something
    account-specific; becomes AUTHENTICATED only after `username` is
    validated against the SMSC API (see app.services.smsc_service). The
    conversation's AI turn always resolves the caller's SMSC identity from
    this row — never from anything the visitor types once authenticated —
    so a crafted message can't switch the effective account mid-session.
    """

    __tablename__ = "smsc_sessions"
    __table_args__ = (UniqueConstraint("conversation_id", name="uq_smsc_session_conversation"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False
    )
    session_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    smsc_user_id: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    # "support" or "user", from the SMSC API's validate-user response.
    # Drives which tools smsc_ai_service offers this session — never set
    # from anything the visitor types.
    role: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[SmscSessionStatus] = mapped_column(
        pg_enum(SmscSessionStatus, "smsc_session_status"), default=SmscSessionStatus.PENDING, nullable=False
    )
    # The account-specific question that triggered the PENDING state, so it
    # can be answered immediately once the username validates instead of
    # making the visitor repeat themselves.
    pending_question: Mapped[str | None] = mapped_column(Text)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SmscApiLog(Base, UUIDPKMixin, TimestampMixin):
    """Audit trail for every call made to the SMSC API. Never stores request
    bodies, API keys, or any field value that could be a credential —
    see app.services.smsc_service._strip_sensitive."""

    __tablename__ = "smsc_api_logs"

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    smsc_user_id: Mapped[str | None] = mapped_column(String(255))
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    request_type: Mapped[str] = mapped_column(String(10), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500))
