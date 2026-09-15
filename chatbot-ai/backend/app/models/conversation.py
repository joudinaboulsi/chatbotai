import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin, pg_enum
from app.models.enums import ConversationStatus, MessageSender


class Visitor(Base, UUIDPKMixin, TimestampMixin):
    """A website visitor interacting with a given Agent's widget.

    Identified by an opaque session token stored client-side (cookie/
    localStorage); never authenticated, never granted admin access.
    """

    __tablename__ = "visitors"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    session_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    # Answers collected by the public sales conversation flow (business
    # type, use case, monthly volume, destination countries, whether they
    # have a website/app to integrate) — free-form like name/email/phone,
    # just grouped into one JSON blob instead of a column per field since
    # the sales workflow's exact question set is expected to keep evolving.
    # See app.services.sales_flow_service. Wrapped in MutableDict so an
    # in-place mutation (profile["x"] = y) is tracked for the UPDATE —
    # a plain JSONB column only notices whole-attribute reassignment to a
    # genuinely different object, which silently drops in-place edits.
    sales_profile: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="visitor")


class Conversation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "conversations"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ConversationStatus] = mapped_column(
        pg_enum(ConversationStatus, "conversation_status"), default=ConversationStatus.AI_ACTIVE, nullable=False
    )
    assigned_operator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    visitor: Mapped["Visitor"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_type: Mapped[MessageSender] = mapped_column(pg_enum(MessageSender, "message_sender"), nullable=False)
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
