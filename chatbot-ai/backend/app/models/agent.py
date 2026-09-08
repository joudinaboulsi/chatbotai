import uuid

from sqlalchemy import ARRAY, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPKMixin, pg_enum
from app.models.enums import AgentStatus, WidgetPosition, WidgetSize


class Agent(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)
    languages: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    status: Mapped[AgentStatus] = mapped_column(
        pg_enum(AgentStatus, "active_status"), default=AgentStatus.ACTIVE, nullable=False
    )
    notification_email: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    branding: Mapped["AgentBranding"] = relationship(
        back_populates="agent", uselist=False, cascade="all, delete-orphan"
    )
    operator_assignments: Mapped[list["OperatorAssignment"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class AgentBranding(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "agent_branding"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    logo_url: Mapped[str | None] = mapped_column(String(1024))
    avatar_url: Mapped[str | None] = mapped_column(String(1024))

    primary_color: Mapped[str] = mapped_column(String(9), default="#0066A1")
    secondary_color: Mapped[str] = mapped_column(String(9), default="#003D63")
    background_color: Mapped[str] = mapped_column(String(9), default="#FFFFFF")
    text_color: Mapped[str] = mapped_column(String(9), default="#1A1A1A")
    button_color: Mapped[str] = mapped_column(String(9), default="#0066A1")

    font_family: Mapped[str] = mapped_column(String(100), default="Inter")
    font_size: Mapped[str] = mapped_column(String(20), default="14px")

    widget_position: Mapped[WidgetPosition] = mapped_column(
        pg_enum(WidgetPosition, "widget_position"), default=WidgetPosition.BOTTOM_RIGHT
    )
    widget_size: Mapped[WidgetSize] = mapped_column(
        pg_enum(WidgetSize, "widget_size"), default=WidgetSize.STANDARD
    )

    welcome_message: Mapped[str] = mapped_column(
        Text, default="Hello! I'm here to help. How can I assist you today?"
    )
    placeholder_text: Mapped[str] = mapped_column(String(255), default="Type your message...")
    display_company_name: Mapped[str | None] = mapped_column(String(255))
    display_agent_name: Mapped[str | None] = mapped_column(String(255))

    agent: Mapped["Agent"] = relationship(back_populates="branding")


class OperatorAssignment(Base, UUIDPKMixin, TimestampMixin):
    """Which agents a given operator/admin user may access.

    Super Admins bypass this check entirely in the authorization layer, but
    still get rows here for consistent auditing/listing.
    """

    __tablename__ = "operator_assignments"
    __table_args__ = (UniqueConstraint("user_id", "agent_id", name="uq_operator_agent"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="agent_assignments")
    agent: Mapped["Agent"] = relationship(back_populates="operator_assignments")
