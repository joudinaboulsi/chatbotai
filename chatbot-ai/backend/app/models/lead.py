import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin, pg_enum
from app.models.enums import LeadSource, LeadStatus


class Lead(Base, UUIDPKMixin, TimestampMixin):
    """One lead per conversation — the unique constraint on conversation_id
    is what prevents duplicate-lead creation; lead detection always upserts
    against it instead of inserting blindly."""

    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("conversation_id", name="uq_lead_conversation"),)

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    company: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[LeadSource] = mapped_column(pg_enum(LeadSource, "lead_source"), default=LeadSource.MANUAL, nullable=False)
    status: Mapped[LeadStatus] = mapped_column(pg_enum(LeadStatus, "lead_status"), default=LeadStatus.NEW, nullable=False)
    assigned_operator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
